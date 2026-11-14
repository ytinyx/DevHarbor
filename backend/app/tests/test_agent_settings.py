"""Agent management changes real business execution, without external model calls."""

from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.routes import agent_settings, chat, ci, issues, pull_requests, reports
from app.db.models import Base, Repository
from app.db.session import get_db
from app.schemas.workflow import WorkflowClaim, WorkflowSpec, WorkflowTask, WorkflowTaskResult
from app.services import agent_settings as service
from app.services.agents.planner_agent import PlannerAgent
from app.services.agents.workflow_orchestrator import WorkflowOrchestrator

PREFIX = "/api/settings/agents"


@pytest.fixture
def agent_app(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'agents.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    app = FastAPI()
    app.include_router(agent_settings.router, prefix=PREFIX)
    for module in (ci, issues, pull_requests):
        app.include_router(module.router, prefix="/api")
    app.include_router(reports.router, prefix="/api/reports")
    app.include_router(chat.router, prefix="/api/chat")

    @app.exception_handler(service.AgentSettingsError)
    async def settings_error(_request, exc):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})

    def database():
        with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = database
    with TestClient(app) as client:
        yield client, sessions
    engine.dispose()


def test_catalog_counts_roles_not_function_aliases_and_marks_unwired_role(agent_app):
    client, _ = agent_app
    result = client.get(PREFIX).json()
    roles = {item["id"]: item for item in result["agents"]}
    assert result["total"] == len(roles) == 12
    assert "repo_health_agent" not in roles and "rag_context_agent" not in roles
    assert roles["github_retrieval_agent"]["availability"] == "not_integrated"
    assert roles["github_retrieval_agent"]["enabled"] is False
    assert roles["workflow_orchestrator"]["implementation"] == "workflow"
    assert len([item for item in roles.values() if item["configurable"]]) == 5


def test_toggle_persists_across_sessions_and_is_read_fresh(agent_app):
    client, sessions = agent_app
    with sessions() as old_session:
        assert "report_agent" not in service.disabled_agent_ids(old_session)
        response = client.patch(f"{PREFIX}/report_agent", json={"enabled": False})
        assert response.status_code == 200 and response.json()["enabled"] is False
        assert "report_agent" in service.disabled_agent_ids(old_session)
    with sessions() as fresh_session:
        assert "report_agent" in service.disabled_agent_ids(fresh_session)
    assert client.patch(f"{PREFIX}/report_agent", json={"enabled": True}).status_code == 200
    assert next(role for role in client.get(PREFIX).json()["agents"] if role["id"] == "report_agent")["enabled"] is True


@pytest.mark.parametrize("agent_id", ["chat_agent", "planner_agent", "workflow_orchestrator", "observer_agent", "synthesis_agent", "safety_agent", "github_retrieval_agent"])
def test_required_and_unintegrated_roles_cannot_be_changed(agent_app, agent_id):
    client, _ = agent_app
    response = client.patch(f"{PREFIX}/{agent_id}", json={"enabled": False})
    assert response.status_code == 409
    assert "不能停用" in response.json()["detail"] or "尚未接入" in response.json()["detail"]


def test_unknown_roles_and_unexpected_edit_fields_are_rejected(agent_app):
    client, _ = agent_app
    assert client.patch(f"{PREFIX}/made_up_agent", json={"enabled": True}).status_code == 404
    assert client.patch(f"{PREFIX}/report_agent", json={"enabled": "false"}).status_code == 422
    assert client.patch(f"{PREFIX}/report_agent", json={"enabled": False, "prompt": "override"}).status_code == 422


@pytest.mark.parametrize("agent_id,path", [
    ("issue_analyst_agent", "/api/issues/{id}/analyze"),
    ("issue_analyst_agent", "/api/issues/{id}/analyze/stream"),
    ("pr_review_agent", "/api/pull-requests/{id}/analyze"),
    ("pr_review_agent", "/api/pull-requests/{id}/analyze/stream"),
    ("ci_debug_agent", "/api/workflow-runs/{id}/analyze"),
    ("ci_debug_agent", "/api/workflow-runs/{id}/analyze/stream"),
])
def test_disabled_specialist_routes_reject_before_stream_or_data_work(agent_app, agent_id, path):
    client, _ = agent_app
    client.patch(f"{PREFIX}/{agent_id}", json={"enabled": False})
    response = client.post(path.format(id=uuid4()))
    assert response.status_code == 409
    assert response.headers["content-type"].startswith("application/json")
    assert "已停用" in response.json()["detail"]


