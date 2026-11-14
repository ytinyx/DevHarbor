import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app import main
from app.core.config import settings
from app.db import session as db_session
from app.db.models import Base, Document, KnowledgeBaseConfig, Repository, RetrievalModelSetting
from app.services.rag import embeddings, vector_store


PATH = "/api/settings/retrieval-models"


@pytest.fixture
def database(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{(tmp_path / 'retrieval.db').as_posix()}")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    monkeypatch.setattr(main, "engine", engine)
    monkeypatch.setattr(db_session, "SessionLocal", sessions)
    monkeypatch.setenv("DEVHARBOR_PROVIDER_KEY_FILE", str(tmp_path / "providers.key"))
    monkeypatch.setattr(settings, "token_encryption_key", "change-me-in-local-dev")
    yield sessions
    engine.dispose()


def test_settings_keep_credentials_private_and_separate(database):
    with TestClient(main.create_app()) as client:
        invalid = client.put(PATH, json={"embedding": {"api_key": "secret-on-invalid-request"}})
        assert invalid.status_code == 422
        assert "secret-on-invalid-request" not in invalid.text

        response = client.put(PATH, json={"rerank": {
            "base_url": "https://rank.example.test/v1/reranks/", "model": "rank-a", "api_key": "rank-test-secret",
        }})
        assert response.status_code == 200, response.text
        assert response.json()["restart_required"] is True
        assert response.json()["rerank"] == {
            "base_url": "https://rank.example.test/v1", "model": "rank-a", "has_api_key": True,
        }
        assert "rank-test-secret" not in response.text
        refused = client.put(PATH, json={"rerank": {"base_url": "https://other.example.test/v1", "model": "rank-a"}})
        assert refused.status_code == 400
        response = client.put(PATH, json={"embedding": {
            "provider": "local", "model": "local-embedding", "dimensions": 128, "milvus_uri": "http://127.0.0.1:19530",
        }})
        assert response.status_code == 200, response.text
        assert response.json()["rerank"]["has_api_key"] is True

    with database() as db:
        row = db.get(RetrievalModelSetting, "rerank")
        assert row.configuration == {"base_url": "https://rank.example.test/v1", "model": "rank-a"}
        assert row.api_key_encrypted and "rank-test-secret" not in row.api_key_encrypted


def test_restart_reconciles_existing_knowledge_and_reindexes_into_a_separate_collection(database, monkeypatch):
    indexed = []
    hits = []

    class Milvus:
        def __init__(self):
            self.collection_name = settings.milvus_collection

        def delete_documents(self, **_):
            return 0

        def upsert_documents(self, documents, vectors):
            indexed.extend((self.collection_name, doc.content, vector) for doc, vector in zip(documents, vectors))

        def search(self, **_):
            return hits

    def embed(texts, dimensions, **_):
        assert settings.embedding_api_key == "embed-test-secret"
        return [[1.0] * dimensions for _ in texts]

    monkeypatch.setattr(vector_store, "MilvusVectorStore", Milvus)
    monkeypatch.setattr(embeddings, "_embed_openai_compatible", embed)
    with database() as db:
        repo = Repository(owner="example", name="docs", full_name="example/docs")
        db.add(repo)
        db.flush()
        repo_id = repo.id
        db.add(KnowledgeBaseConfig(
            repo_id=repo_id, embedding_provider="disabled", embedding_model="disabled", embedding_dimensions=128,
            retrieval_method="fulltext", chunk_size=333, chunk_overlap=50,
        ))
        document = Document(repo_id=repo_id, source_type="knowledge_file", source_id=repo_id, title="Guide", content="Original text")
        db.add(document)
        db.flush()
        document_id = document.id
        db.commit()

    original_collection = settings.milvus_collection
    payload = {"embedding": {
        "provider": "openai_compatible", "base_url": "https://embed.example.test/v1/embeddings",
        "model": "embed-a", "dimensions": 128, "api_key": "embed-test-secret", "milvus_uri": "http://127.0.0.1:19530",
    }}
    with TestClient(main.create_app()) as client:
        saved = client.put(PATH, json=payload)
        assert saved.status_code == 200, saved.text
        assert saved.json()["restart_required"] is True
        assert settings.milvus_collection == original_collection
    with TestClient(main.create_app()) as client:
        collection = settings.milvus_collection
        assert collection != original_collection
        assert client.get(PATH).json()["restart_required"] is False
        response = client.get(f"/api/rag/repositories/{repo_id}")
        assert response.status_code == 200, response.text
        config = response.json()["config"]
        assert config["embedding_model"] == "embed-a"
        assert config["chunk_size"] == 333
        rebuilt = client.post(f"/api/rag/{repo_id}/reindex")
        assert rebuilt.status_code == 200, rebuilt.text
        assert indexed == [(collection, "Original text", [1.0] * 128)]
        hits.extend([{"id": str(repo_id), "score": 0.99}, {"id": str(document_id), "score": 0.8}])
        assert client.patch(f"/api/rag/repositories/{repo_id}/config", json={
            "retrieval_method": "vector", "rerank_enabled": False, "score_threshold_enabled": False,
        }).status_code == 200
        result = client.post(f"/api/rag/{repo_id}/search", json={"question": "Original text"})
        assert result.status_code == 200, result.text
        assert [item["document_id"] for item in result.json()["results"]] == [str(document_id)]
        payload["embedding"]["model"] = "embed-b"
        payload["embedding"].pop("api_key")
        assert client.put(PATH, json=payload).json()["restart_required"] is True
    with TestClient(main.create_app()) as client:
        assert settings.milvus_collection != collection
        payload["embedding"]["model"] = "embed-a"
        assert client.put(PATH, json=payload).json()["restart_required"] is True
    with TestClient(main.create_app()) as client:
        assert settings.milvus_collection != collection
        assert client.put(PATH, json={"embedding": None}).json()["restart_required"] is True
    with TestClient(main.create_app()) as client:
        assert settings.milvus_collection == original_collection
        assert client.get(f"/api/rag/repositories/{repo_id}").status_code == 200
        assert client.get(PATH).json()["restart_required"] is False
    with database() as db:
        assert db.scalar(select(Document).where(Document.repo_id == repo_id)).content == "Original text"


def test_pgvector_connection_test_and_save_explain_sqlite_requirement(database):
    with TestClient(main.create_app()) as client:
        result = client.post(f"{PATH}/test-vector-store", json={"vector_backend": "pgvector"})
        assert result.status_code == 200
        assert result.json()["ready"] is False
        assert "DATABASE_URL" in result.json()["message"]
        saved = client.put(PATH, json={"embedding": {
            "provider": "local", "model": "embed-pg", "dimensions": 128, "vector_backend": "pgvector",
        }})
        assert saved.status_code == 400
        assert client.get(PATH).json()["embedding"] is None


def test_pgvector_selection_routes_reindex_and_search_after_restart(database, monkeypatch):
    indexed = {}
    writes = []

    def upsert(store, documents, vectors, *, db):
        assert db.in_transaction()
        writes.append(("upsert", store.collection_name))
        indexed.update((doc.id, vector) for doc, vector in zip(documents, vectors))

    def delete(store, *, db, repo_id, **_):
        assert db.in_transaction()
        assert repo_id == expected_repo_id
        writes.append(("delete", store.collection_name))

    def search(store, *, db, repo_id, query_embedding, **_):
        assert db.in_nested_transaction()
        assert repo_id == expected_repo_id
        assert store.collection_name == settings.pgvector_collection
        assert len(query_embedding) == 128
        return [{"id": str(document_id), "score": 1.0} for document_id in indexed]

    adapter = vector_store.PgvectorStore
    monkeypatch.setattr(adapter, "probe", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(adapter, "prepare_write", lambda *_: None)
    monkeypatch.setattr(adapter, "upsert_documents", upsert)
    monkeypatch.setattr(adapter, "delete_documents", delete)
    monkeypatch.setattr(adapter, "search", search)
    monkeypatch.setattr(embeddings, "_embed_openai_compatible", lambda texts, dimensions, **_: [[1.0] * dimensions for _ in texts])
    with database() as db:
        repo = Repository(owner="example", name="pgvector", full_name="example/pgvector")
        db.add(repo)
        db.flush()
        expected_repo_id = repo.id
        doc = Document(repo_id=repo.id, source_type="knowledge_file", source_id=repo.id, title="Guide", content="Saved guide")
        db.add(doc)
        db.flush()
        expected_doc_id = doc.id
        db.commit()

    with TestClient(main.create_app()) as client:
        assert client.post(f"{PATH}/test-vector-store", json={"vector_backend": "pgvector"}).json()["ready"]
        saved = client.put(PATH, json={"embedding": {
            "provider": "openai_compatible", "model": "embed-pg", "dimensions": 128, "vector_backend": "pgvector",
            "base_url": "https://embed.example.test/v1", "api_key": "embed-test-secret",
        }})
        assert saved.status_code == 200, saved.text
        assert saved.json()["embedding"]["vector_backend"] == "pgvector"
        assert saved.json()["restart_required"] is True
        assert settings.vector_backend == "milvus"

    with TestClient(main.create_app()) as client:
        assert client.get(PATH).json()["restart_required"] is False
        assert client.get(f"/api/rag/{expected_repo_id}/status").json()["vector_store"]["backend"] == "pgvector"
        assert client.post(f"/api/rag/{expected_repo_id}/reindex").status_code == 200
        assert writes == [("delete", settings.pgvector_collection), ("upsert", settings.pgvector_collection)]
        assert client.patch(f"/api/rag/repositories/{expected_repo_id}/config", json={
            "retrieval_method": "vector", "rerank_enabled": False, "score_threshold_enabled": False,
        }).status_code == 200
        result = client.post(f"/api/rag/{expected_repo_id}/search", json={"question": "Saved guide"})
        assert result.status_code == 200, result.text
        assert [item["document_id"] for item in result.json()["results"]] == [str(expected_doc_id)]
