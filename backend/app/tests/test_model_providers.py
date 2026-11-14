"""Provider settings must persist, switch runtime configuration, and keep secrets server-side."""

from uuid import UUID

import httpx
import pytest
from cryptography.fernet import Fernet
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.api.routes.model_providers import router
from app.core.config import settings
from app.db.models import Base, ModelProvider
from app.db.session import get_db
from app.services import model_providers as service

PREFIX = "/api/settings/model-providers"
SECRET = "sk-unit-test-never-display-this-value"


@pytest.fixture
def provider_app(tmp_path, monkeypatch):
    database_path = tmp_path / "providers.db"
    engine = create_engine(f"sqlite:///{database_path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    key_path = tmp_path / "provider-secret.key"
    monkeypatch.setenv("DEVHARBOR_PROVIDER_KEY_FILE", str(key_path))
    monkeypatch.setattr(settings, "token_encryption_key", "change-me-in-local-dev")
    monkeypatch.setattr(settings, "llm_api_key", "")
    monkeypatch.setattr(settings, "llm_base_url", "https://environment.invalid/v1")
    monkeypatch.setattr(settings, "llm_model", "environment-model")
    monkeypatch.setattr(service.db_session, "SessionLocal", sessions)
    app = FastAPI()
    app.include_router(router, prefix=PREFIX)

    @app.exception_handler(service.ModelProviderError)
    async def provider_error(_request, exc):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})

    def database():
        with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = database
    with TestClient(app) as client:
        yield client, sessions, key_path, engine, database_path
    engine.dispose()


def create(client, **overrides):
    payload = {
        "name": "我的模型服务", "base_url": "https://models.example.test/v1/",
        "protocol": "openai_compatible", "api_key": SECRET,
        "models": ["model-a", "model-b"], "default_model": "model-a",
        **overrides,
    }
    return client.post(PREFIX, json=payload)


def activate(client, provider_id, model="model-a"):
    return client.post(f"{PREFIX}/activate", json={"provider_id": provider_id, "model": model})


def test_crud_never_returns_plaintext_or_ciphertext_and_activation_persists(provider_app, monkeypatch):
    client, sessions, key_path, engine, database_path = provider_app
    response = create(client)
    assert response.status_code == 201
    provider = response.json()
    assert provider["has_api_key"] is True
    assert provider["base_url"] == "https://models.example.test/v1"
    assert "api_key" not in provider and "api_key_encrypted" not in provider
    assert SECRET not in response.text
    assert key_path.exists()
    with sessions() as db:
        stored = db.get(ModelProvider, UUID(provider["id"]))
        assert stored.api_key_encrypted != SECRET
        encrypted = stored.api_key_encrypted
    assert activate(client, provider["id"], "model-b").status_code == 200
    listing = client.get(PREFIX)
    assert SECRET not in listing.text and encrypted not in listing.text
    assert listing.json()["active"] == {"provider_id": provider["id"], "model": "model-b"}

    # A fresh connection/session factory has no in-process provider state to reuse.
    engine.dispose()
    restarted_engine = create_engine(f"sqlite:///{database_path}")
    monkeypatch.setattr(service.db_session, "SessionLocal", sessionmaker(bind=restarted_engine))
    runtime = service.resolve_model_config()
    assert runtime.api_key == SECRET
    assert runtime.model == "model-b"
    assert runtime.provider_id == provider["id"]
    assert runtime.enabled is True and runtime.source == "provider"
    assert SECRET not in repr(runtime)
    restarted_engine.dispose()

    removed = client.delete(f"{PREFIX}/{provider['id']}")
    assert removed.status_code == 200
    assert client.get(PREFIX).json()["active"] == {"provider_id": None, "model": None}
    assert client.get(PREFIX).json()["providers"] == []


def test_edit_preserves_blank_key_and_requires_reentry_for_changed_url(provider_app):
    client, sessions, *_ = provider_app
    provider_id = create(client).json()["id"]
    assert activate(client, provider_id).status_code == 200
    response = client.patch(f"{PREFIX}/{provider_id}", json={"name": "重命名", "api_key": ""})
    assert response.status_code == 200
    assert service.resolve_model_config().api_key == SECRET
    response = client.patch(f"{PREFIX}/{provider_id}", json={"base_url": "https://other.example.test/v1"})
    assert response.status_code == 400
    assert SECRET not in response.text
    assert service.resolve_model_config().base_url == "https://models.example.test/v1"
    response = client.patch(f"{PREFIX}/{provider_id}", json={"base_url": "https://other.example.test/v1", "api_key": "replacement-secret"})
    assert response.status_code == 200
    assert service.resolve_model_config().api_key == "replacement-secret"
    assert service.resolve_model_config().base_url == "https://other.example.test/v1"
    response = client.patch(f"{PREFIX}/{provider_id}", json={"clear_api_key": True})
    assert response.json()["has_api_key"] is False
    assert service.resolve_model_config().api_key is None


def test_model_catalog_edits_keep_active_selection_valid(provider_app):
    client, *_ = provider_app
    provider_id = create(client).json()["id"]
    activate(client, provider_id, "model-b")
    assert client.patch(f"{PREFIX}/{provider_id}", json={"models": ["new-model"]}).status_code == 400
    response = client.patch(f"{PREFIX}/{provider_id}", json={"models": ["new-model"], "default_model": "new-model"})
    assert response.status_code == 200
    assert service.resolve_model_config().model == "new-model"
    assert activate(client, provider_id, "unknown-model").status_code == 400