@pytest.mark.parametrize("agent_id,path,payload", [
    ("report_agent", "/api/reports/weekly", {"repo_id": str(uuid4()), "start_date": "2026-11-01", "end_date": "2026-11-10"}),
    ("recommendation_agent", "/api/chat/recommendations", {"repo_id": str(uuid4())}),
])
def test_optional_support_routes_respect_disabled_state(agent_app, agent_id, path, payload):
    client, _ = agent_app
    client.patch(f"{PREFIX}/{agent_id}", json={"enabled": False})
    response = client.post(path, json=payload)
    assert response.status_code == 409 and "已停用" in response.json()["detail"]


@pytest.mark.asyncio
@pytest.mark.parametrize("agent_id,tool", [
    ("issue_analyst_agent", "issue_agent.analyze_issue"),
    ("pr_review_agent", "pr_review_agent.analyze_pr"),
    ("ci_debug_agent", "ci_debug_agent.analyze_workflow_run"),
    ("report_agent", "report_agent.generate_weekly_report"),
])
async def test_chat_tools_cannot_bypass_disabled_roles(agent_app, agent_id, tool):
    _, sessions = agent_app
    with sessions() as db:
        tools = chat._build_conversation_tools(None, None, db)
        service.update_agent(db, agent_id, False)
        with pytest.raises(service.AgentSettingsError, match="已停用"):
            await tools[tool]({}, {})


@pytest.mark.asyncio
@pytest.mark.parametrize("agent_id,task_type,target_type", [
    ("issue_analyst_agent", "issue_analysis", "issue"),
    ("pr_review_agent", "pr_review", "pull_request"),
    ("ci_debug_agent", "ci_debug", "workflow_run"),
])
async def test_previously_built_plan_rechecks_disabled_role_and_blocks_dependants(agent_app, agent_id, task_type, target_type):
    _, sessions = agent_app
    with sessions() as db:
        repo = Repository(owner="test", name="guards", full_name="test/guards")
        db.add(repo)
        db.commit()
        context, runners = chat._build_engineering_workflow_runtime(repo, db, "检查项目", {})
        spec = WorkflowSpec(goal="联合检查", trigger_message="联合检查", tasks=[
            WorkflowTask(id="specialist", agent_name=agent_id, task_type=task_type, objective="检查", claim=WorkflowClaim(target_type=target_type)),
            WorkflowTask(id="dependent", agent_name="repo_health_agent", task_type="repo_health", objective="后续处理", dependencies=["specialist"], claim=WorkflowClaim(target_type="repository")),
        ])
        service.update_agent(db, agent_id, False)
        result = await WorkflowOrchestrator(runners).run_spec(spec, context, allow_replan=False)
        assert [item["status"] for item in result["task_results"]] == ["skipped", "skipped"]
        assert result["task_results"][0]["output"]["error_kind"] == "agent_disabled"
        assert "已停用" in result["task_results"][0]["summary"]
        assert "覆盖不完整" in result["final_answer"]
        assert result["metrics"]["success_count"] == 0


@pytest.mark.asyncio
async def test_new_plan_omits_disabled_analysis_and_does_not_claim_full_review():
    context = {"has_repo": True, "has_issue": True, "has_pr": True, "has_ci_run": True, "has_failed_ci": True,
               "disabled_agent_ids": ["issue_analyst_agent", "pr_review_agent", "ci_debug_agent"]}
    plan = await PlannerAgent().run({"message": "联合检查是否可以合并"}, context)
    assert [task["task_type"] for task in plan["tasks"]] == ["repo_health"]

    async def repo_summary(task, _spec, _context):
        return WorkflowTaskResult(task_id=task.id, agent_name=task.agent_name, task_type=task.task_type, status="success", confidence=.9)

    result = await WorkflowOrchestrator({"repo_health": repo_summary}).run_spec(plan, context)
    assert result["metrics"]["replan_count"] == 0
    assert all(task["task_type"] == "repo_health" for task in result["spec"]["tasks"])
    assert any(finding["finding_type"] == "agent_disabled" for finding in result["observation"]["findings"])
    assert "不能确认可合并或发布" in result["final_answer"]


@pytest.mark.asyncio
async def test_disabled_role_is_not_retried_during_replanning():
    calls = 0

    async def disabled_runner(task, _spec, _context):
        nonlocal calls
        calls += 1
        raise service.AgentSettingsError("“代码审查”已停用。")

    task = WorkflowTask(id="pr", agent_name="pr_review_agent", task_type="pr_review", objective="审查", claim=WorkflowClaim(target_type="pull_request"))
    spec = WorkflowSpec(goal="审查", trigger_message="审查", tasks=[task])
    orchestrator = WorkflowOrchestrator({"pr_review": disabled_runner})
    first = await orchestrator._run_task_graph(spec, {})
    second = await orchestrator._run_task_graph(spec, {}, previous_results=first)
    assert calls == 1 and not second
