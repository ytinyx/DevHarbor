"""The packaged sidecar uses a private port, private data and a bounded lifecycle."""

import base64
import json
import os
from pathlib import Path
import queue
import socket
import subprocess
import sys
import threading

import httpx
import pytest
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

import desktop
from app.core.desktop_security import DESKTOP_ORIGINS, DesktopTokenMiddleware


TOKEN = "desktop-unit-test-only-token-" + "a" * 32
ENTRY = Path(__file__).resolve().parents[2] / "desktop.py"


def _sidecar_command():
    """Run this same lifecycle suite against a built artifact when requested."""
    executable = os.environ.get("DEVHARBOR_TEST_SIDECAR_EXE")
    if executable:
        path = Path(executable).resolve(strict=True)
        return [str(path)]
    return [sys.executable, str(ENTRY)]


def test_data_and_secret_configuration_is_isolated_and_keys_survive_restart(tmp_path, monkeypatch):
    outside = tmp_path / "do-not-touch"
    data_dir = tmp_path / "my desktop data"
    environment = {
        "DEVHARBOR_DATA_DIR": str(data_dir), "DEVHARBOR_DESKTOP_TOKEN": TOKEN,
        "DATABASE_URL": "sqlite:///" + str(outside / "developer.db"),
        "REPO_CHECKOUT_DIR": str(outside), "UPLOAD_DIR": str(outside),
        "TOKEN_ENCRYPTION_KEY": "change-me-in-local-dev",
        "DEVHARBOR_PROVIDER_KEY_FILE": str(outside / "old.key"),
        **{name: "inherited-secret-must-not-be-used" for name in desktop._SECRET_ENV_NAMES},
    }
    monkeypatch.setattr(os, "environ", environment)
    result_dir, result_port = desktop.configure_environment()
    assert result_dir == data_dir and result_port == 0
    assert not outside.exists()
    assert all(environment[name] == "" for name in desktop._SECRET_ENV_NAMES)
    assert environment["DATABASE_URL"] == "sqlite:///" + (data_dir / "devharbor.db").as_posix()
    assert environment["REPO_CHECKOUT_DIR"] == str(data_dir / "repos")
    assert environment["UPLOAD_DIR"] == str(data_dir / "uploads")
    assert environment["EMBEDDING_PROVIDER"] == "disabled"
    assert environment["MILVUS_ENABLED"] == "false" and environment["AUTO_SYNC_ENABLED"] == "false"
    assert environment["HF_HUB_OFFLINE"] == "1"
    github_key = environment["TOKEN_ENCRYPTION_KEY"]
    provider_key = Path(environment["DEVHARBOR_PROVIDER_KEY_FILE"]).read_text()
    assert len(base64.urlsafe_b64decode(github_key)) == len(base64.urlsafe_b64decode(provider_key)) == 32
    assert github_key != provider_key
    desktop.configure_environment()
    assert environment["TOKEN_ENCRYPTION_KEY"] == github_key
    assert Path(environment["DEVHARBOR_PROVIDER_KEY_FILE"]).read_text() == provider_key


@pytest.mark.parametrize("patch", [
    {"DEVHARBOR_DATA_DIR": "relative"}, {"DEVHARBOR_DESKTOP_TOKEN": "short"},
    {"DEVHARBOR_DESKTOP_PORT": "-1"}, {"DEVHARBOR_DESKTOP_PORT": "65536"},
    {"DEVHARBOR_DESKTOP_PORT": "not-a-port"},
])
def test_invalid_launch_configuration_is_rejected_before_writing(tmp_path, monkeypatch, patch):
    environment = {"DEVHARBOR_DATA_DIR": str(tmp_path / "data"), "DEVHARBOR_DESKTOP_TOKEN": TOKEN, **patch}
    monkeypatch.setattr(os, "environ", environment)
    with pytest.raises(ValueError):
        desktop.configure_environment()
    assert not (tmp_path / "data").exists()


