import asyncio
import hashlib
import json
from io import BytesIO

import httpx
import pytest
from fastapi import UploadFile
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.routes.knowledge import upload_knowledge_file
from app.api.routes.rag import update_rag_config
from app.core.config import settings
from app.db.models import Base, Document, Issue, KnowledgeBaseConfig, KnowledgeSourceDocument, Repository
from app.schemas.rag import KnowledgeBaseConfigUpdate
from app.services.rag import document_processing, embeddings, indexing, knowledge_base, qa, retrieval, vector_store


@pytest.fixture
def keyword_store(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "embedding_provider", "disabled")
    monkeypatch.setattr(settings, "embedding_model", "disabled")
    monkeypatch.setattr(settings, "embedding_dimensions", 128)
    monkeypatch.setattr(settings, "milvus_enabled", False)
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path / "uploads"))

    def forbidden(*_args, **_kwargs):
        raise AssertionError("Keyword-only operation attempted vector generation or a vector database request")

    for module, name in [
        (vector_store, "embed_text"), (vector_store, "embed_texts"), (vector_store, "_milvus_store"),
        (embeddings, "_local_sentence_transformer"), (embeddings, "deterministic_embedding"),
        (indexing, "embed_knowledge_texts"), (document_processing, "_embed_in_batches"),
        (knowledge_base, "embed_knowledge_query"), (qa, "embed_knowledge_texts"), (qa, "embed_texts"),
    ]:
        monkeypatch.setattr(module, name, forbidden)
    monkeypatch.setattr("app.api.routes.knowledge._embed_default_in_batches", forbidden)

    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'keyword.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    monkeypatch.setattr(document_processing, "SessionLocal", factory)
    db = factory()
    repo = Repository(owner="local", name="keyword", full_name="local/keyword")
    db.add(repo)
    db.commit()
    yield db, repo
    db.close()
    engine.dispose()


@pytest.mark.parametrize("method", ["fulltext", "hybrid", "vector"])
def test_keyword_write_and_retrieval_never_generate_vectors(keyword_store, method):
    db, repo = keyword_store
    vector_store.add_document(db, repo.id, "memory_note", None, "部署回滚", "发布失败时先回滚版本，再检查部署日志。")
    vector_store.add_documents(db, repo.id, [vector_store.DocumentPayload(
        source_type="knowledge_file", title="部署说明", content="部署前应备份数据库并准备回滚。",
        metadata={"embedding_provider": "stale-provider", "embedding_model": "stale-model"},
    )])
    trace = {}
    results = retrieval.search_similar_documents(db, repo.id, "部署 回滚", retrieval_method=method, pipeline_trace=trace)
    assert results
    assert trace["retrieval_method"] == "fulltext"
    assert trace["requested_retrieval_method"] == method
    assert trace["semantic_enabled"] is False
    assert trace["stages"][0]["status"] == "disabled"
    assert all(item["retrieval"]["sources"] == ["keyword"] for item in results)
    for doc in db.query(Document).all():
        assert doc.meta["semantic_enabled"] is False
        assert doc.meta["retrieval_backend"] == "bm25"
        assert not any(key.startswith("embedding_") for key in doc.meta)


def test_synced_repository_and_reindex_work_without_embeddings(keyword_store):
    db, repo = keyword_store
    db.add(Issue(repo_id=repo.id, number=1, title="登录失败", body="令牌过期后刷新失败。", state="open"))
    # Existing semantic settings from an imported repository must not load a model.
    db.add(KnowledgeBaseConfig(repo_id=repo.id, embedding_provider="local", embedding_model="old-model", embedding_dimensions=1024))
    db.commit()
    assert indexing.index_repository_documents(db, repo.id) == 1
    db.commit()
    assert qa.reindex_documents(db, repo.id) == 1
    assert retrieval.search_similar_documents(db, repo.id, "登录失败")
    results, trace, _ = asyncio.run(knowledge_base.retrieve_knowledge(db, repo.id, "登录失败", retrieval_method="hybrid"))
    assert results
    assert trace["retrieval_method"] == "fulltext"
    assert trace["rerank_enabled"] is False
    assert trace["runtime"]["embedding"]["available"] is False
    assert trace["runtime"]["retrieval"]["available"] is True
    assert db.query(KnowledgeBaseConfig).one().embedding_model == "old-model"


