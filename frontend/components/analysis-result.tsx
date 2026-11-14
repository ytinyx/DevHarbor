import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

type RecordValue = Record<string, unknown>;

const valueLabels: Record<string, string> = {
  Bug: "缺陷", Feature: "功能需求", Question: "使用问题", Documentation: "文档",
  Refactor: "代码重构", Test: "测试", Ops: "运维",
  P0: "紧急（P0）", P1: "高（P1）", P2: "中（P2）", P3: "低（P3）",
  S: "较小", M: "中等", L: "较大", XL: "很大",
  test: "测试失败", build: "构建失败", lint: "代码规范检查",
  dependency: "依赖问题", permission: "权限问题", environment: "环境问题", unknown: "尚未确定"
};
const textFields = [
  ["conclusion_reason", "判断依据"], ["recommendation_reason", "审查理由"],
  ["owner_reason", "负责人建议依据"], ["root_cause", "原因分析"],
  ["first_error", "最早出现的错误"], ["blocking_reason", "合入影响说明"]
] as const;
const listFields = [
  ["key_changes", "主要改动"], ["review_findings", "审查发现"],
  ["risk_points", "需要关注的风险"], ["blocking_issues", "合入前需要解决"],
  ["possible_causes", "可能的原因"], ["fix_steps", "建议修复步骤"],
  ["debug_steps", "排查步骤"], ["action_items", "下一步行动"],
  ["checklist", "检查清单"], ["review_checklist", "审查清单"],
  ["test_suggestions", "测试建议"], ["files_need_attention", "重点关注的文件"],
  ["related_files", "相关文件"], ["review_comments", "建议评论"],
  ["plan", "分析计划"], ["executed_steps", "已执行步骤"]
] as const;

function isRecord(value: unknown): value is RecordValue {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}
function text(value: unknown): string {
  return typeof value === "string" ? value : typeof value === "number" ? String(value) : "";
}
function readable(value: unknown): string {
  const content = text(value);
  return valueLabels[content] ?? content;
}
function MarkdownText({ children }: { children: string }) {
  return <div className="markdown-body min-w-0 overflow-x-auto text-sm leading-7 text-slate-700"><ReactMarkdown remarkPlugins={[remarkGfm]}>{children}</ReactMarkdown></div>;
}

