"""Exercise saved model settings through real clients with only HTTP mocked."""

import asyncio
import json

import httpx
import pytest
from langchain_core.messages import AIMessage
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.db.models import Base
from app.schemas.model_providers import ProviderCreate
from app.services import model_providers
from app.services.agents.chat_agent import ChatAgent
from app.services.agents.issue_agent import IssueAgent
from app.services.llm.client import LLMClient
from app.services.rag import qa


SECRET = "sk-runtime-fixture-secret"
ENV_SECRET = "sk-environment-fixture-secret"


@pytest.fixture
def runtime_db(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'runtime.db'}")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(model_providers.db_session, "SessionLocal", sessions)
    monkeypatch.setenv("DEVHARBOR_PROVIDER_KEY_FILE", str(tmp_path / "provider.key"))
    monkeypatch.setattr(settings, "token_encryption_key", "change-me-in-local-dev")
    monkeypatch.setattr(settings, "llm_base_url", "https://environment.invalid/v1")
    monkeypatch.setattr(settings, "llm_model", "environment-model")
    monkeypatch.setattr(settings, "llm_api_key", ENV_SECRET)
    monkeypatch.setattr(settings, "rag_llm_enabled", False)
    monkeypatch.setattr(settings, "prompt_cache_enabled", True)
    monkeypatch.setattr(settings, "prompt_cache_key", "environment-cache-key")
    monkeypatch.setattr(settings, "prompt_cache_retention", "24h")
    with sessions() as db:
        yield db
    engine.dispose()


def _activate(db, *, key=SECRET, base_url="https://custom.invalid/v1", model="provider-model"):
    provider = model_providers.create_provider(
        db,
        ProviderCreate(
            name="测试供应商", base_url=base_url, api_key=key,
            models=[model], default_model=model,
        ),
    )
    model_providers.activate_model(db, provider.id, model)
    return provider


