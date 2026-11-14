import { useEffect, useRef, useState } from "react";

import { Card, GhostButton, PageTitle, PrimaryButton } from "@/components/ui/card";
import { AnalysisResult } from "@/components/analysis-result";
import { apiGet, apiPost } from "@/lib/api";
import type { Repository } from "@/lib/types";

type PullRequest = {
  id: string;
  number: number;
  title: string;
  state: string;
  files: { filename: string; additions: number; deletions: number }[];
};

export default function PullRequestsPage() {
  const [prs, setPrs] = useState<PullRequest[]>([]);
  const [selected, setSelected] = useState<PullRequest | null>(null);
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
    apiGet<PullRequest[]>(`/api/repos/${repoId}/pull-requests`)
      .then((items) => {
        if (!active || request !== projectRequestRef.current) return;
        setPrs(items);
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
    setPrs([]);
    setSelected(null);
    setAnalysis("");
    setAnalyzing(false);
    setError("");
  }

  function chooseItem(item: PullRequest) {
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
      const data = await apiPost(`/api/pull-requests/${selected.id}/analyze`, {});
      if (request === analysisRequestRef.current) setAnalysis(JSON.stringify(data, null, 2));
    } catch (reason) {
      if (request === analysisRequestRef.current) setError(reason instanceof Error ? reason.message : "分析失败，请稍后重试。");
    } finally {
      if (request === analysisRequestRef.current) setAnalyzing(false);
    }
  }

  return (
    <>
      <PageTitle title="PR 审查" description="选择一个 PR（代码变更），让助手查看修改内容，整理风险、检查清单和测试建议。" />
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
            <h2 className="font-semibold text-ink">PR 列表</h2>
            <span className="rounded-full bg-panel px-2.5 py-1 text-xs text-slate-500">{prs.length} 个</span>
          </div>
          <div className="mt-4 space-y-2">
            {loadingItems && <p role="status" className="py-4 text-sm text-slate-500">正在读取当前项目的 PR…</p>}
            {!loadingProjects && !loadingItems && !error && prs.length === 0 && <p className="py-4 text-sm leading-6 text-slate-500">{repoId ? "这个项目还没有已同步的 PR。" : "连接项目后，即可查看 PR。"}</p>}
            {prs.map((pr) => (
              <GhostButton key={pr.id} onClick={() => chooseItem(pr)} className={selected?.id === pr.id ? "border-teal-300 bg-teal-50 text-teal-900" : ""}>
                PR #{pr.number} {pr.title}
              </GhostButton>
            ))}
          </div>
        </Card>

        <Card>
          <h2 className="font-semibold text-ink">PR 审查结果</h2>
          {selected && (
            <div className="mt-3 rounded-md bg-panel p-3">
              <div className="text-sm font-medium text-ink">PR #{selected.number} {selected.title}</div>
              <div className="mt-3 grid gap-2">
                {selected.files.map((file) => (
                  <div key={file.filename} className="flex items-center justify-between rounded-md bg-white px-3 py-2 text-sm text-slate-600">
                    <span className="truncate">{file.filename}</span>
                    <span className="ml-3 whitespace-nowrap text-xs text-slate-500">+{file.additions} / -{file.deletions}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
          <PrimaryButton onClick={analyze} disabled={!selected || analyzing || loadingItems} className="mt-4">{analyzing ? "正在审查 PR…" : "审查此 PR"}</PrimaryButton>
          {analysis && <AnalysisResult data={analysis} />}
        </Card>
      </div>
    </>
  );
}