/** Readable views of the three analysis schemas; original fields remain available below. */
export function AnalysisResult({ data }: { data: unknown }) {
  let parsed = data;
  if (typeof data === "string") {
    try { parsed = JSON.parse(data); } catch { parsed = data; }
  }
  const envelope = isRecord(parsed) ? parsed : {};
  const result = isRecord(envelope.result) ? envelope.result : envelope;
  const summary = text(result.summary || result.failure_summary || result.answer || result.markdown || result.report_markdown)
    || (typeof parsed === "string" ? parsed : typeof envelope.result === "string" ? envelope.result : "");
  const conclusion = text(result.conclusion || result.merge_recommendation);
  const facts = [
    ["Issue 类型", readable(result.category)], ["优先级", readable(result.priority)],
    ["处理复杂度", readable(result.complexity)], ["建议负责人", text(result.suggested_owner)],
    ["失败类型", readable(result.failure_type)],
    ["是否阻止合入", typeof result.is_merge_blocking === "boolean" ? result.is_merge_blocking ? "是" : "否" : ""]
  ].filter(([, value]) => value);
  const findings = Array.isArray(result.review_findings) ? result.review_findings.filter(isRecord) : [];
  const evidence = Array.isArray(result.evidence) ? result.evidence.filter(isRecord) : [];
  const duplicates = Array.isArray(result.duplicate_candidates) ? result.duplicate_candidates.filter(isRecord) : [];
  const drafts = isRecord(result.drafts) ? result.drafts : {};
  const original = typeof data === "string" ? data : JSON.stringify(data, null, 2);

  return (
    <div className="mt-5 min-w-0 space-y-5" aria-label="分析报告">
      {conclusion && <div className="rounded-xl border border-teal-200 bg-teal-50 p-4"><span className="text-xs text-teal-800">分析建议</span><p className="mt-1 font-semibold text-ink">{conclusion}</p></div>}
      {summary && <section><h3 className="mb-2 text-sm font-semibold text-ink">分析概览</h3><MarkdownText>{summary}</MarkdownText></section>}
      {facts.length > 0 && <dl className="grid gap-3 rounded-xl border border-line bg-panel p-4 sm:grid-cols-2">{facts.map(([label, value]) => <div key={label}><dt className="text-xs text-slate-500">{label}</dt><dd className="mt-1 break-words text-sm font-medium text-ink">{value}</dd></div>)}</dl>}
      {textFields.map(([key, label]) => text(result[key]) ? <section key={key}><h3 className="mb-2 text-sm font-semibold text-ink">{label}</h3><MarkdownText>{text(result[key])}</MarkdownText></section> : null)}
      {listFields.map(([key, label]) => {
        if (key === "review_findings") {
          return findings.length ? <section key={key}><h3 className="mb-3 text-sm font-semibold text-ink">{label}</h3><div className="space-y-3">{findings.map((finding, index) => <article key={index} className="rounded-xl border border-line bg-panel p-4"><div className="flex flex-wrap items-center gap-2"><h4 className="text-sm font-semibold text-ink">{text(finding.title) || `发现 ${index + 1}`}</h4><span className="text-xs text-amber-700">{readable(finding.severity)}{finding.blocking === true ? " · 合入前需处理" : ""}</span></div>{text(finding.evidence) && <div className="mt-2"><span className="text-xs text-slate-500">依据</span><MarkdownText>{text(finding.evidence)}</MarkdownText></div>}{text(finding.required_action) && <div className="mt-3"><span className="text-xs text-teal-800">建议行动</span><MarkdownText>{text(finding.required_action)}</MarkdownText></div>}</article>)}</div></section> : null;
        }
        const items = Array.isArray(result[key]) ? (result[key] as unknown[]).map(text).filter(Boolean) : [];
        return items.length ? <section key={key}><h3 className="mb-2 text-sm font-semibold text-ink">{label}</h3><ol className="list-decimal space-y-2 pl-5 text-sm text-slate-500">{items.map((item, index) => <li key={index}><MarkdownText>{item}</MarkdownText></li>)}</ol></section> : null;
      })}
      {duplicates.length > 0 && <section><h3 className="mb-2 text-sm font-semibold text-ink">可能相关的 Issue</h3><ul className="space-y-2">{duplicates.map((item, index) => <li key={index} className="rounded-lg border border-line p-3 text-sm text-slate-700">{text(item.title)}{typeof item.score === "number" && <span className="ml-2 text-xs text-slate-500">相似度 {Math.round(item.score * 100)}%</span>}</li>)}</ul></section>}
      {evidence.length > 0 && <section><h3 className="mb-2 text-sm font-semibold text-ink">参考依据</h3><div className="space-y-3">{evidence.map((item, index) => <article key={index} className="rounded-xl border border-line p-4"><h4 className="mb-2 text-sm font-medium text-ink">{text(item.title) || `资料 ${index + 1}`}</h4><MarkdownText>{text(item.snippet)}</MarkdownText></article>)}</div></section>}
      {([['clarification_comment', '建议追问的内容'], ['task_breakdown', '建议任务拆分']] as const).map(([key, label]) => text(drafts[key]) ? <section key={key}><h3 className="mb-2 text-sm font-semibold text-ink">{label}</h3><MarkdownText>{text(drafts[key])}</MarkdownText></section> : null)}
      {typeof result.confidence === "number" && <p className="text-xs text-slate-500">助手自评置信度：{Math.round(result.confidence * 100)}%</p>}
      <details className="rounded-xl border border-line bg-panel p-4"><summary className="cursor-pointer text-xs text-slate-500">查看原始分析数据</summary><pre className="mt-3 max-h-[480px] overflow-auto text-xs leading-6 text-slate-600">{original}</pre></details>
    </div>
  );
}
