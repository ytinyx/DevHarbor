const labels: Record<string, string> = {
  open: "待处理", closed: "已关闭", merged: "已合并", draft: "草稿",
  pending: "等待中", queued: "排队中", running: "进行中", in_progress: "进行中",
  completed: "已完成", success: "成功", failure: "失败", failed: "失败",
  cancelled: "已取消", canceled: "已取消", skipped: "已跳过", ready: "已就绪",
  degraded: "基础模式", unavailable: "不可用", disabled: "未启用", unknown: "未知",
  timed_out: "已超时", action_required: "需要处理", neutral: "无结论",
  pending_confirmation: "等待确认", executed: "已执行",
  issue: "Issue", pull_request: "PR", workflow_run: "CI", repository: "项目",
  comment: "评论", issue_comment: "Issue 评论", pr_comment: "PR 评论",
  create_issue: "新建 Issue", weekly_report: "研发周报", report: "报告",
  issue_triage: "Issue 分析", pr_review: "PR 审查", ci_debug: "CI 排障",
  issue_agent: "Issue 分析助手", pr_review_agent: "PR 审查助手", ci_debug_agent: "CI 排障助手",
  report_agent: "周报助手", github_retrieval_agent: "项目检索助手",
  planner_agent: "任务规划", observer_agent: "交叉检查", synthesis_agent: "结果汇总",
  IssueAgent: "Issue 分析助手", PRReviewAgent: "PR 审查助手", CIDebugAgent: "CI 排障助手",
  ReportAgent: "周报助手", GitHubRetrievalAgent: "项目检索助手",
  PlannerAgent: "任务规划", ObserverAgent: "交叉检查", SynthesisAgent: "结果汇总",
  vector: "语义检索", fulltext: "关键词检索", hybrid: "混合检索", retrieval: "资料检索",
  milvus: "Milvus", pgvector: "PostgreSQL（pgvector）",
  heuristic: "基础规则排序", weighted: "加权融合", rrf: "排序融合",
  local: "本地模型", qwen_local: "本地通义模型", deterministic: "演示模型",
  openai_compatible: "兼容接口", dashscope: "通义服务",
  function: "函数", class: "类", method: "方法", module: "模块",
  calls: "调用", imports: "引用", contains: "包含", inherits: "继承"
};

/** Translate display labels only; identifiers and API payloads stay unchanged. */
export function displayLabel(value: string | null | undefined, fallback = "未记录"): string {
  return value ? labels[value] ?? value : fallback;
}
