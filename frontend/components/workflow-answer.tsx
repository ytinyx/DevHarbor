import type { ReactNode } from "react";

type Finding = { severity: "blocker" | "warning" | "info"; message: string; recommendation: string; taskIds: string[] };
type WorkflowSummary = { decision: string; nextSteps: string[]; findings: Finding[] };
const headings = ["多 Agent 协作结论", "协作任务图", "Agent 输出摘要", "Observer 检查", "决策依据与待确认项", "下一步"];

export function parseWorkflowAnswer(content: string, events: Array<Record<string, unknown>> = []): WorkflowSummary | null {
  const report = content.replace(/\r\n/g, "\n").trim();
  const sections = [...report.matchAll(/^## (.+)$/gm)];
  if (sections.length !== headings.length || sections[0]?.index !== 0
    || sections.some((section, index) => section[1] !== headings[index])) return null;
  const bodies = sections.map((section, index) => report.slice(
    (section.index ?? 0) + section[0].length, sections[index + 1]?.index ?? report.length
  ).trim());
  const introduction = /^目标：[^\n]+\n总体判断：([^\n]+)\nObserver 置信度：(?:0(?:\.\d+)?|1(?:\.0+)?)$/.exec(bodies[0]);
  const nextSteps = bodies[5].split("\n");
  if (!introduction || !nextSteps.length || nextSteps.some((line) => !/^- .+/.test(line))) return null;

  const findings: Finding[] = [];
  if (bodies[3] !== "- 未发现跨 Agent 结论冲突。") {
    for (const line of bodies[3].split("\n")) {
      const finding = /^- (BLOCKER|WARNING|INFO): (.+?) 建议：(.*)$/.exec(line);
      if (!finding) return null;
      findings.push({ severity: finding[1].toLowerCase() as Finding["severity"], message: finding[2], recommendation: finding[3], taskIds: [] });
    }
  }

  const observation = [...events].reverse().find((event) => event.type === "workflow_observer_result");
  if (observation) {
    if (!Array.isArray(observation.findings)) return null;
    for (const value of observation.findings) {
      if (!value || typeof value !== "object") return null;
      const finding = value as Record<string, unknown>;
      if (!["blocker", "warning", "info"].includes(String(finding.severity)) || typeof finding.message !== "string" || !finding.message.trim()) return null;
      const recommendation = typeof finding.recommendation === "string" ? finding.recommendation : "";
      const existing = findings.find((item) => item.severity === finding.severity && item.message === finding.message && item.recommendation === recommendation);
      const taskIds = Array.isArray(finding.task_ids) ? finding.task_ids.filter((id): id is string => typeof id === "string") : [];
      if (existing) existing.taskIds = taskIds;
      else findings.push({ severity: finding.severity as Finding["severity"], message: finding.message, recommendation, taskIds });
    }
  }
  const priority = { blocker: 0, warning: 1, info: 2 };
  return { decision: introduction[1], nextSteps: nextSteps.map((line) => line.slice(2)), findings: findings.sort((left, right) => priority[left.severity] - priority[right.severity]) };
}

const words: Record<string, string> = {
  "最新失败 workflow": "最近失败的 CI", "review comment": "审查意见", job: "检查任务", diff: "代码差异",
  "CI/跨 Agent": "CI 或跨智能体",
  issue_analyst_agent: "Issue 分析助手", issue_agent: "Issue 分析助手", pr_review_agent: "PR 审查助手", ci_debug_agent: "CI 排障助手",
  repo_health_agent: "项目概况助手", rag_context_agent: "资料检索助手", planner_agent: "任务规划助手", observer_agent: "结果核对助手", synthesis_agent: "结果汇总助手", safety_agent: "操作检查助手",
  "CI Agent": "CI 排障助手", "PR Agent": "PR 审查助手", "Issue Agent": "Issue 分析助手", SafetyAgent: "操作检查助手",
  "跨 Agent": "跨智能体", Observer: "结果核对助手", workflow: "工作流", Agent: "智能体"
};
const knownWords = new RegExp(`(?<![A-Za-z0-9_./:-])(?:${Object.keys(words).join("|")})(?![A-Za-z0-9_./:-])`, "g");

export function workflowDisplayText(value: string): string {
  // Leave code, URLs and link destinations intact; task IDs are rendered separately.
  return value.split(/(```[\s\S]*?```|`[^`]*`|https?:\/\/[^\s<>]+|\]\([^)]*\))/g)
    .map((part, index) => index % 2 ? part : part.replace(knownWords, (word) => words[word])).join("");
}

export function WorkflowAnswer({ content, events, renderMarkdown }: {
  content: string;
  events?: Array<Record<string, unknown>>;
  renderMarkdown: (text: string) => ReactNode;
}) {
  const summary = parseWorkflowAnswer(content, events);
  if (!summary) return <>{renderMarkdown(content)}</>;
  return <div className="space-y-5">
    <p className="text-base font-medium leading-8 text-ink">{workflowDisplayText(summary.decision)}</p>
    {summary.findings.length > 0 && <section aria-label="风险与待确认事项">
      <h3 className="mb-3 text-xs font-medium text-slate-500">风险与待确认</h3>
      <ul className="space-y-3">
        {summary.findings.map((finding, index) => <li key={index} className={`border-l-2 pl-3 ${finding.severity === "blocker" ? "border-rose-600/60" : "border-amber-600/50"}`}>
          <p className="text-sm leading-7"><span className={`mr-2 text-xs font-medium ${finding.severity === "blocker" ? "text-rose-600" : "text-amber-700"}`}>{finding.severity === "blocker" ? "阻塞" : finding.severity === "warning" ? "注意" : "提示"}</span>{workflowDisplayText(finding.message)}</p>
          {finding.recommendation && <p className="mt-0.5 text-xs leading-6 text-slate-500">{workflowDisplayText(finding.recommendation)}</p>}
        </li>)}
      </ul>
    </section>}
    <section aria-label="建议下一步">
      <h3 className="mb-2 text-xs font-medium text-slate-500">建议下一步</h3>
      <ol className="list-decimal space-y-1.5 pl-5 text-sm leading-7 text-slate-600">
        {summary.nextSteps.map((step, index) => <li key={index}>{workflowDisplayText(step)}</li>)}
      </ol>
    </section>
    <details className="border-t border-line pt-3">
      <summary className="w-fit cursor-pointer text-xs text-slate-500">完整协作报告</summary>
      <div className="mt-4">{renderMarkdown(content)}</div>
      {summary.findings.some((finding) => finding.taskIds.length > 0) && <div className="mt-4 space-y-2 border-t border-line pt-3 text-xs text-slate-500">{summary.findings.filter((finding) => finding.taskIds.length > 0).map((finding, index) => <p key={index}>{workflowDisplayText(finding.message)}<span className="block">关联任务：{finding.taskIds.map((id) => <code key={id} className="mr-2 break-all">{id}</code>)}</span></p>)}</div>}
    </details>
  </div>;
}
