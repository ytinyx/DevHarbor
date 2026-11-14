import { useEffect, useMemo, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { apiGet, apiPost } from "@/lib/api";
import type { Repository } from "@/lib/types";
import { Card, PageTitle, PrimaryButton } from "@/components/ui/card";

type Workspace = {
  id: string;
  name: string;
  description?: string | null;
  repo_ids: string[];
};

type MultiRepoReport = {
  report_markdown: string;
  metrics: Record<string, number>;
  repo_summaries: Array<Record<string, unknown>>;
};

function toDateInput(date: Date) {
  return date.toISOString().slice(0, 10);
}

export default function WorkspacesPage() {
  const today = useMemo(() => new Date(), []);
  const start = useMemo(() => {
    const value = new Date(today);
    value.setDate(value.getDate() - 6);
    return value;
  }, [today]);
  const [repos, setRepos] = useState<Repository[]>([]);
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [name, setName] = useState("研发团队");
  const [selectedRepos, setSelectedRepos] = useState<string[]>([]);
  const [workspaceId, setWorkspaceId] = useState("");
  const [startDate, setStartDate] = useState(toDateInput(start));
  const [endDate, setEndDate] = useState(toDateInput(today));
  const [report, setReport] = useState<MultiRepoReport | null>(null);
  const [loading, setLoading] = useState(false);

  async function load() {
    const [repoItems, workspaceItems] = await Promise.all([apiGet<Repository[]>("/api/repos"), apiGet<Workspace[]>("/api/workspaces")]);
    setRepos(repoItems);
    setWorkspaces(workspaceItems);
    setSelectedRepos(repoItems.slice(0, 2).map((repo) => repo.id));
    setWorkspaceId(workspaceItems[0]?.id || "");
  }

  useEffect(() => {
    load().catch(() => undefined);
  }, []);

  async function createWorkspace() {
    if (!name.trim()) return;
    setLoading(true);
    try {
      await apiPost<Workspace>("/api/workspaces", { name, repo_ids: selectedRepos });
      await load();
    } finally {
      setLoading(false);
    }
  }

  async function generateReport() {
    setLoading(true);
    try {
      const data = await apiPost<MultiRepoReport>("/api/workspaces/multi-repo-report", {
        workspace_id: workspaceId || undefined,
        repo_ids: workspaceId ? [] : selectedRepos,
        start_date: startDate,
        end_date: endDate
      });
      setReport(data);
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <PageTitle title="团队工作区" description="将多个项目归到同一个工作区，一次查看团队进展并生成汇总周报。" />
      <div className="grid gap-4 lg:grid-cols-[380px_1fr]">
        <Card>
          <label className="text-sm font-medium text-slate-700">
            工作区名称
            <input className="mt-2 w-full rounded-md border border-line px-3 py-2 outline-none" value={name} onChange={(event) => setName(event.target.value)} />
          </label>
          <div className="mt-4 text-sm font-medium text-slate-700">仓库</div>
          <div className="mt-2 grid gap-2">
            {repos.map((repo) => (
              <label key={repo.id} className="flex items-center gap-2 rounded-md border border-line px-3 py-2 text-sm">
                <input
                  type="checkbox"
                  checked={selectedRepos.includes(repo.id)}
                  onChange={(event) => {
                    setSelectedRepos((current) => (event.target.checked ? [...current, repo.id] : current.filter((id) => id !== repo.id)));
                  }}
                />
                {repo.full_name}
              </label>
            ))}
          </div>
          <PrimaryButton className="mt-4" disabled={loading || selectedRepos.length === 0} onClick={createWorkspace}>
            创建工作区
          </PrimaryButton>

          <div className="mt-6 grid gap-3 border-t border-line pt-4">
            <label className="text-sm font-medium text-slate-700">
              报表范围
              <select className="mt-2 w-full rounded-md border border-line px-3 py-2" value={workspaceId} onChange={(event) => setWorkspaceId(event.target.value)}>
                <option value="">使用上方勾选仓库</option>
                {workspaces.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name}
                  </option>
                ))}
              </select>
            </label>
            <input className="rounded-md border border-line px-3 py-2" type="date" value={startDate} onChange={(event) => setStartDate(event.target.value)} />
            <input className="rounded-md border border-line px-3 py-2" type="date" value={endDate} onChange={(event) => setEndDate(event.target.value)} />
            <PrimaryButton disabled={loading || (!workspaceId && selectedRepos.length === 0)} onClick={generateReport}>
              生成多项目周报
            </PrimaryButton>
          </div>
        </Card>

        <div className="grid gap-4">
          <Card>
            <h2 className="font-semibold text-ink">已有工作区</h2>
            <div className="mt-3 grid gap-2">
              {workspaces.map((item) => (
                <div key={item.id} className="rounded-md border border-line bg-panel px-3 py-2 text-sm text-slate-700">
                  {item.name} · {item.repo_ids.length} 个仓库
                </div>
              ))}
              {workspaces.length === 0 && <div className="text-sm text-slate-500">还没有工作区。勾选项目后即可创建。</div>}
            </div>
          </Card>
          <Card>
            <h2 className="font-semibold text-ink">多项目周报</h2>
            {report ? (
              <div className="markdown-body mt-4 max-h-[620px] overflow-auto rounded-md border border-line bg-panel p-5 text-sm leading-7 text-slate-700"><ReactMarkdown remarkPlugins={[remarkGfm]}>{report.report_markdown}</ReactMarkdown></div>
            ) : (
              <div className="mt-4 rounded-md border border-line bg-panel p-4 text-sm text-slate-600">先选择工作区或勾选项目，再点击“生成多项目周报”。</div>
            )}
          </Card>
        </div>
      </div>
    </>
  );
}
