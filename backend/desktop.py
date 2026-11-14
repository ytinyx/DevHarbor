"""Electron's private, loopback-only Python sidecar.

Run with piped stdin/stdout. Stdout is a JSON-line control channel; logs go to
stderr. A successful ASGI startup emits {"type":"ready","port":actual_port}.
Closing stdin or sending {"type":"shutdown"} shuts the server down.
"""

from __future__ import annotations

import asyncio
import base64
from contextlib import redirect_stdout
import json
import os
from pathlib import Path
import secrets
import sys
import threading
from typing import TextIO

from desktop_database import (
    DesktopDatabaseError, INVALID_PROFILE_WARNING, LOCAL_FALLBACK_WARNING,
    normalize_postgres_url, postgres_data_dir, read_postgres_url, read_profile,
)


_SECRET_ENV_NAMES = (
    "GITHUB_TOKEN", "GITHUB_WEBHOOK_SECRET", "LLM_API_KEY", "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY", "EMBEDDING_API_KEY", "DASHSCOPE_API_KEY", "RERANK_API_KEY",
    "RAGAS_JUDGE_API_KEY", "MILVUS_TOKEN", "FEISHU_FEEDBACK_WEBHOOK_URL",
    "LANGSMITH_API_KEY", "LANGCHAIN_API_KEY", "HUGGING_FACE_HUB_TOKEN", "HF_TOKEN",
)


def _persistent_secret(path: Path) -> str:
    """Create once, never silently replace a key which protects saved data."""
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        pass
    else:
        with os.fdopen(fd, "w", encoding="ascii") as stream:
            stream.write(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode("ascii"))
            stream.flush()
            os.fsync(stream.fileno())
    try:
        value = path.read_text(encoding="ascii").strip()
        if len(base64.b64decode(value.encode("ascii"), altchars=b"-_", validate=True)) != 32:
            raise ValueError("invalid length")
    except (OSError, ValueError, UnicodeError) as exc:
        raise RuntimeError(f"Saved desktop encryption key is invalid: {path.name}; restore it instead of replacing it.") from exc
    return value


def _database_for_launch(data_dir: Path, local_database: bool, mcp_server: bool) -> tuple[str, str, str]:
    sqlite_url = "sqlite:///" + (data_dir / "devharbor.db").as_posix()
    try:
        if mcp_server:
            # The parent sidecar's active database can differ from the saved choice.
            if os.environ.get("DEVHARBOR_DESKTOP_DATABASE_MODE") == "postgresql":
                return "postgresql", normalize_postgres_url(os.environ.get("DATABASE_URL", "")), ""
            return "sqlite", sqlite_url, ""
        profile = read_profile(data_dir)
        if profile.mode == "postgresql":
            if local_database:
                return "sqlite", sqlite_url, LOCAL_FALLBACK_WARNING
            return "postgresql", read_postgres_url(data_dir, profile), ""
    except DesktopDatabaseError:
        if mcp_server:
            raise
        return "sqlite", sqlite_url, INVALID_PROFILE_WARNING
    return "sqlite", sqlite_url, ""


def configure_environment(*, local_database: bool = False, mcp_server: bool = False) -> tuple[Path, int]:
    """Must run before importing any app module or its Settings singleton."""
    raw_data_dir = os.environ.get("DEVHARBOR_DATA_DIR", "")
    if not raw_data_dir or not Path(raw_data_dir).is_absolute():
        raise ValueError("DEVHARBOR_DATA_DIR must be an absolute path.")
    data_dir = Path(raw_data_dir).resolve()
    token = os.environ.get("DEVHARBOR_DESKTOP_TOKEN", "")
    if len(token.encode("utf-8")) < 32:
        raise ValueError("DEVHARBOR_DESKTOP_TOKEN must contain at least 32 bytes of randomness.")
    try:
        port = int(os.environ.get("DEVHARBOR_DESKTOP_PORT", "0"))
    except ValueError as exc:
        raise ValueError("DEVHARBOR_DESKTOP_PORT must be an integer between 0 and 65535.") from exc
    if not 0 <= port <= 65535:
        raise ValueError("DEVHARBOR_DESKTOP_PORT must be an integer between 0 and 65535.")

    data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    encryption_key = _persistent_secret(data_dir / "secrets" / "github-token.key")
    provider_key_path = data_dir / "secrets" / "model-providers.key"
    _persistent_secret(provider_key_path)
    database_mode, database_url, database_warning = _database_for_launch(data_dir, local_database, mcp_server)
    database_data_dir = postgres_data_dir(data_dir, database_url) if database_mode == "postgresql" else data_dir
    for directory in (database_data_dir / "repos", database_data_dir / "uploads", data_dir / "cache"):
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)

    for name in _SECRET_ENV_NAMES:
        os.environ[name] = ""
    # libpq otherwise consults inherited credentials, service files and host overrides.
    for name in list(os.environ):
        if name.startswith("PG"):
            del os.environ[name]
    # Desktop-owned settings deliberately override inherited development values.
    os.environ.update({
        "DEVHARBOR_DESKTOP": "1",
        "DEVHARBOR_DATA_DIR": str(data_dir),
        "DEVHARBOR_PROVIDER_KEY_FILE": str(provider_key_path),
        "DEVHARBOR_DESKTOP_DATABASE_MODE": database_mode,
        "DEVHARBOR_DESKTOP_DATABASE_WARNING": database_warning,
        "APP_ENV": "desktop", "API_HOST": "127.0.0.1", "API_PORT": str(port),
        "DATABASE_URL": database_url,
        "REPO_CHECKOUT_DIR": str(database_data_dir / "repos"), "UPLOAD_DIR": str(database_data_dir / "uploads"),
        "TOKEN_ENCRYPTION_KEY": encryption_key,
        "CORS_ORIGINS": "app://localhost,http://127.0.0.1:5174,http://localhost:5174",
        "AUTO_SYNC_ENABLED": "false", "DEMO_MODE": "false", "MILVUS_ENABLED": "false",
        "VECTOR_BACKEND": "milvus",
        "RAGAS_ENABLED": "false", "RAG_LLM_ENABLED": "false",
        "EMBEDDING_PROVIDER": "disabled", "EMBEDDING_MODEL": "disabled", "EMBEDDING_DIMENSIONS": "128",
        "EMBEDDING_BASE_URL": "", "RERANK_BASE_URL": "", "RAGAS_JUDGE_BASE_URL": "",
        "LLM_BASE_URL": "https://api.deepseek.com", "GITHUB_API_BASE_URL": "https://api.github.com",
        "LANGSMITH_TRACING": "false", "LANGCHAIN_TRACING_V2": "false", "RAGAS_DO_NOT_TRACK": "true",
        "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "HF_HUB_DISABLE_TELEMETRY": "1",
        "HF_HOME": str(data_dir / "cache" / "huggingface"),
        "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1",
    })
    return data_dir, port


