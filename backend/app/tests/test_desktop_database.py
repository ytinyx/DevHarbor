import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError

import desktop
from app.api.routes import desktop_database as database_route
from app.core.config import settings
from app.db.models import Base
from app.main import create_app
from desktop_database import (
    DatabaseProfile, DesktopDatabaseError, PostgresProbe, PROFILE_FILENAME,
    normalize_postgres_url, read_postgres_url, read_profile, save_profile,
)


TOKEN = "test-desktop-database-" + "a" * 32
HEADERS = {"X-DevHarbor-Token": TOKEN}
ENDPOINT = "/api/settings/desktop-database"
POSTGRES_URL = "postgres://user:test-secret@localhost:5432/example?sslmode=require&connect_timeout=999"


@pytest.fixture
def desktop_profile(tmp_path, monkeypatch):
    environment = {"DEVHARBOR_DATA_DIR": str(tmp_path), "DEVHARBOR_DESKTOP_TOKEN": TOKEN}
    monkeypatch.setattr(desktop.os, "environ", environment)
    desktop.configure_environment()
    return tmp_path, environment


def test_desktop_database_normalizes_postgres_and_rejects_driver_overrides():
    url = make_url(normalize_postgres_url(POSTGRES_URL))
    assert url.drivername == "postgresql+psycopg"
    assert url.query == {"sslmode": "require", "connect_timeout": "4"}
    for value in ("postgresql+psycopg2://user:test-secret@localhost/example", POSTGRES_URL + "&host=other-host"):
        with pytest.raises(DesktopDatabaseError) as error:
            normalize_postgres_url(value)
        assert "test-secret" not in str(error.value)


def test_saved_postgres_profile_encrypts_url_and_local_fallback_keeps_it(desktop_profile):
    data_dir, environment = desktop_profile
    postgres_url = normalize_postgres_url(POSTGRES_URL)
    save_profile(data_dir, "postgresql", DatabaseProfile(), postgres_url)
    assert "test-secret" not in (data_dir / PROFILE_FILENAME).read_text(encoding="utf-8")
    assert read_postgres_url(data_dir, read_profile(data_dir)) == postgres_url

    environment["PGPASSWORD"] = "inherited-value"
    desktop.configure_environment()
    assert environment["DEVHARBOR_DESKTOP_DATABASE_MODE"] == "postgresql"
    assert environment["DATABASE_URL"] == postgres_url
    assert environment["REPO_CHECKOUT_DIR"] != str(data_dir / "repos")
    assert environment["UPLOAD_DIR"] != str(data_dir / "uploads")
    assert "PGPASSWORD" not in environment
    desktop.configure_environment(local_database=True)
    assert environment["DEVHARBOR_DESKTOP_DATABASE_MODE"] == "sqlite"
    assert "SQLite" in environment["DEVHARBOR_DESKTOP_DATABASE_WARNING"]
    assert environment["DATABASE_URL"].startswith("sqlite:///")
    assert read_profile(data_dir).mode == "postgresql"

    # An internal MCP child must inherit the active fallback, not the saved target.
    desktop.configure_environment(mcp_server=True)
    assert environment["DEVHARBOR_DESKTOP_DATABASE_MODE"] == "sqlite"


def test_corrupt_saved_profile_starts_local_with_warning(desktop_profile):
    data_dir, environment = desktop_profile
    (data_dir / PROFILE_FILENAME).write_text("corrupted profile", encoding="utf-8")
    desktop.configure_environment()
    assert environment["DEVHARBOR_DESKTOP_DATABASE_MODE"] == "sqlite"
    assert "SQLite" in environment["DEVHARBOR_DESKTOP_DATABASE_WARNING"]
    assert (data_dir / PROFILE_FILENAME).read_text(encoding="utf-8") == "corrupted profile"


def test_desktop_database_api_uses_authenticated_profile_and_reuses_saved_url(desktop_profile, monkeypatch):
    data_dir, _ = desktop_profile
    monkeypatch.setattr(settings, "desktop_mode", True)
    monkeypatch.setattr(settings, "desktop_token", TOKEN)
    monkeypatch.setattr(settings, "desktop_data_dir", str(data_dir))
    monkeypatch.setattr(settings, "desktop_database_mode", "sqlite")
    probes = []

    def probe(url):
        probes.append(url)
        return PostgresProbe(True, True, "可用")

    monkeypatch.setattr(database_route, "probe_postgres", probe)
    client = TestClient(create_app())
    assert client.get(ENDPOINT).status_code == 401
    assert client.get(ENDPOINT, headers=HEADERS).json() == {
        "active_mode": "sqlite", "configured_mode": "sqlite", "restart_required": False,
        "has_postgresql_url": False, "warning": None,
    }
    response = client.put(ENDPOINT, json={"mode": "postgresql", "url": POSTGRES_URL}, headers=HEADERS)
    assert response.status_code == 200
    assert response.json()["configured_mode"] == "postgresql"
    assert response.json()["restart_required"] is True
    assert "test-secret" not in response.text
    assert client.put(ENDPOINT, json={"mode": "sqlite"}, headers=HEADERS).json()["has_postgresql_url"] is True
    assert client.post(ENDPOINT + "/test", json={}, headers=HEADERS).json()["pgvector_available"] is True
    assert client.put(ENDPOINT, json={"mode": "postgresql"}, headers=HEADERS).status_code == 200
    assert probes == [normalize_postgres_url(POSTGRES_URL)] * 3
    invalid = client.put(ENDPOINT, json={"mode": "bad", "url": POSTGRES_URL}, headers=HEADERS)
    assert invalid.status_code == 422 and "test-secret" not in invalid.text


def test_postgres_connection_failure_reports_safe_startup_error(monkeypatch):
    monkeypatch.setattr(settings, "desktop_mode", True)
    monkeypatch.setattr(settings, "desktop_token", TOKEN)
    monkeypatch.setattr(settings, "desktop_database_mode", "postgresql")

    def fail(**_kwargs):
        raise SQLAlchemyError(POSTGRES_URL)

    monkeypatch.setattr(Base.metadata, "create_all", fail)
    app = create_app()
    with pytest.raises(RuntimeError, match="无法初始化桌面版 PostgreSQL") as error, TestClient(app):
        pass
    assert app.state.desktop_database_unavailable is True
    assert "test-secret" not in str(error.value)
    assert error.value.__suppress_context__


def test_database_api_is_not_registered_in_browser(monkeypatch):
    monkeypatch.setattr(settings, "desktop_mode", False)
    assert TestClient(create_app()).get(ENDPOINT).status_code == 404
