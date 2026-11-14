import { Check, ChevronDown, Circle, Loader2, Network, TriangleAlert } from "lucide-react";

type RunStatus = "running" | "done" | "error" | "unconfirmed";
type ExecutionRecord = { tool_name?: string; status?: string; error?: string };
type TraceRecord = { toolName?: string; status?: string; content?: string };
type Participant = { id: string; name: string; responsibility: string; status: RunStatus; summary: string };

const roles: Record<string, { id: string; name: string; responsibility: string }> = {
  planner_agent: { id: "planner", name: "任务规划", responsibility: "拆解目标，安排分工" },
  issue_analyst_agent: { id: "issue", name: "Issue 分析", responsibility: "识别优先级与待办事项" },
  issue_agent: { id: "issue", name: "Issue 分析", responsibility: "识别优先级与待办事项" },
  pr_review_agent: { id: "pr", name: "PR 审查", responsibility: "检查代码变更与合并风险" },
  ci_debug_agent: { id: "ci", name: "CI 排障", responsibility: "分析失败原因与修复方向" },
  repo_health_agent: { id: "repo", name: "项目概况", responsibility: "整理项目状态与待处理事项" },
  rag_context_agent: { id: "rag", name: "资料检索", responsibility: "查找项目依据" },
  safety_agent: { id: "safety", name: "操作检查", responsibility: "核对操作风险与确认要求" },
  observer_agent: { id: "observer", name: "结果核对", responsibility: "检查证据和结论是否一致" },
  report_agent: { id: "report", name: "报告整理", responsibility: "整理项目进展" }
};

const workflowRoles: Record<string, string> = {
  repo_health: "repo_health_agent", issue_analysis: "issue_analyst_agent", pr_review: "pr_review_agent",
  ci_debug: "ci_debug_agent", rag_search: "rag_context_agent", safety_review: "safety_agent"
};

function text(value: unknown): string { return typeof value === "string" ? value : ""; }

function roleForTool(name: string) {
  const [prefix, action] = name.replaceAll("__", ".").split(".");
  return roles[prefix] ?? (prefix === "workflow" ? roles[workflowRoles[action]] : undefined);
}

/** Plans describe possible work; only execution records establish participation. */
export function collaborationParticipants(
  events: Array<Record<string, unknown>>,
  traces: TraceRecord[],
  calls: ExecutionRecord[],
  pending: boolean
): Participant[] {
  const participants = new Map<string, Participant>();
  function add(role: typeof roles[string] | undefined, status: string, summary = "") {
    if (!role || ["skipped", "pending", "queued", "not_executed"].includes(status)) return;
    const resolved: RunStatus = status === "error" || status === "failed" ? "error"
      : status === "running" ? (pending ? "running" : "unconfirmed")
        : ["done", "success", "completed"].includes(status) ? "done" : "unconfirmed";
    const previous = participants.get(role.id);
    // A failed task stays visible even if another task for the same role succeeded.
    participants.set(role.id, {
      ...role,
      status: previous?.status === "error" ? "error" : resolved,
      summary: previous?.status === "error" ? previous.summary || summary : summary || previous?.summary || ""
    });
  }
  for (const call of calls) add(roleForTool(call.tool_name ?? ""), call.status ?? "", call.error);
  for (const trace of traces) add(roleForTool(trace.toolName ?? ""), trace.status ?? "");
  for (const event of events) {
    const kind = text(event.type);
    if (kind === "workflow_task_result") {
      add(roles[text(event.agent_name)] ?? roles[workflowRoles[text(event.task_type)]], text(event.status), text(event.summary));
    } else if (kind === "workflow_observer_result") {
      const findings = Array.isArray(event.findings) ? event.findings.length : 0;
      add(roles.observer_agent, "done", findings ? `已核对结果，发现 ${findings} 项需要关注的内容。` : "已完成证据与结论核对。");
    } else if (kind === "workflow_replan") {
      add(roles.planner_agent, "done", text(event.reason) || "已根据核对结果调整分工。");
    } else if (kind === "tool_result") {
      add(roleForTool(text(event.tool_name)), text(event.status), text(event.error));
    }
  }
  return [...participants.values()];
}

