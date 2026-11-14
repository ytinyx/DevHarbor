import json
import uuid

import httpx
import pytest

from app.core.config import settings
from app.db.models import Document
from app.services.rag.embeddings import embed_knowledge_texts, validate_embedding_contract
from app.services.rag.vector_store import _clip_utf8, _collection_dimensions, upsert_vector_documents


def test_clip_utf8_limits_encoded_length_without_breaking_characters() -> None:
    value = "\u732b" * 3000
    clipped = _clip_utf8(value, 8192)

    assert len(clipped.encode("utf-8")) <= 8192
    assert clipped
    assert set(clipped) == {"\u732b"}


def test_collection_dimension_is_read_from_milvus_schema() -> None:
    assert _collection_dimensions(
        {"fields": [{"name": "embedding", "params": {"dim": "1024"}}]}
    ) == 1024


def test_embedding_contract_rejects_per_repository_vector_spaces() -> None:
    with pytest.raises(ValueError, match="Embedding contract mismatch"):
        validate_embedding_contract("deterministic", "other-model", 384)


def test_explicit_deterministic_provider_is_allowed_without_becoming_a_fallback(monkeypatch) -> None:
    monkeypatch.setattr(settings, "embedding_provider", "deterministic")
    monkeypatch.setattr(settings, "embedding_model", "deterministic-local")
    monkeypatch.setattr(settings, "embedding_dimensions", 8)

    vectors = embed_knowledge_texts(
        ["token failure"],
        provider="deterministic",
        model="deterministic-local",
        dimensions=8,
    )

    assert len(vectors) == 1
    assert len(vectors[0]) == 8


def test_embedding_provider_failure_is_not_replaced_with_hash_vectors(monkeypatch) -> None:
    monkeypatch.setattr(settings, "embedding_provider", "openai_compatible")
    monkeypatch.setattr(settings, "embedding_model", "configured-model")
    monkeypatch.setattr(settings, "embedding_dimensions", 8)
    monkeypatch.setattr(
        "app.services.rag.embeddings._embed_openai_compatible",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("provider offline")),
    )

    with pytest.raises(RuntimeError, match="provider offline"):
        embed_knowledge_texts(
            ["token failure"],
            provider="openai_compatible",
            model="configured-model",
            dimensions=8,
        )


@pytest.mark.parametrize("url_suffix", ["/v1", "/v1/embeddings/"])
def test_remote_embeddings_limit_batches_and_preserve_input_order(monkeypatch, url_suffix) -> None:
    monkeypatch.setattr(settings, "embedding_provider", "openai_compatible")
    monkeypatch.setattr(settings, "embedding_model", "configured-model")
    monkeypatch.setattr(settings, "embedding_dimensions", 2)
    monkeypatch.setattr(settings, "embedding_api_key", "test-key")
    monkeypatch.setattr(settings, "embedding_base_url", f"https://embedding.example.test{url_suffix}")
    batch_sizes: list[int] = []
    client_class = httpx.Client

    def embedding_api(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "https://embedding.example.test/v1/embeddings"
        payload = json.loads(request.content)
        batch = payload["input"]
        batch_sizes.append(len(batch))
        return httpx.Response(200, json={"data": [
            {"index": index, "embedding": [float(batch[index]), 1.0]}
            for index in reversed(range(len(batch)))
        ]})

    monkeypatch.setattr(httpx, "Client", lambda **kwargs: client_class(transport=httpx.MockTransport(embedding_api), **kwargs))
    vectors = embed_knowledge_texts(
        [str(index) for index in range(23)],
        provider="openai_compatible",
        model="configured-model",
        dimensions=2,
    )

    assert batch_sizes == [10, 10, 3]
    assert vectors == [[float(index), 1.0] for index in range(23)]


def test_milvus_upsert_rejects_dimension_fitting_before_connecting(monkeypatch) -> None:
    monkeypatch.setattr(settings, "embedding_dimensions", 4)
    document = Document(
        id=uuid.uuid4(),
        repo_id=uuid.uuid4(),
        source_type="issue",
        source_id=uuid.uuid4(),
        title="Token failure",
        content="Refresh failed.",
        meta={},
    )

    with pytest.raises(ValueError, match="Refusing to truncate or pad"):
        upsert_vector_documents(None, [document], [[1.0, 0.0]])