def test_both_upload_paths_complete_without_embeddings(keyword_store, tmp_path):
    db, repo = keyword_store
    file_bytes = "# 发布说明\n发布前执行检查，部署失败时回滚。".encode()
    upload = UploadFile(filename="release.md", file=BytesIO(file_bytes))
    result = asyncio.run(upload_knowledge_file(repo.id, upload, db))
    assert result.indexed and result.chunks > 0
    db.commit()

    stored_path = tmp_path / "process.md"
    stored_path.write_bytes(file_bytes)
    source = KnowledgeSourceDocument(repo_id=repo.id, name="process.md", stored_path=str(stored_path),
                                     checksum=hashlib.sha256(file_bytes).hexdigest(), file_size=len(file_bytes))
    db.add(source)
    db.commit()
    document_processing.process_knowledge_document(source.id)
    db.refresh(source)
    assert source.status == "completed"
    assert source.chunk_count > 0
    assert source.error_message is None
    assert db.query(Document).filter(Document.source_id == source.id).count() == source.chunk_count


def test_disabled_catalog_and_status_never_claim_semantic_availability(keyword_store):
    db, repo = keyword_store
    config = knowledge_base.get_or_create_config(db, repo.id)
    assert config.retrieval_method == "fulltext"
    assert config.rerank_enabled is False
    model = knowledge_base.model_catalog()["embedding_models"][0]
    assert model["provider"] == "disabled"
    assert model["available"] is False
    assert "关键词" in model["label"]
    assert "未启用语义" in model["label"]
    runtime = knowledge_base.runtime_status(config)
    assert runtime["embedding"]["available"] is False
    assert runtime["retrieval"]["backend"] == "bm25"
    assert vector_store.vector_store_runtime_status()["status"] == "keyword_only"
    with pytest.raises(RuntimeError, match="语义检索尚未启用"):
        embeddings.embed_text("不能伪造向量")


def test_configured_qwen_rerank_runs_after_bm25_without_embeddings(keyword_store, monkeypatch):
    db, repo = keyword_store
    config = knowledge_base.get_or_create_config(db, repo.id)
    assert not config.rerank_enabled
    vector_store.add_document(db, repo.id, "memory_note", None, "部署回滚", "发布失败时先回滚版本。")
    monkeypatch.setattr(settings, "rerank_api_key", "test-key")
    monkeypatch.setattr(settings, "rerank_base_url", "https://rerank.example.test/v1")
    monkeypatch.setattr(settings, "qwen_rerank_model", "custom-reranker")
    client_class = httpx.AsyncClient

    def rerank_api(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert str(request.url) == "https://rerank.example.test/v1/reranks"
        assert payload["model"] == "custom-reranker"
        assert "部署回滚" in payload["documents"][0]
        return httpx.Response(200, json={"results": [{"index": 0, "relevance_score": 0.95}]})

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: client_class(transport=httpx.MockTransport(rerank_api), **kwargs))
    saved = asyncio.run(update_rag_config(repo.id, KnowledgeBaseConfigUpdate(
        retrieval_method="hybrid", rerank_enabled=True, rerank_model="custom-reranker",
    ), db))
    assert saved.config["retrieval_method"] == "fulltext"
    assert saved.runtime["rerank"]["enabled"] is True
    assert saved.runtime["rerank"]["available"] is True
    assert saved.runtime["retrieval"]["backend"] == "bm25"

    results, trace, _ = asyncio.run(knowledge_base.retrieve_knowledge(db, repo.id, "部署 回滚"))
    assert results[0]["retrieval"]["sources"] == ["keyword"]
    assert results[0]["retrieval"]["rerank_model"] == "custom-reranker"
    assert next(stage for stage in trace["pipeline"]["stages"] if stage["name"] == "rerank")["mode"] == "qwen_api"
