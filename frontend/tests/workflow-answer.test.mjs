import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import Module from "node:module";
import path from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";
import ts from "typescript";
import { renderToStaticMarkup } from "react-dom/server";
import { createElement } from "react";

const filename = fileURLToPath(new URL("../components/workflow-answer.tsx", import.meta.url));
const compiled = ts.transpileModule(readFileSync(filename, "utf8"), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2021 }
});
const loaded = new Module(filename);
loaded.paths = Module._nodeModulePaths(path.dirname(filename));
loaded._compile(compiled.outputText, filename);
const { parseWorkflowAnswer, WorkflowAnswer, workflowDisplayText } = loaded.exports;

const report = [
  "## 多 Agent 协作结论", "", "目标：检查 PR #42", "总体判断：暂缓合并或发布，先处理 CI/跨 Agent 冲突。", "Observer 置信度：0.35", "",
  "## 协作任务图", "- ci_debug: ci_debug_agent 负责检查", "",
  "## Agent 输出摘要", "- ci_debug_agent [success]: 找到失败日志", "",
  "## Observer 检查", "- WARNING: 尚需补充资料。 建议：同步日志。", "",
  "## 决策依据与待确认项", "- 完整依据：evidence-42", "",
  "## 下一步", "- 先修复 CI，再核对 PR #42。", "- 复查 https://example.test/CI/PR-42 与 `CI-run-42`。"
].join("\n");
const renderMarkdown = (content) => createElement("pre", null, content);

test("unknown or incomplete report formats render the full original answer", () => {
  for (const content of ["一份未知格式的报告\n严重风险：不可发布。\n证据：evidence-42", report.replace("## 下一步", "## 新格式建议")]) {
    assert.equal(parseWorkflowAnswer(content), null);
    const html = renderToStaticMarkup(createElement(WorkflowAnswer, { content, renderMarkdown }));
    assert.equal(html, renderToStaticMarkup(renderMarkdown(content)));
    assert.doesNotMatch(html, /完整协作报告/);
  }
});

test("compact result keeps blockers visible and preserves exact task identifiers in details", () => {
  const events = [
    { type: "workflow_observer_result", findings: [{ severity: "blocker", message: "旧轮次风险", task_ids: [] }] },
    { type: "workflow_observer_result", is_final: true, findings: [{ severity: "blocker", message: "ci_debug_agent 报告 PR #42 存在严重阻塞。", recommendation: "修复 CI 后再审批。", task_ids: ["CI-run/PR-42"] }] }
  ];
  const parsed = parseWorkflowAnswer(report, events);
  assert.equal(parsed.findings[0].severity, "blocker");
  assert.equal(parsed.findings[0].taskIds[0], "CI-run/PR-42");
  assert.equal(parsed.findings.length, 2);
  assert.ok(!parsed.findings.some((finding) => finding.message === "旧轮次风险"));
  const html = renderToStaticMarkup(createElement(WorkflowAnswer, { content: report, events, renderMarkdown }));
  const visible = html.slice(0, html.indexOf("<details"));
  assert.match(visible, /CI 排障助手 报告 PR #42 存在严重阻塞/);
  assert.match(visible, /修复 CI 后再审批/);
  assert.doesNotMatch(visible, /CI-run\/PR-42/);
  assert.match(html.slice(html.indexOf("<details")), /CI-run\/PR-42/);
  assert.match(visible, /暂缓合并或发布/);
  assert.match(html, /完整协作报告/);
  assert.ok(html.includes(renderToStaticMarkup(renderMarkdown(report))));
  assert.equal(workflowDisplayText("https://example.test/CI/PR-42 `CI-run-42`"), "https://example.test/CI/PR-42 `CI-run-42`");
  assert.equal(workflowDisplayText("Issue #7、PR #42 与 CI，PR/Issue 关联"), "Issue #7、PR #42 与 CI，PR/Issue 关联");
  assert.equal(workflowDisplayText("`CI Agent` [PR](https://example.test/Issue/CI)"), "`CI Agent` [PR](https://example.test/Issue/CI)");
});