def test_corrupt_saved_key_is_not_silently_regenerated(tmp_path):
    key = tmp_path / "secret.key"
    key.write_text("corrupt")
    with pytest.raises(RuntimeError, match="restore"):
        desktop._persistent_secret(key)
    assert key.read_text() == "corrupt"


def test_token_required_even_on_health_and_cors_is_limited():
    app = FastAPI()

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    app.add_middleware(DesktopTokenMiddleware, token=TOKEN)
    app.add_middleware(CORSMiddleware, allow_origins=DESKTOP_ORIGINS, allow_methods=["*"], allow_headers=["*"])
    with TestClient(app) as client:
        assert client.get("/health").status_code == 401
        assert client.get("/health", headers={"X-DevHarbor-Token": "wrong"}).status_code == 401
        assert client.get("/health", headers=[("X-DevHarbor-Token", TOKEN), ("X-DevHarbor-Token", TOKEN)]).status_code == 401
        assert client.get("/health", headers={"X-DevHarbor-Token": TOKEN}).json() == {"status": "ok"}
        for origin in DESKTOP_ORIGINS:
            response = client.get("/health", headers={"X-DevHarbor-Token": TOKEN, "Origin": origin})
            assert response.headers["access-control-allow-origin"] == origin
            preflight = client.options("/health", headers={"Origin": origin, "Access-Control-Request-Method": "GET", "Access-Control-Request-Headers": "x-devharbor-token"})
            assert preflight.status_code == 200
        for origin in ("https://example.test", "http://localhost:3000", "app://other"):
            response = client.get("/health", headers={"X-DevHarbor-Token": TOKEN, "Origin": origin})
            assert "access-control-allow-origin" not in response.headers
            assert client.options("/health", headers={"Origin": origin, "Access-Control-Request-Method": "GET"}).status_code == 400


def _start_sidecar(tmp_path, *, port=0):
    data_dir = tmp_path / "desktop-state"
    launch_dir = tmp_path / "launch"
    launch_dir.mkdir()
    (tmp_path / ".env").write_text("LLM_API_KEY=must-not-read-parent-dotenv\nGITHUB_TOKEN=parent-dotenv-token\n", encoding="utf-8")
    (launch_dir / ".env").write_text("LLM_API_KEY=must-not-read-launch-dotenv\n", encoding="utf-8")
    environment = {**os.environ, "DEVHARBOR_DESKTOP": "1", "DEVHARBOR_DESKTOP_TOKEN": TOKEN,
                   "DEVHARBOR_DATA_DIR": str(data_dir), "DEVHARBOR_DESKTOP_PORT": str(port),
                   "LLM_API_KEY": "must-not-inherit-model-key", "GITHUB_TOKEN": "must-not-inherit-github-token"}
    process = subprocess.Popen(
        _sidecar_command(), cwd=launch_dir, env=environment,
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding="utf-8", creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    lines = queue.Queue()
    threading.Thread(target=lambda: lines.put(process.stdout.readline()), daemon=True).start()
    try:
        line = lines.get(timeout=50)
        if not line:
            raise AssertionError("Sidecar exited before readiness: " + process.stderr.read())
        ready = json.loads(line)
        assert ready["type"] == "ready" and isinstance(ready["port"], int) and ready["port"] > 0
        assert set(ready) == {"type", "port"}
        return process, ready["port"], data_dir
    except BaseException:
        process.kill()
        process.wait(timeout=10)
        raise


@pytest.mark.parametrize("shutdown", ["command", "eof"])
def test_real_sidecar_readiness_authentication_isolation_and_shutdown(tmp_path, shutdown):
    process, port, data_dir = _start_sidecar(tmp_path)
    try:
        with httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=15, trust_env=False) as client:
            assert client.get("/health").status_code == 401
            headers = {"X-DevHarbor-Token": TOKEN}
            assert client.get("/health", headers=headers).json()["status"] == "ok"
            providers = client.get("/api/settings/model-providers", headers=headers).json()
            assert providers["environment"]["configured"] is False
            assert providers["providers"] == []
            catalog = client.get("/api/settings/agents", headers=headers).json()
            assert catalog["total"] == 12
            # This starts the actual MCP child through the HTTP sidecar. In a
            # frozen build it must relaunch the bundled executable, not Python.
            mcp_response = client.get("/api/skills/mcp-status", headers=headers)
            assert mcp_response.status_code == 200, mcp_response.text
            mcp = mcp_response.json()
            assert mcp["status"] == "online" and mcp["server_name"] == "devharbor-memory-mcp"
            assert len(mcp["tools"]) == 3
            skills = client.get("/api/skills", headers=headers).json()
            assert skills["skills"], "Bundled skill manifests must be available"
        assert (data_dir / "devharbor.db").exists()
        assert (data_dir / "secrets" / "github-token.key").exists()
        assert (data_dir / "secrets" / "model-providers.key").exists()
        if shutdown == "command":
            process.stdin.write('{"type":"shutdown"}\n')
            process.stdin.flush()
        else:
            process.stdin.close()
        assert process.wait(timeout=15) == 0
        assert not process.stdout.read().strip(), "Only the readiness protocol belongs on stdout"
        with socket.socket() as check:
            assert check.connect_ex(("127.0.0.1", port)) != 0
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=10)