export function WorkspaceCollaboration({ events = [], traces = [], calls = [], pending, planning = false, stopped = false, failed: requestFailed = false }: {
  events?: Array<Record<string, unknown>>;
  traces?: TraceRecord[];
  calls?: ExecutionRecord[];
  pending: boolean;
  planning?: boolean;
  stopped?: boolean;
  failed?: boolean;
}) {
  const participants = collaborationParticipants(events, traces, calls, pending);
  const workflowStarted = traces.some((item) => item.toolName === "workflow.run_engineering_review")
    || calls.some((item) => item.tool_name === "workflow.run_engineering_review");
  const failed = participants.some((item) => item.status === "error");
  const unconfirmed = participants.some((item) => item.status === "unconfirmed");
  const summary = stopped ? "已停止接收结果" : requestFailed ? "任务未完成"
    : pending ? (workflowStarted ? "协作任务执行中" : planning ? "正在安排任务分工" : "正在处理任务")
    : planning ? "分工计划已生成" : failed ? "协作结束，部分任务未完成" : unconfirmed ? "部分执行结果尚未返回"
      : participants.length > 1 ? `${participants.length} 个角色已参与` : participants.length ? "已完成专项处理" : "任务助手直接处理";

  if (!participants.length) {
    return <div role={pending ? "status" : undefined} className="mb-5 flex items-center gap-2 text-xs text-slate-500">
      {pending ? <Loader2 className="h-3.5 w-3.5 animate-spin text-accent" /> : requestFailed ? <TriangleAlert className="h-3.5 w-3.5 text-amber-700" /> : <Circle className="h-3.5 w-3.5 text-slate-500" />}
      <span>{summary}</span>
      {pending && workflowStarted && <span className="hidden sm:inline">· 完成后可查看实际分工</span>}
    </div>;
  }

  return <details className="group mb-5 border-y border-line py-3">
    <summary className="flex cursor-pointer list-none flex-wrap items-center gap-x-3 gap-y-2 text-xs [&::-webkit-details-marker]:hidden">
      <span className="inline-flex items-center gap-2 font-medium text-ink"><Network className="h-4 w-4 text-accent" />本次协作</span>
      <span className="min-w-0 flex-1 text-slate-500">{participants.map((item) => item.name).join(" · ")}</span>
      <span className={`inline-flex items-center gap-1.5 ${failed ? "text-amber-700" : "text-slate-500"}`}>
        {pending && <Loader2 className="h-3 w-3 animate-spin text-accent" />}{summary}
        <ChevronDown className="h-3.5 w-3.5 transition group-open:rotate-180" />
      </span>
    </summary>
    <ol className="mt-4 space-y-4 pl-1">
      {participants.map((participant) => <li key={participant.id} className="flex gap-3 text-xs">
        <span className="mt-0.5 shrink-0">
          {participant.status === "running" ? <Loader2 className="h-4 w-4 animate-spin text-accent" />
            : participant.status === "done" ? <Check className="h-4 w-4 text-accent" />
              : participant.status === "error" ? <TriangleAlert className="h-4 w-4 text-amber-700" /> : <Circle className="h-4 w-4 text-slate-500" />}
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap justify-between gap-2"><span className="font-medium text-ink">{participant.name}</span><span className="text-slate-500">{participant.status === "done" ? "已完成" : participant.status === "error" ? "执行失败" : participant.status === "running" ? "正在执行" : "未收到完成记录"}</span></div>
          <p className="mt-1 text-slate-500">{participant.responsibility}</p>
          {participant.summary && <p className="mt-1 break-words leading-6 text-slate-600">{participant.summary}</p>}
        </div>
      </li>)}
    </ol>
  </details>;
}
