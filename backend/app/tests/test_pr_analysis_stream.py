import asyncio
import threading
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI
from fastapi.responses import StreamingResponse

from app.api.routes import pull_requests


@pytest.fixture
def review_stubs(monkeypatch):
    pr = SimpleNamespace(id=uuid4(), number=8)
    db = MagicMock()
    db.query.return_value.options.return_value.filter.return_value.one_or_none.return_value = pr
    agent = SimpleNamespace(
        llm=SimpleNamespace(model="test-model"),
        run=AsyncMock(return_value={"merge_recommendation": "暂缓"}),
    )
    counts = dict(files=2, code=0, documents=0, issues=3, conversation=0, comments=1, failed_ci=1)

    async def reasoning(*args):
        yield "根据已保存的 PR 和 CI 资料审查。"

    monkeypatch.setattr(pull_requests, "PRReviewAgent", lambda: agent)
    monkeypatch.setattr(pull_requests, "_pr_payload", lambda pr: {})
    monkeypatch.setattr(pull_requests, "_prepare_pr_snapshot_context", lambda *args, **kwargs: {"status": "skipped"})
    monkeypatch.setattr(pull_requests, "_build_pr_analysis_context", lambda *args: ("query", {}, counts))
    monkeypatch.setattr(pull_requests, "_augment_pr_context_with_snapshot", lambda *args: None)
    monkeypatch.setattr(pull_requests, "_stream_public_reasoning", reasoning)
    monkeypatch.setattr(pull_requests, "_persist_pr_analysis", lambda *args: SimpleNamespace(id=uuid4()))
    return pr, db


@pytest.mark.asyncio
@pytest.mark.parametrize("stage", [
    "_prepare_pr_snapshot_context",
    "_build_pr_analysis_context",
    "_augment_pr_context_with_snapshot",
])
async def test_pr_stream_keeps_backend_responsive_during_blocking_preparation(monkeypatch, review_stubs, stage):
    pr, db = review_stubs
    entered = threading.Event()
    release = threading.Event()
    timed_out = threading.Event()
    original = getattr(pull_requests, stage)

    def blocking_stage(*args, **kwargs):
        entered.set()
        if not release.wait(timeout=2):
            timed_out.set()
        return original(*args, **kwargs)

    monkeypatch.setattr(pull_requests, stage, blocking_stage)
    app = FastAPI()

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.post("/analyze")
    async def analyze():
        return StreamingResponse(pull_requests._pr_analysis_sse(pr.id, None, db), media_type="text/event-stream")

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        request = asyncio.create_task(client.post("/analyze"))
        try:
            assert await asyncio.to_thread(entered.wait, 1)
            response = await asyncio.wait_for(client.get("/health"), timeout=0.5)
            assert response.json() == {"status": "ok"}
            assert not timed_out.is_set(), "PR preparation blocked the server event loop"
            assert not request.done(), "The health response must arrive while preparation is still running"
        finally:
            release.set()
            result = await asyncio.wait_for(request, timeout=5)
        assert "event: final" in result.text
        assert "event: error" not in result.text


@pytest.mark.asyncio
async def test_pr_stream_reports_model_initialization_error_after_plan(monkeypatch, review_stubs):
    pr, db = review_stubs

    def invalid_model():
        raise RuntimeError("默认模型配置无效")

    monkeypatch.setattr(pull_requests, "PRReviewAgent", invalid_model)
    events = [event async for event in pull_requests._pr_analysis_sse(pr.id, None, db)]

    assert events[0].startswith("event: trace\n")
    assert "制定 Review 计划" in events[0]
    assert events[-1].startswith("event: error\n")
    assert "默认模型配置无效" in events[-1]
    db.rollback.assert_called_once()