def _completion(request, content="来自供应商的回答。[1]"):
    return httpx.Response(
        200,
        request=request,
        json={
            "id": "chatcmpl-runtime", "object": "chat.completion", "created": 1,
            "model": json.loads(request.content)["model"],
            "choices": [{"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 12, "completion_tokens": 4, "total_tokens": 16},
        },
    )


def _mock_http(monkeypatch, responder=None):
    requests = []

    async def send(_client, request, **_kwargs):
        requests.append(request)
        if responder:
            return responder(request)
        payload = json.loads(request.content)
        if payload.get("stream"):
            chunk = json.dumps({"choices": [{"delta": {"content": "供应商流式回答"}}]})
            return httpx.Response(200, request=request, text=f"data: {chunk}\n\ndata: [DONE]\n\n")
        return _completion(request, '{"result":"供应商分析"}' if payload.get("response_format") else "来自供应商的回答。[1]")

    monkeypatch.setattr(httpx.AsyncClient, "send", send)
    return requests


async def _invoke_client(client, method):
    if method == "json":
        return await client.chat_json("分析资料", {"question": "你好"})
    if method == "stream":
        return "".join([chunk async for chunk in client.chat_text_stream("助手", [{"role": "user", "content": "你好"}])])
    return await client.chat_text("助手", "你好")


@pytest.mark.asyncio
@pytest.mark.parametrize("method", ["text", "json", "stream"])
async def test_llm_client_uses_saved_provider_and_omits_private_cache_options(runtime_db, monkeypatch, method):
    _activate(runtime_db)
    requests = _mock_http(monkeypatch)

    result = await _invoke_client(LLMClient(), method)

    assert result
    assert len(requests) == 1
    assert str(requests[0].url) == "https://custom.invalid/v1/chat/completions"
    assert requests[0].headers["authorization"] == f"Bearer {SECRET}"
    payload = json.loads(requests[0].content)
    assert payload["model"] == "provider-model"
    assert "prompt_cache_key" not in payload and "prompt_cache_retention" not in payload


@pytest.mark.asyncio
@pytest.mark.parametrize("key", [SECRET, None])
async def test_chat_agent_runs_real_model_with_saved_configuration(runtime_db, monkeypatch, key):
    _activate(runtime_db, key=key, base_url="http://localhost:11434/v1")
    requests = _mock_http(monkeypatch)

    agent = ChatAgent()
    result = await agent.run({"message": "你好，请简短回答。"}, {"tools": {}})

    assert result["answer"] == "来自供应商的回答。[1]"
    assert agent.model_name == "provider-model"
    assert len(requests) == 1
    request = requests[0]
    assert str(request.url) == "http://localhost:11434/v1/chat/completions"
    assert request.headers["authorization"] == f"Bearer {key or 'local-no-key'}"
    payload = json.loads(request.content)
    assert payload["model"] == "provider-model"
    assert "prompt_cache_key" not in payload and "prompt_cache_retention" not in payload
    assert "temperature" not in payload
    assert result["model_usage"][-1]["model"] == "provider-model"


@pytest.mark.asyncio
async def test_no_key_local_provider_is_used_by_llm_and_rag_despite_demo_flag(runtime_db, monkeypatch):
    _activate(runtime_db, key=None, base_url="http://127.0.0.1:11434/v1")
    requests = _mock_http(monkeypatch)

    async def retrieve(*_args, **_kwargs):
        return ([{
            "id": "doc-1", "source_id": "source-1", "source_type": "knowledge_file",
            "title": "handbook.md", "snippet": "本地供应商支持知识问答。", "score": 0.95,
        }], {"answer_gate": {"decision": "answer"}}, 1)

    monkeypatch.setattr(qa, "retrieve_knowledge", retrieve)
    result = await qa.answer_question(runtime_db, "00000000-0000-0000-0000-000000000001", "支持知识问答吗？")

    assert result["generation_mode"] == "llm"
    assert result["model"] == "provider-model"
    assert result["answer"] == "来自供应商的回答。[1]"
    assert len(requests) == 1
    assert str(requests[0].url) == "http://127.0.0.1:11434/v1/chat/completions"
    assert "authorization" not in requests[0].headers
    assert json.loads(requests[0].content)["model"] == "provider-model"


@pytest.mark.asyncio
async def test_new_clients_follow_provider_switch_while_existing_call_keeps_snapshot(runtime_db, monkeypatch):
    _activate(runtime_db)
    original = LLMClient()
    _activate(runtime_db, key="second-fixture-key", base_url="https://second.invalid/v1", model="second-model")
    requests = _mock_http(monkeypatch)

    await original.chat_text("助手", "第一个请求")
    await LLMClient().chat_text("助手", "第二个请求")

    assert [str(request.url) for request in requests] == [
        "https://custom.invalid/v1/chat/completions", "https://second.invalid/v1/chat/completions",
    ]
    assert [json.loads(request.content)["model"] for request in requests] == ["provider-model", "second-model"]
    assert [request.headers["authorization"] for request in requests] == [f"Bearer {SECRET}", "Bearer second-fixture-key"]


@pytest.mark.asyncio
async def test_issue_analysis_uses_selected_provider_output(runtime_db, monkeypatch):
    _activate(runtime_db)
    requests = _mock_http(monkeypatch, lambda request: _completion(request, '{"summary":"供应商给出的分析摘要"}'))

    result = await IssueAgent().run({"title": "登录错误", "body": "登录返回 500", "labels": ["bug"]}, {})

    assert result["summary"] == "供应商给出的分析摘要"
    assert len(requests) == 1
    assert str(requests[0].url) == "https://custom.invalid/v1/chat/completions"
    payload = json.loads(requests[0].content)
    assert payload["model"] == "provider-model"
    assert payload["response_format"] == {"type": "json_object"}


@pytest.mark.asyncio
@pytest.mark.parametrize("consumer", ["client", "agent"])
async def test_reset_restores_environment_model_credentials_and_cache_options(runtime_db, monkeypatch, consumer):
    _activate(runtime_db)
    model_providers.reset_active(runtime_db)
    requests = _mock_http(monkeypatch)

    if consumer == "client":
        await LLMClient().chat_text("助手", "你好")
    else:
        await ChatAgent().run({"message": "你好，请简短回答。"}, {"tools": {}})

    assert len(requests) == 1
    request = requests[0]
    assert str(request.url) == "https://environment.invalid/v1/chat/completions"
    assert request.headers["authorization"] == f"Bearer {ENV_SECRET}"
    payload = json.loads(request.content)
    assert payload["model"] == "environment-model"
    assert payload["prompt_cache_key"] == "environment-cache-key"
    assert payload["prompt_cache_retention"] == "24h"


@pytest.mark.asyncio
async def test_environment_without_key_preserves_offline_client_behavior(runtime_db, monkeypatch):
    monkeypatch.setattr(settings, "llm_api_key", "")
    requests = _mock_http(monkeypatch)
    client = LLMClient()

    assert await _invoke_client(client, "text") == ""
    assert await _invoke_client(client, "json") == {}
    assert await _invoke_client(client, "stream") == ""
    assert ChatAgent().model is None
    assert requests == []


@pytest.mark.asyncio
@pytest.mark.parametrize("enabled", [False, True])
async def test_environment_rag_still_respects_its_generation_flag(runtime_db, monkeypatch, enabled):
    monkeypatch.setattr(settings, "rag_llm_enabled", enabled)
    monkeypatch.setattr(qa, "search_similar_documents", lambda *_args, **_kwargs: [{
        "id": "doc-1", "source_type": "knowledge_file", "title": "handbook.md",
        "snippet": "知识问答依据检索资料生成回答。", "score": 0.95,
    }])
    requests = _mock_http(monkeypatch)

    result = await qa.answer_question(object(), "00000000-0000-0000-0000-000000000001", "知识问答如何工作？")

    assert result["generation_mode"] == ("llm" if enabled else "extractive")
    assert result["model"] == ("environment-model" if enabled else None)
    assert len(requests) == int(enabled)


@pytest.mark.asyncio
@pytest.mark.parametrize("method", ["text", "json", "stream"])
@pytest.mark.parametrize("failure", ["unauthorized", "connection"])
async def test_provider_errors_never_expose_upstream_secrets(runtime_db, monkeypatch, method, failure):
    _activate(runtime_db)

    def fail(request):
        if failure == "connection":
            raise httpx.ConnectError(f"upstream accidentally echoed {SECRET}", request=request)
        return httpx.Response(401, request=request, json={"error": {"message": f"bad key {SECRET}"}})

    _mock_http(monkeypatch, fail)
    with pytest.raises(model_providers.ModelProviderError) as error:
        await _invoke_client(LLMClient(), method)

    assert error.value.status_code == 502
    assert SECRET not in str(error.value)
    assert "模型服务" in str(error.value)


@pytest.mark.asyncio
async def test_chat_agent_wraps_sdk_errors_before_routes_can_echo_them(runtime_db, monkeypatch):
    _activate(runtime_db)
    _mock_http(monkeypatch, lambda request: httpx.Response(
        401, request=request, json={"error": {"message": f"bad key {SECRET}", "type": "invalid_api_key"}},
    ))

    with pytest.raises(model_providers.ModelProviderError) as error:
        await ChatAgent().run({"message": "你好，请简短回答。"}, {"tools": {}})

    assert error.value.status_code == 502
    assert SECRET not in str(error.value)
    assert "密钥" in str(error.value)


@pytest.mark.asyncio
async def test_rag_response_and_request_share_configuration_during_provider_switch(runtime_db, monkeypatch):
    _activate(runtime_db)
    original_resolve = model_providers.resolve_model_config

    def resolve_then_switch():
        config = original_resolve()
        _activate(runtime_db, model="switched-model", base_url="https://switched.invalid/v1")
        return config

    monkeypatch.setattr(qa, "resolve_model_config", resolve_then_switch)
    monkeypatch.setattr(qa, "search_similar_documents", lambda *_args, **_kwargs: [{
        "id": "doc-1", "source_type": "knowledge_file", "title": "handbook.md",
        "snippet": "请求期间应使用同一个模型配置。", "score": 0.95,
    }])
    requests = _mock_http(monkeypatch)

    result = await qa.answer_question(object(), "00000000-0000-0000-0000-000000000001", "如何保持一致？")

    assert original_resolve().model == "switched-model"
    assert len(requests) == 1
    assert result["model"] == json.loads(requests[0].content)["model"] == "provider-model"
    assert str(requests[0].url) == "https://custom.invalid/v1/chat/completions"


@pytest.mark.asyncio
@pytest.mark.parametrize("recover", [True, False])
async def test_chat_agent_context_overflow_retries_once_without_echoing_upstream(runtime_db, monkeypatch, recover):
    _activate(runtime_db)
    attempts = 0

    def respond(request):
        nonlocal attempts
        attempts += 1
        if attempts == 2 and recover:
            return _completion(request)
        return httpx.Response(400, request=request, json={
            "error": {"message": f"maximum context length exceeded; private details {SECRET}", "code": "context_length_exceeded"},
        })

    _mock_http(monkeypatch, respond)
    if recover:
        result = await ChatAgent().run({"message": "你好，请简短回答。"}, {"tools": {}})
        assert result["answer"] == "来自供应商的回答。[1]"
        assert result["context_diagnostics"]["reactive_overflow_retry"] is True
        assert SECRET not in json.dumps(result)
    else:
        with pytest.raises(model_providers.ModelProviderError) as error:
            await ChatAgent().run({"message": "你好，请简短回答。"}, {"tools": {}})
        assert SECRET not in str(error.value)
    assert attempts == 2


@pytest.mark.asyncio
async def test_chat_agent_does_not_follow_provider_redirects(runtime_db, monkeypatch):
    _activate(runtime_db)
    requests = []

    async def redirected(_transport, request):
        requests.append(request)
        return httpx.Response(307, request=request, headers={"Location": "https://unexpected.invalid/v1/chat/completions"})

    # Mock below AsyncClient.send so the real HTTP redirect behavior is exercised.
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", redirected)
    with pytest.raises(model_providers.ModelProviderError):
        await ChatAgent().run({"message": "你好，请简短回答。"}, {"tools": {}})

    assert len(requests) == 1
    assert requests[0].url.host == "custom.invalid"


@pytest.mark.asyncio
@pytest.mark.parametrize("outcome", ["success", "error", "cancel"])
async def test_owned_model_client_closes_on_every_exit_and_agent_can_be_reused(runtime_db, monkeypatch, outcome):
    _activate(runtime_db)
    clients = []
    started = asyncio.Event()
    first_call = True

    async def send(client, request, **_kwargs):
        nonlocal first_call
        assert not client.is_closed
        clients.append(client)
        if first_call:
            first_call = False
            if outcome == "error":
                return httpx.Response(401, request=request, json={"error": {"message": "unauthorized"}})
            if outcome == "cancel":
                started.set()
                await asyncio.Event().wait()
        return _completion(request)

    monkeypatch.setattr(httpx.AsyncClient, "send", send)
    agent = ChatAgent()
    task = asyncio.create_task(agent.run({"message": "你好，请简短回答。"}, {"tools": {}}))
    if outcome == "cancel":
        await asyncio.wait_for(started.wait(), timeout=5)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    elif outcome == "error":
        with pytest.raises(model_providers.ModelProviderError):
            await task
    else:
        assert (await task)["answer"] == "来自供应商的回答。[1]"
    assert len(clients) == 1 and clients[0].is_closed

    result = await agent.run({"message": "再次回答。"}, {"tools": {}})

    assert result["answer"] == "来自供应商的回答。[1]"
    assert len(clients) == 2 and clients[1].is_closed
    assert clients[0] is not clients[1]


@pytest.mark.asyncio
async def test_agent_does_not_close_injected_model_and_can_reuse_it(runtime_db):
    _activate(runtime_db)

    class InjectedModel:
        model_name = "injected-model"

        def bind_tools(self, _tools):
            return self

        async def ainvoke(self, _messages):
            return AIMessage(content="注入模型回答")

        async def aclose(self):
            raise AssertionError("The caller owns an injected model")

    injected = InjectedModel()
    agent = ChatAgent(model=injected)
    for _ in range(2):
        assert (await agent.run({"message": "你好。"}, {"tools": {}}))["answer"] == "注入模型回答"
    assert agent.model is injected
