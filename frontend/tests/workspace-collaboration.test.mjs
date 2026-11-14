import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import Module from "node:module";
import path from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";
import ts from "typescript";
import { renderToStaticMarkup } from "react-dom/server";
import { createElement } from "react";

const filename = fileURLToPath(new URL("../components/workspace-collaboration.tsx", import.meta.url));
const compiled = ts.transpileModule(readFileSync(filename, "utf8"), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2021 }
});
const loaded = new Module(filename);
loaded.paths = Module._nodeModulePaths(path.dirname(filename));
loaded._compile(compiled.outputText, filename);
const { collaborationParticipants, WorkspaceCollaboration } = loaded.exports;

test("planned roles are not counted as executed agents", () => {
  assert.deepEqual(collaborationParticipants([{
    type: "workflow_spec", tasks: [{ agent_name: "issue_analyst_agent", status: "running" }]
  }], [], [], true), []);
});

test("skipped and pending tasks do not appear as successful participation", () => {
  const result = collaborationParticipants([
    { type: "workflow_task_result", agent_name: "issue_analyst_agent", status: "skipped" },
    { type: "workflow_task_result", agent_name: "pr_review_agent", status: "pending" },
    { type: "workflow_task_result", agent_name: "ci_debug_agent", status: "success", summary: "已找到错误日志" }
  ], [{ toolName: "workflow.issue_analysis", status: "skipped" }], [], false);
  assert.equal(result.length, 1);
  assert.equal(result[0].name, "CI 排障");
  assert.equal(result[0].summary, "已找到错误日志");
});

test("a failure is retained when the same agent has another successful task", () => {
  const result = collaborationParticipants([
    { type: "workflow_task_result", agent_name: "issue_analyst_agent", status: "error", summary: "任务失败" },
    { type: "workflow_task_result", agent_name: "issue_analyst_agent", status: "success", summary: "另一项完成" }
  ], [], [{ tool_name: "issue_agent.analyze_issue", status: "success" }], false);
  assert.equal(result.length, 1);
  assert.equal(result[0].name, "Issue 分析");
  assert.equal(result[0].status, "error");
  assert.equal(result[0].summary, "任务失败");
});

test("unknown status and interrupted calls never become completed", () => {
  for (const status of [undefined, "unexpected", "running"]) {
    const result = collaborationParticipants([], [{ toolName: "pr_review_agent.analyze_pr", status }], [], false);
    assert.equal(result[0].name, "PR 审查");
    assert.equal(result[0].status, "unconfirmed");
  }
  assert.equal(collaborationParticipants([], [{ toolName: "pr_review_agent.analyze_pr", status: "running" }], [], true)[0].status, "running");
});

test("stopped and failed empty runs do not claim completion", () => {
  for (const props of [{ stopped: true }, { failed: true }]) {
    const markup = renderToStaticMarkup(createElement(WorkspaceCollaboration, { pending: false, ...props }));
    assert.doesNotMatch(markup, /已完成|lucide-check|任务助手直接处理/);
    assert.match(markup, /已停止接收结果|任务未完成/);
  }
});

test("a workflow running marker does not invent its specialist agents", () => {
  const markup = renderToStaticMarkup(createElement(WorkspaceCollaboration, {
    pending: true, traces: [{ toolName: "workflow.run_engineering_review", status: "running" }]
  }));
  assert.match(markup, /协作任务执行中/);
  assert.doesNotMatch(markup, /PR 审查|Issue 分析|CI 排障/);
});
