import { displayLabel } from "@/lib/display";

import { useEffect, useRef, useState } from "react";

import { Card, GhostButton, PageTitle, PrimaryButton } from "@/components/ui/card";
import { AnalysisResult } from "@/components/analysis-result";
import { apiGet, apiPost } from "@/lib/api";
import type { Repository } from "@/lib/types";

type Issue = { id: string; number: number; title: string; state: string; labels: string[]; body?: string };

export default function IssuesPage() {
  const [issues, setIssues] = useState<Issue[]>([]);
  const [selected, setSelected] = useState<Issue | null>(null);
  const [analysis, setAnalysis] = useState("");

  const [repos, setRepos] = useState<Repository[]>([]);
  const [repoId, setRepoId] = useState("");
  const [loadingProjects, setLoadingProjects] = useState(true);
  const [loadingItems, setLoadingItems] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState("");
  const projectRequestRef = useRef(0);
  const analysisRequestRef = useRef(0);

  useEffect(() => {
    let active = true;
    apiGet<Repository[]>("/api/repos")
      .then((items) => {
        if (!active) return;
        setRepos(items);
        setRepoId(items[0]?.id ?? "");
      })
      .catch(() => { if (active) setError("暂时无法读取项目，请检查后端服务后刷新页面。"); })
      .finally(() => { if (active) setLoadingProjects(false); });
    return () => { active = false; analysisRequestRef.current += 1; };
  }, []);

  useEffect(() => {
    if (!repoId) return;
    const request = ++projectRequestRef.current;
    let active = true;
    setLoadingItems(true);
    setError("");
    apiGet<Issue[]>(`/api/repos/${repoId}/issues`)
      .then((items) => {
        if (!active || request !== projectRequestRef.current) return;
        setIssues(items);
        setSelected(items[0] ?? null);
      })
      .catch((reason) => {
        if (active && request === projectRequestRef.current) setError(reason instanceof Error ? reason.message : "读取项目记录失败，请稍后重试。");
      })
      .finally(() => {
        if (active && request === projectRequestRef.current) setLoadingItems(false);
      });
    return () => { active = false; };
  }, [repoId]);

  function chooseProject(nextRepoId: string) {
    projectRequestRef.current += 1;
    analysisRequestRef.current += 1;
    setRepoId(nextRepoId);
    setIssues([]);
    setSelected(null);
    setAnalysis("");
    setAnalyzing(false);
    setError("");
  }

  function chooseItem(item: Issue) {
    analysisRequestRef.current += 1;
    setSelected(item);
    setAnalysis("");
    setAnalyzing(false);
    setError("");
  }

  async function analyze() {
    if (!selected || analyzing || loadingItems) return;
    const request = ++analysisRequestRef.current;
    setAnalyzing(true);
    setAnalysis("");
    setError("");
    try {
      const data = await apiPost(`/api/issues/${selected.id}/analyze`, {});
      if (request === analysisRequestRef.current) setAnalysis(JSON.stringify(data, null, 2));
    } catch (reason) {
      if (request === analysisRequestRef.current) setError(reason instanceof Error ? reason.message : "分析失败，请稍后重试。");
    } finally {
      if (request === analysisRequestRef.current) setAnalyzing(false);
    }
  }

  return (
    <>
      <PageTitle title="Issue 分析" description="选择一个 Issue（问题），查看优先级、处理难度、负责人建议和下一步行动。" />
      <div className="mb-5 rounded-xl border border-line bg-white p-4">
        <label className="block text-sm font-medium text-slate-700">
          当前项目
          <select value={repoId} onChange={(event) => chooseProject(event.target.value)} disabled={loadingProjects || repos.length === 0} className="mt-2 w-full rounded-lg border border-line bg-panel px-3 py-2.5 text-sm text-ink outline-none focus:border-teal-500 sm:max-w-lg">
            {!repos.length && <option value="">{loadingProjects ? "正在读取项目…" : "请先在“我的项目”中连接项目"}</option>}
            {repos.map((repo) => <option key={repo.id} value={repo.id}>{repo.full_name}</option>)}
          </select>
        </label>
        <p className="mt-2 text-xs leading-5 text-slate-500">下方仅显示所选项目的记录。切换项目后，需要重新选择并分析。</p>
      </div>
      {error && <p role="alert" className="mb-4 rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700">{error}</p>}
      <div className="grid gap-4 lg:grid-cols-[380px_1fr]">
        <Card>
          <div className="flex items-center justify-between">
            <h2 className="font-semibold text-ink">Issue 列表</h2>
            <span className="rounded-full bg-panel px-2.5 py-1 text-xs text-slate-500">{issues.length} 条</span>
          </div>
          <div className="mt-4 space-y-2">
            {loadingItems && <p role="status" className="py-4 text-sm text-slate-500">正在读取当前项目的 Issue…</p>}
            {!loadingProjects && !loadingItems && !error && issues.length === 0 && <p className="py-4 text-sm leading-6 text-slate-500">{repoId ? "这个项目还没有已同步的 Issue。" : "连接项目后，即可查看 Issue。"}</p>}
            {issues.map((issue) => (
              <GhostButton key={issue.id} onClick={() => chooseItem(issue)} className={selected?.id === issue.id ? "border-teal-300 bg-teal-50 text-teal-900" : ""}>
                <div className="flex items-center justify-between gap-3">
                  <span>Issue #{issue.number} {issue.title}</span>
                  <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs">{displayLabel(issue.state)}</span>
                </div>
              </GhostButton>
            ))}
          </div>
        </Card>

        <Card>
          <h2 className="font-semibold text-ink">Issue 分析结果</h2>
          {selected && (
            <div className="mt-3 rounded-md bg-panel p-3 text-sm leading-6 text-slate-600">
              <div className="font-medium text-ink">Issue #{selected.number} {selected.title}</div>
              <div className="mt-1">{selected.body || "暂无正文"}</div>
            </div>
          )}
          <PrimaryButton onClick={analyze} disabled={!selected || analyzing || loadingItems} className="mt-4">{analyzing ? "正在分析 Issue…" : "分析此 Issue"}</PrimaryButton>
          {analysis && <AnalysisResult data={analysis} />}
        </Card>
      </div>
    </>
  );
}
