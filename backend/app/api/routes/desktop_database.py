from pathlib import Path
from threading import Lock

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, SecretStr

from app.api.routes.model_providers import CredentialSafeRoute
from app.core.config import settings
from desktop_database import (
    DatabaseMode, DatabaseProfile, DesktopDatabaseError, INVALID_PROFILE_WARNING,
    normalize_postgres_url, probe_postgres, read_postgres_url, read_profile, save_profile,
)


router = APIRouter(route_class=CredentialSafeRoute)
_profile_lock = Lock()


class DesktopDatabaseTest(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    url: SecretStr | None = Field(default=None, max_length=4096)


class DesktopDatabaseUpdate(DesktopDatabaseTest):
    mode: DatabaseMode


class DesktopDatabaseStatus(BaseModel):
    active_mode: DatabaseMode
    configured_mode: DatabaseMode
    has_postgresql_url: bool
    restart_required: bool
    warning: str | None = None


class DesktopDatabaseTestResult(BaseModel):
    ready: bool
    pgvector_available: bool
    message: str


def _desktop_data_dir() -> Path:
    if not settings.desktop_mode or not settings.desktop_data_dir:
        raise HTTPException(status_code=404, detail="数据库设置仅适用于 DevHarbor 桌面版。")
    return Path(settings.desktop_data_dir)


def _database_status(data_dir: Path) -> DesktopDatabaseStatus:
    active_mode = settings.desktop_database_mode
    warning = settings.desktop_database_warning or None
    profile = DatabaseProfile()
    configured_url = None
    try:
        profile = read_profile(data_dir)
        if profile.mode == "postgresql":
            configured_url = read_postgres_url(data_dir, profile)
    except DesktopDatabaseError:
        warning = INVALID_PROFILE_WARNING
    return DesktopDatabaseStatus(
        active_mode=active_mode,
        configured_mode=profile.mode,
        has_postgresql_url=bool(profile.encrypted_url),
        restart_required=active_mode != profile.mode or (
            active_mode == "postgresql" and configured_url != settings.database_url
        ),
        warning=warning,
    )


@router.get("", response_model=DesktopDatabaseStatus)
def get_desktop_database(data_dir: Path = Depends(_desktop_data_dir)) -> DesktopDatabaseStatus:
    return _database_status(data_dir)


@router.put("", response_model=DesktopDatabaseStatus)
def update_desktop_database(payload: DesktopDatabaseUpdate, data_dir: Path = Depends(_desktop_data_dir)) -> DesktopDatabaseStatus:
    with _profile_lock:
        try:
            previous = read_profile(data_dir)
        except DesktopDatabaseError:
            previous = DatabaseProfile()
        try:
            url = None
            if payload.mode == "postgresql":
                if payload.url is None:
                    url = read_postgres_url(data_dir, previous)
                else:
                    url = normalize_postgres_url(payload.url.get_secret_value())
                result = probe_postgres(url)
                if not result.ready:
                    raise HTTPException(status_code=400, detail=result.message)
            save_profile(data_dir, payload.mode, previous, url)
        except DesktopDatabaseError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None
        return _database_status(data_dir)


@router.post("/test", response_model=DesktopDatabaseTestResult)
def test_desktop_database(payload: DesktopDatabaseTest | None = None, data_dir: Path = Depends(_desktop_data_dir)) -> DesktopDatabaseTestResult:
    try:
        if payload is None or payload.url is None:
            url = read_postgres_url(data_dir, read_profile(data_dir))
        else:
            url = normalize_postgres_url(payload.url.get_secret_value())
    except DesktopDatabaseError as exc:
        return DesktopDatabaseTestResult(ready=False, pgvector_available=False, message=str(exc))
    result = probe_postgres(url)
    return DesktopDatabaseTestResult(ready=result.ready, pgvector_available=result.pgvector_available, message=result.message)