def test_frozen_mcp_uses_the_sidecar_internal_mode(monkeypatch):
    from app.services.mcp_client import StdioMcpClient
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    assert StdioMcpClient().args == ["--mcp-memory-server"]
    assert StdioMcpClient(command="custom-python", args=["custom-server.py"]).args == ["custom-server.py"]


def test_explicit_port_is_honored(tmp_path):
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        requested_port = reservation.getsockname()[1]
    process, actual_port, _ = _start_sidecar(tmp_path, port=requested_port)
    try:
        assert actual_port == requested_port
        process.stdin.close()
        assert process.wait(timeout=15) == 0
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=10)


def test_early_parent_exit_does_not_leave_an_orphan_service(tmp_path):
    environment = {**os.environ, "DEVHARBOR_DESKTOP": "1", "DEVHARBOR_DESKTOP_TOKEN": TOKEN,
                   "DEVHARBOR_DATA_DIR": str(tmp_path / "state"), "DEVHARBOR_DESKTOP_PORT": "0"}
    process = subprocess.Popen(
        _sidecar_command(), cwd=tmp_path, env=environment,
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding="utf-8", creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    try:
        process.stdin.close()
        assert process.wait(timeout=30) == 0
        assert not process.stdout.read().strip()
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=10)


def test_desktop_without_a_project_does_not_read_installation_sources(monkeypatch):
    from app.api.routes.chat import PROJECT_ROOT, _workspace_root
    from app.core.config import settings
    monkeypatch.setattr(settings, "desktop_mode", True)
    with pytest.raises(ValueError, match="先连接或选择"):
        _workspace_root(None)
    monkeypatch.setattr(settings, "desktop_mode", False)
    assert _workspace_root(None) == PROJECT_ROOT


def test_internal_mcp_mode_uses_json_rpc_instead_of_starting_http(tmp_path):
    environment = {**os.environ, "DEVHARBOR_DESKTOP": "1", "DEVHARBOR_DESKTOP_TOKEN": TOKEN,
                   "DEVHARBOR_DATA_DIR": str(tmp_path / "mcp-state"), "DEVHARBOR_DESKTOP_PORT": "0"}
    messages = '\n'.join([
        json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}),
        json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}),
        "",
    ])
    result = subprocess.run(
        [*_sidecar_command(), "--mcp-memory-server"], cwd=tmp_path, env=environment,
        input=messages, capture_output=True, text=True, encoding="utf-8", timeout=30,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    assert result.returncode == 0, result.stderr
    responses = [json.loads(line) for line in result.stdout.splitlines()]
    assert [item["id"] for item in responses] == [1, 2]
    assert responses[0]["result"]["serverInfo"]["name"] == "devharbor-memory-mcp"
    assert responses[1]["result"]["tools"]