def test_local_provider_without_a_key_is_enabled_and_reset_returns_environment(provider_app):
    client, _, key_path, *_ = provider_app
    provider_id = create(client, base_url="http://localhost:11434/v1", api_key="").json()["id"]
    assert not key_path.exists()
    activate(client, provider_id)
    config = service.resolve_model_config()
    assert config.enabled is True and config.api_key is None
    assert config.base_url == "http://localhost:11434/v1"
    assert client.post(f"{PREFIX}/reset-active", json={}).status_code == 200
    config = service.resolve_model_config()
    assert config.source == "environment" and config.enabled is False
    assert config.model == "environment-model"


@pytest.mark.parametrize("url", [
    "file:///etc/passwd", "https://user:password@example.com/v1",
    "https://example.com/v1?token=secret", "https://example.com/v1#secret",
    "https://example.com/v1/chat/completions", "https://example.com/v1/models",
    "https://example.com:invalid/v1", "https://@example.com/v1",
])
def test_invalid_addresses_are_rejected_without_echoing_credentials(provider_app, url):
    client, *_ = provider_app
    response = create(client, base_url=url)
    assert response.status_code == 422
    assert SECRET not in response.text
    assert "input" not in response.text


def test_validation_does_not_echo_entire_secret_bearing_payload(provider_app):
    client, *_ = provider_app
    response = create(client, default_model="not-in-catalog")
    assert response.status_code == 422
    assert SECRET not in response.text and "input" not in response.text

    # SecretStr still reports a framework validation error for an invalid input type.
    response = create(client, api_key={"nested": SECRET})
    assert response.status_code == 422
    assert SECRET not in response.text and "input" not in response.text


def test_lost_or_replaced_encryption_key_fails_explicitly_without_environment_fallback(provider_app):
    client, _, key_path, *_ = provider_app
    provider_id = create(client).json()["id"]
    activate(client, provider_id)
    key_path.write_bytes(Fernet.generate_key())
    with pytest.raises(service.ModelProviderError) as failure:
        service.resolve_model_config()
    assert failure.value.status_code == 503
    assert SECRET not in str(failure.value)
    assert activate(client, provider_id).status_code == 503
    assert client.patch(f"{PREFIX}/{provider_id}", json={"api_key": "reentered-secret"}).status_code == 200
    assert service.resolve_model_config().api_key == "reentered-secret"


def test_missing_key_file_never_silently_regenerates_during_resolution(provider_app):
    client, _, key_path, *_ = provider_app
    provider_id = create(client).json()["id"]
    activate(client, provider_id)
    key_path.unlink()
    with pytest.raises(service.ModelProviderError) as failure:
        service.resolve_model_config()
    assert failure.value.status_code == 503
    assert not key_path.exists()
    assert client.patch(f"{PREFIX}/{provider_id}", json={"api_key": "replacement-key"}).status_code == 200
    assert key_path.exists()
    assert service.resolve_model_config().api_key == "replacement-key"


def mock_catalog(monkeypatch, *, status=200, body=None):
    calls = []

    class FakeClient:
        def __init__(self, **kwargs):
            assert kwargs["follow_redirects"] is False

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, url, headers):
            calls.append((url, headers))
            return httpx.Response(status, json=body, request=httpx.Request("GET", url))

    monkeypatch.setattr(service.httpx, "AsyncClient", FakeClient)
    return calls


def test_model_discovery_uses_saved_key_only_for_unchanged_address(provider_app, monkeypatch):
    client, *_ = provider_app
    provider_id = create(client).json()["id"]
    calls = mock_catalog(monkeypatch, body={"data": [{"id": "b"}, {"id": "a"}, {"id": "a"}, {"id": SECRET}]})
    denied = client.post(f"{PREFIX}/discover-models", json={"provider_id": provider_id, "base_url": "https://other.test/v1"})
    assert denied.status_code == 400 and not calls
    response = client.post(f"{PREFIX}/discover-models", json={"provider_id": provider_id, "base_url": "https://models.example.test/v1"})
    assert response.status_code == 200 and response.json() == {"models": ["a", "b"]}
    assert calls == [("https://models.example.test/v1/models", {"Authorization": f"Bearer {SECRET}"})]
    assert SECRET not in response.text


def test_keyless_local_discovery_sends_no_authorization_header(provider_app, monkeypatch):
    client, *_ = provider_app
    calls = mock_catalog(monkeypatch, body={"data": [{"id": "local-model"}]})
    response = client.post(f"{PREFIX}/discover-models", json={"base_url": "http://127.0.0.1:11434/v1"})
    assert response.json() == {"models": ["local-model"]}
    assert calls == [("http://127.0.0.1:11434/v1/models", {})]


@pytest.mark.parametrize("status", [302, 401, 403, 404, 429, 500])
def test_discovery_errors_do_not_forward_provider_bodies_or_keys(provider_app, monkeypatch, status):
    client, *_ = provider_app
    mock_catalog(monkeypatch, status=status, body={"error": f"upstream accidentally echoed {SECRET}"})
    response = client.post(f"{PREFIX}/discover-models", json={"base_url": "https://models.test/v1", "api_key": SECRET})
    assert response.status_code == 502
    assert SECRET not in response.text and "upstream" not in response.text


def test_missing_selection_table_allows_legacy_isolated_callers(provider_app):
    from sqlalchemy.pool import StaticPool

    engine = create_engine("sqlite://", poolclass=StaticPool)
    with sessionmaker(bind=engine)() as db:
        resolved = service.resolve_model_config(db)
    assert resolved.source == "environment"
    engine.dispose()


def test_database_failure_is_not_silently_treated_as_missing_configuration(provider_app):
    from sqlalchemy.exc import OperationalError

    class BrokenSession:
        def get(self, *args):
            raise OperationalError("SELECT model_provider_selection", {}, RuntimeError("database is locked"))

    with pytest.raises(OperationalError):
        service.resolve_model_config(BrokenSession())