def _read_control(stream: TextIO, request_stop) -> None:
    """A daemon reader avoids keeping Python alive on a still-open stdin pipe."""
    try:
        for line in stream:
            try:
                command = json.loads(line)
            except (ValueError, UnicodeError):
                continue
            if isinstance(command, dict) and command.get("type") == "shutdown":
                break
    except (OSError, ValueError):
        pass
    finally:
        request_stop()


async def serve(port: int, output: TextIO, control: TextIO) -> None:
    import uvicorn

    using_postgres = os.environ.get("DEVHARBOR_DESKTOP_DATABASE_MODE") == "postgresql"
    if using_postgres:
        try:
            import psycopg
        except ImportError:
            _write_control(output, {"type": "database_unavailable"})
            raise RuntimeError("PostgreSQL 驱动不可用。") from None
    from app.main import app

    if using_postgres:
        # Settings and the engine hold the active DSN. Only the internal MCP
        # launcher passes it explicitly to its child; unrelated tools do not inherit it.
        os.environ.pop("DATABASE_URL", None)

    stop_requested = threading.Event()
    loop = asyncio.get_running_loop()

    class DesktopServer(uvicorn.Server):
        async def startup(self, sockets=None):
            await super().startup(sockets=sockets)
            if not self.started:
                if getattr(app.state, "desktop_database_unavailable", False) and not stop_requested.is_set():
                    _write_control(output, {"type": "database_unavailable"})
                return
            if stop_requested.is_set():
                self.should_exit = True
                await self.shutdown(sockets=sockets)
                return
            actual_port = self.servers[0].sockets[0].getsockname()[1]
            try:
                _write_control(output, {"type": "ready", "port": actual_port})
            except (BrokenPipeError, OSError):
                self.should_exit = True
                await self.shutdown(sockets=sockets)

    server = DesktopServer(uvicorn.Config(
        app, host="127.0.0.1", port=port, loop="asyncio", http="h11", ws="none",
        lifespan="on", workers=1, reload=False, access_log=False, use_colors=False,
        timeout_graceful_shutdown=8,
    ))

    def request_stop() -> None:
        stop_requested.set()
        def signal_server() -> None:
            # startup handles an early EOF and runs lifespan shutdown itself.
            if server.started:
                server.should_exit = True
        try:
            loop.call_soon_threadsafe(signal_server)
        except RuntimeError:
            pass  # The event loop already exited after a startup failure.

    threading.Thread(target=_read_control, args=(control, request_stop), daemon=True, name="desktop-control").start()
    await server.serve()
    if not server.started and not stop_requested.is_set():
        raise RuntimeError("Desktop backend did not complete startup.")


def _write_control(output: TextIO, message: dict) -> None:
    output.write(json.dumps(message, separators=(",", ":")) + "\n")
    output.flush()


def main() -> int:
    # PyInstaller may create worker processes; handle its private bootstrap first.
    if getattr(sys, "frozen", False):
        import multiprocessing
        multiprocessing.freeze_support()
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    output, control = sys.stdout, sys.stdin
    try:
        mcp_server = "--mcp-memory-server" in sys.argv[1:]
        configure_environment(local_database="--local-database" in sys.argv[1:], mcp_server=mcp_server)
        if mcp_server:
            with redirect_stdout(sys.stderr):
                from app.mcp.memory_server import main as memory_main
            if os.environ.get("DEVHARBOR_DESKTOP_DATABASE_MODE") == "postgresql":
                os.environ.pop("DATABASE_URL", None)
            asyncio.run(memory_main())
            return 0
        if output is None or control is None:
            raise RuntimeError("Desktop sidecar requires piped stdin and stdout.")
        # Keep dependency prints off the JSON control channel, including imports.
        sys.stdout = sys.stderr
        port = int(os.environ["API_PORT"])
        asyncio.run(serve(port, output, control))
        return 0
    except KeyboardInterrupt:
        return 0
    except Exception as exc:
        print(f"Desktop backend failed: {exc}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
