"""Manage the desktop database selection without importing the application."""

from dataclasses import dataclass, field
import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Literal

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.pool import NullPool


DatabaseMode = Literal["sqlite", "postgresql"]
PROFILE_FILENAME = "database-profile.json"
CONNECT_TIMEOUT = 4
INVALID_PROFILE_WARNING = "无法读取已保存的数据库配置，当前使用本地 SQLite。请重新填写 PostgreSQL 连接地址。"
LOCAL_FALLBACK_WARNING = "PostgreSQL 暂不可用，当前使用本地 SQLite。原 PostgreSQL 配置已保留。"
_POSTGRES_OPTIONS = {"sslmode", "channel_binding", "connect_timeout"}


class DesktopDatabaseError(ValueError):
    """An error safe to expose to the desktop user."""


@dataclass(frozen=True)
class DatabaseProfile:
    mode: DatabaseMode = "sqlite"
    encrypted_url: str | None = field(default=None, repr=False)


@dataclass(frozen=True)
class PostgresProbe:
    ready: bool
    pgvector_available: bool
    message: str


def normalize_postgres_url(value: str) -> str:
    try:
        if any(character in value for character in "\x00\r\n"):
            raise ValueError
        url = make_url(value.strip())
        if url.drivername not in {"postgresql", "postgres", "postgresql+psycopg"}:
            raise ValueError
        if not url.host or not url.database or not url.username or any(character in url.host for character in ",/\\"):
            raise ValueError
        if url.port is not None and not 1 <= url.port <= 65535:
            raise ValueError
        if any(name not in _POSTGRES_OPTIONS or not isinstance(option, str) for name, option in url.query.items()):
            raise ValueError
        if url.query.get("sslmode", "prefer") not in {"disable", "allow", "prefer", "require", "verify-ca", "verify-full"}:
            raise ValueError
        if url.query.get("channel_binding", "prefer") not in {"disable", "prefer", "require"}:
            raise ValueError
    except (ValueError, SQLAlchemyError):
        raise DesktopDatabaseError("请输入有效的 PostgreSQL 连接地址，包含主机、用户名和数据库名。") from None
    return url.set(drivername="postgresql+psycopg", query={**url.query, "connect_timeout": str(CONNECT_TIMEOUT)}).render_as_string(hide_password=False)


def read_profile(data_dir: Path) -> DatabaseProfile:
    try:
        payload = json.loads((data_dir / PROFILE_FILENAME).read_text(encoding="utf-8"))
        mode = payload.get("mode")
        encrypted_url = payload.get("encrypted_url")
        if mode not in {"sqlite", "postgresql"} or (encrypted_url is not None and not isinstance(encrypted_url, str)):
            raise ValueError
    except FileNotFoundError:
        return DatabaseProfile()
    except (AttributeError, OSError, TypeError, ValueError):
        raise DesktopDatabaseError(INVALID_PROFILE_WARNING) from None
    return DatabaseProfile(mode, encrypted_url)


def _profile_cipher(data_dir: Path) -> Fernet:
    return Fernet((data_dir / "secrets" / "model-providers.key").read_bytes().strip())


def read_postgres_url(data_dir: Path, profile: DatabaseProfile) -> str:
    if not profile.encrypted_url:
        raise DesktopDatabaseError("请输入 PostgreSQL 连接地址。")
    try:
        encrypted = profile.encrypted_url.encode("ascii")
        value = _profile_cipher(data_dir).decrypt(encrypted).decode("utf-8")
        return normalize_postgres_url(value)
    except (InvalidToken, OSError, ValueError):
        raise DesktopDatabaseError("无法读取已保存的 PostgreSQL 连接地址，请重新填写。") from None


def save_profile(data_dir: Path, mode: DatabaseMode, previous: DatabaseProfile, url: str | None) -> None:
    temp_path = None
    try:
        encrypted_url = previous.encrypted_url
        if url is not None:
            encrypted_url = _profile_cipher(data_dir).encrypt(url.encode("utf-8")).decode("ascii")
        payload = json.dumps({"mode": mode, "encrypted_url": encrypted_url}).encode("utf-8")
        with tempfile.NamedTemporaryFile(dir=data_dir, prefix=".database-profile-", delete=False) as stream:
            temp_path = Path(stream.name)
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_path, data_dir / PROFILE_FILENAME)
        if hasattr(os, "O_DIRECTORY"):
            directory = os.open(data_dir, os.O_DIRECTORY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
    except (OSError, ValueError):
        raise DesktopDatabaseError("无法保存数据库配置，请检查桌面数据目录的写入权限。") from None
    finally:
        if temp_path is not None:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass


def postgres_data_dir(data_dir: Path, normalized_url: str) -> Path:
    url = make_url(normalized_url)
    identity = json.dumps([url.host, url.port or 5432, url.database, url.username]).encode("utf-8")
    return data_dir / "postgresql" / hashlib.sha256(identity).hexdigest()[:24]


def probe_postgres(url: str) -> PostgresProbe:
    engine = None
    try:
        engine = create_engine(
            url, poolclass=NullPool, hide_parameters=True,
            connect_args={"options": "-c statement_timeout=4000"},
        )
        with engine.connect() as connection:
            readable, writable, vector = connection.execute(text("""
                SELECT has_schema_privilege(current_schema(), 'USAGE'),
                       current_setting('transaction_read_only') = 'off'
                           AND (has_schema_privilege(current_schema(), 'CREATE') OR (
                               to_regclass('repositories') IS NOT NULL
                               AND has_table_privilege(to_regclass('repositories'), 'INSERT')
                               AND has_table_privilege(to_regclass('repositories'), 'UPDATE')
                               AND has_table_privilege(to_regclass('repositories'), 'DELETE')
                           )),
                       EXISTS(SELECT 1 FROM pg_extension WHERE extname = 'vector')
                           AND to_regtype('vector') IS NOT NULL
            """)).one()
    except (ImportError, OSError, SQLAlchemyError):
        return PostgresProbe(False, False, "无法连接 PostgreSQL，请检查服务地址、登录凭据和网络。")
    finally:
        if engine is not None:
            engine.dispose()
    if not readable or not writable:
        return PostgresProbe(False, bool(vector), "已连接 PostgreSQL，请检查当前数据库模式的读写和建表权限。")
    if vector:
        return PostgresProbe(True, True, "PostgreSQL 可连接，pgvector 已启用。")
    return PostgresProbe(True, False, "PostgreSQL 可连接，当前未启用 pgvector。")
