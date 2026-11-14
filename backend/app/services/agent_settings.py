"""The fixed role catalog and persisted availability of optional business agents.

This is not a plugin registry: task labels such as repo_health_agent and
rag_context_agent refer to workflow functions, not additional agent classes.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AgentSetting
from app.schemas.agent_settings import AgentDescriptor, AgentListResponse


class AgentSettingsError(Exception):
    def __init__(self, message: str, status_code: int = 409):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _role(id, name, description, group, implementation, capabilities, used_in, *, required=False, integrated=True, note=""):
    return AgentDescriptor(
        id=id, name=name, description=description, group=group, implementation=implementation,
        capabilities=capabilities, used_in=used_in, required=required,
        availability="available" if integrated else "not_integrated",
        enabled=integrated, configurable=integrated and not required, note=note,
    )


_OPTIONAL_NOTE = "停用后不会接受新的业务任务；已开始的调用可完成。离线评测独立运行。"
CATALOG = (
    _role("chat_agent", "对话助手", "理解你的问题，并选择需要调用的工具。", "coordination", "model",
          ["理解问题", "选择工具", "结合上下文回答"], ["工作台对话"], required=True, note="使用 API 配置中的默认模型；未配置时部分任务可由内置规则处理。"),
    _role("planner_agent", "任务规划", "把目标拆成任务，安排现有角色的分工。", "coordination", "rules",
          ["拆分任务", "安排依赖", "调整计划"], ["协作计划", "多智能体执行"], required=True, note="根据目标和项目状态按预设规则规划，不会自动创建新角色。"),
    _role("workflow_orchestrator", "流程协调器", "按计划组织执行，并连接核对与汇总步骤。", "coordination", "workflow",
          ["并行调度", "处理依赖", "管理超时与重规划"], ["多智能体执行"], required=True, note="这是流程协调器。项目概况、资料检索是它调用的任务能力，不额外计为独立智能体。"),
    _role("observer_agent", "结果核对", "检查分析结果里的证据缺口、冲突与确认要求。", "coordination", "rules",
          ["核对证据", "发现冲突", "标注未完成任务"], ["多智能体执行"], required=True, note="系统必需，确保未完成的分析不会被当成成功结果。"),
    _role("synthesis_agent", "结论汇总", "把各角色的结果整理成结论和下一步建议。", "coordination", "rules",
          ["汇总分析", "保留风险", "整理后续行动"], ["多智能体执行"], required=True, note="当前使用结构化结果和规则整理报告。"),
    _role("issue_analyst_agent", "问题分析", "分析项目问题的优先级、负责人和处理建议。", "analysis", "model",
          ["问题分诊", "优先级分析", "建议负责人与处理步骤"], ["问题分析工具", "工作台对话", "多智能体执行"], note=_OPTIONAL_NOTE),
    _role("pr_review_agent", "代码审查", "审查代码变更，识别合并风险和测试需求。", "analysis", "model",
          ["审查代码差异", "标注风险等级", "建议测试与合并条件"], ["代码审查工具", "工作台对话", "多智能体执行"], note=_OPTIONAL_NOTE),
    _role("ci_debug_agent", "检查排障", "根据自动检查日志分析失败原因和排查方向。", "analysis", "model",
          ["分析失败日志", "识别阻塞原因", "整理排查步骤"], ["检查与排错工具", "工作台对话", "多智能体执行"], note=_OPTIONAL_NOTE),
    _role("safety_agent", "操作检查", "判断外部写入等操作是否需要你确认。", "support", "rules",
          ["识别操作风险", "要求人工确认", "保留待确认草稿"], ["待确认操作", "工作台对话", "多智能体执行"], required=True, note="系统必需；智能体管理不会关闭人工确认要求。"),
    _role("report_agent", "报告整理", "根据项目活动整理研发周报。", "support", "rules",
          ["整理问题与变更", "统计项目活动", "生成周报"], ["开发报告工具", "工作台对话"], note=_OPTIONAL_NOTE),
    _role("recommendation_agent", "提问推荐", "根据当前项目状态推荐可以继续追问的问题。", "support", "rules",
          ["识别可关注事项", "生成提问建议", "避开重复推荐"], ["工作台推荐问题"], note=_OPTIONAL_NOTE),
    _role("github_retrieval_agent", "GitHub 资料检索", "代码中定义了获取问题、代码变更和检查日志的角色。", "support", "tools",
          ["读取项目问题", "读取代码变更", "读取检查日志"], [], integrated=False,
          note="尚未接入运行入口，不能在这里启用。当前项目同步和检索由其他服务提供。"),
)
_BY_ID = {role.id: role for role in CATALOG}
WORKFLOW_AGENT_IDS = {"issue_analysis": "issue_analyst_agent", "pr_review": "pr_review_agent", "ci_debug": "ci_debug_agent"}


def _definition(agent_id: str) -> AgentDescriptor:
    role = _BY_ID.get(agent_id)
    if role is None:
        raise AgentSettingsError("未找到这个智能体。", 404)
    return role


def disabled_agent_ids(db: Session) -> set[str]:
    # Select scalar columns rather than cached ORM objects so later calls see updates.
    rows = db.scalars(select(AgentSetting.agent_id).where(AgentSetting.enabled.is_(False)))
    return {agent_id for agent_id in rows if agent_id in _BY_ID and _BY_ID[agent_id].configurable}


def list_agents(db: Session) -> AgentListResponse:
    disabled = disabled_agent_ids(db)
    roles = [role.model_copy(update={"enabled": role.enabled and role.id not in disabled}, deep=True) for role in CATALOG]
    return AgentListResponse(agents=roles, total=len(roles))


def update_agent(db: Session, agent_id: str, enabled: bool) -> AgentDescriptor:
    role = _definition(agent_id)
    if not role.configurable:
        reason = "这个角色尚未接入运行入口，暂时无法启用。" if role.availability == "not_integrated" else "这是系统必需角色，不能停用。"
        raise AgentSettingsError(reason)
    row = db.get(AgentSetting, agent_id)
    if row is None:
        row = AgentSetting(agent_id=agent_id, enabled=enabled)
        db.add(row)
    else:
        row.enabled = enabled
    db.commit()
    return role.model_copy(update={"enabled": enabled}, deep=True)


def require_agent_enabled(db: Session, agent_id: str) -> None:
    role = _definition(agent_id)
    if role.availability != "available" or agent_id in disabled_agent_ids(db):
        raise AgentSettingsError(f"“{role.name}”已停用，请先在设置 → 智能体管理中启用。")


def agent_name(agent_id: str) -> str:
    return _definition(agent_id).name
