import { useCallback, useEffect, useState } from "react";
import { Folder, Trash2 } from "lucide-react";

import { Card, PageTitle, PrimaryButton } from "@/components/ui/card";
import { apiDelete, apiGet, apiPost } from "@/lib/api";
import { API_BASE_URL } from "@/lib/api";
import type { Repository } from "@/lib/types";
import { getRepositorySyncError, isDemoRepository, refreshRepositoryData } from "@/lib/repository-sync";

type RepoConnectResult = {
  repo_id: string;
  full_name: string;
  provider: string;
  api_base_url?: string | null;
  local_path?: string | null;
  checkout_mode?: string;
  default_branch?: string | null;
  connected: boolean;
  demo_mode: boolean;
  message: string;
};

type RepoSource = "remote" | "local";

type RepoSyncResult = {
  repo_id: string;
  status: string;
  synced: {
    issues: number;
    pull_requests: number;
    workflow_runs: number;
  };
};

const providers = [
  { value: "github", label: "GitHub", hint: "支持公开项目；私有项目需要填写有访问权限的个人访问令牌。" },
  { value: "github_compatible", label: "兼容 GitHub 的自定义服务", hint: "适合使用企业版 GitHub 或兼容接口的服务，需要填写服务地址。" },
  { value: "gitlab", label: "GitLab（暂不支持）", hint: "此平台尚未接入，请先选择 GitHub。" },
  { value: "gitee", label: "Gitee（暂不支持）", hint: "此平台尚未接入，请先选择 GitHub。" }
];

export default function ReposPage() {
  const [repos, setRepos] = useState<Repository[]>([]);
  const [selectedRepoId, setSelectedRepoId] = useState<string>("");
  const [source, setSource] = useState<RepoSource>("remote");
  const [provider, setProvider] = useState("github");
  const [owner, setOwner] = useState("");
  const [repo, setRepo] = useState("");
  const [localPath, setLocalPath] = useState("");
  const [cloneParentDir, setCloneParentDir] = useState("");
  const [apiBaseUrl, setApiBaseUrl] = useState("https://api.github.com");
  const [token, setToken] = useState("");
  const [result, setResult] = useState<string>("");
  const [loading, setLoading] = useState(false);

  const selectedProvider = providers.find((item) => item.value === provider) ?? providers[0];
  const supportsRealConnect = provider === "github" || provider === "github_compatible";

  const refreshRepos = useCallback(async (nextSelectedId?: string) => {
    const items = await apiGet<Repository[]>("/api/repos");
    setRepos(items);
    setSelectedRepoId((current) => nextSelectedId || current || items[0]?.id || "");
  }, []);

  useEffect(() => {
    refreshRepos().catch(() => setRepos([]));
  }, [refreshRepos]);

  async function syncRepo(repoId: string) {
    const data = await apiPost<RepoSyncResult>(`/api/repos/${repoId}/sync`, {
      sync_issues: true,
      sync_pull_requests: true,
      sync_workflow_runs: true,
      limit: 50
    });
    return data;
  }

  async function connect() {
    if (source === "remote" && (!owner.trim() || !repo.trim())) {
      setResult("请填写项目所属的用户或组织，以及项目名称。");
      return;
    }
    if (source === "local" && !localPath.trim()) {
      setResult("请填写本地 Git 项目的文件夹路径。");
      return;
    }
    setLoading(true);
    try {
      const connected = await apiPost<RepoConnectResult>("/api/repos/connect", {
        owner: source === "remote" ? owner.trim() : undefined,
        repo: source === "remote" ? repo.trim() : undefined,
        local_path: source === "local" ? localPath.trim() : undefined,
        clone_parent_dir: source === "remote" && cloneParentDir.trim() ? cloneParentDir.trim() : undefined,
        provider,
        api_base_url: provider === "github" ? undefined : apiBaseUrl,
        token: token || undefined,
        demo_mode: false
      });
      setResult(`已连接 ${connected.full_name}，正在后台同步项目资料。完成后即可前往智能助手提问。`);
      await refreshRepos(connected.repo_id);
    } catch (error) {
      setResult(error instanceof Error ? error.message : "连接失败，请检查项目信息后重试。");
    } finally {
      setLoading(false);
    }
  }

  async function refreshRepo(repoId: string) {
    const repository = repos.find((item) => item.id === repoId);
    if (!repository || loading) return;
    setLoading(true);
    try {
      let synced: RepoSyncResult | undefined;
      await refreshRepositoryData(repository, {
        sync: async () => { synced = await syncRepo(repoId); },
        reload: () => refreshRepos(repoId)
      });
      setResult(isDemoRepository(repository)
        ? "已刷新本地演示数据。"
        : synced ? `同步完成：${synced.synced.issues} 个问题、${synced.synced.pull_requests} 次代码变更、${synced.synced.workflow_runs} 条检查记录。` : "项目资料已刷新。");
    } catch (error) {
      setResult(getRepositorySyncError(error));
    } finally {
      setLoading(false);
    }
  }

  async function selectRepo(repoId: string) {
    setSelectedRepoId(repoId);
    await apiPost(`/api/repos/${repoId}/select`, {});
    setResult("已切换当前项目。");
    await refreshRepos(repoId);
  }

  async function deleteRepo(item: Repository) {
    const confirmed = window.confirm(`确认移除项目 ${item.full_name} 及其在本系统中的问题、代码变更、检查记录和分析结果吗？远程代码库不会被删除。`);
    if (!confirmed) return;
    setLoading(true);
    try {
      await apiDelete(`/api/repos/${item.id}`);
      setResult("已移除项目及其在本系统中的记录。");
      await refreshRepos();
    } catch (error) {
      setResult(error instanceof Error ? error.message : "移除失败，请稍后重试。");
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <PageTitle title="连接项目" description="添加一个项目代码库，让助手了解你的代码和研发进展。可以选择 GitHub 项目，也可以连接本机的 Git 项目。" />

      <div className="grid gap-4 xl:grid-cols-[1.15fr_0.85fr]">
        <Card>
          <div className="grid gap-4">
            <div className="grid grid-cols-2 overflow-hidden rounded-md border border-line bg-slate-50 p-1">
              <button
                type="button"
                onClick={() => setSource("remote")}
                className={`h-9 rounded px-3 text-sm font-medium transition ${source === "remote" ? "bg-white text-ink shadow-sm" : "text-slate-600 hover:text-ink"}`}
              >
                GitHub 地址
              </button>
              <button
                type="button"
                onClick={() => setSource("local")}
                className={`h-9 rounded px-3 text-sm font-medium transition ${source === "local" ? "bg-white text-ink shadow-sm" : "text-slate-600 hover:text-ink"}`}
              >
                本地仓库
              </button>
            </div>

            <div className="grid gap-4 2xl:grid-cols-[200px_minmax(0,1fr)_minmax(0,1fr)]">
              <label className="text-sm font-medium text-slate-700">
                托管平台
                <select
                  className="mt-2 w-full rounded-md border border-line bg-white px-3 py-2 outline-none transition focus:border-teal-500 focus:ring-2 focus:ring-teal-100"
                  value={provider}
                  onChange={(event) => {
                    const next = event.target.value;
                    setProvider(next);
                    if (next === "github") setApiBaseUrl("https://api.github.com");
                    if (next === "github_compatible") setApiBaseUrl("https://api.example.com");
                    if (next === "gitlab") setApiBaseUrl("https://gitlab.com/api/v4");
                    if (next === "gitee") setApiBaseUrl("https://gitee.com/api/v5");
                  }}
                >
                  {providers.map((item) => (
                    <option key={item.value} value={item.value}>
                      {item.label}
                    </option>
                  ))}
                </select>
              </label>

              {source === "remote" ? (
                <>
                  <label className="text-sm font-medium text-slate-700">
                    所属用户或组织
                    <input
                      className="mt-2 w-full rounded-md border border-line bg-white px-3 py-2 outline-none transition focus:border-teal-500 focus:ring-2 focus:ring-teal-100"
                      value={owner}
                      onChange={(event) => setOwner(event.target.value)}
                      placeholder="例如：你的 GitHub 用户名"
                    />
                  </label>

                  <label className="text-sm font-medium text-slate-700">
                    项目名称
                    <input
                      className="mt-2 w-full rounded-md border border-line bg-white px-3 py-2 outline-none transition focus:border-teal-500 focus:ring-2 focus:ring-teal-100"
                      value={repo}
                      onChange={(event) => setRepo(event.target.value)}
                      placeholder="例如：DevHarbor"
                    />
                  </label>
                </>
              ) : (
                <label className="text-sm font-medium text-slate-700 lg:col-span-2">
                  本地仓库路径
                  <div className="mt-2 flex gap-2">
                    <input
                      className="min-w-0 flex-1 rounded-md border border-line bg-white px-3 py-2 outline-none transition focus:border-teal-500 focus:ring-2 focus:ring-teal-100"
                      value={localPath}
                      onChange={(event) => setLocalPath(event.target.value)}
                      placeholder="例如 D:\\code\\my-repo"
                    />
                    <span className="inline-flex w-10 shrink-0 items-center justify-center rounded-md border border-line bg-white text-slate-500">
                      <Folder className="h-4 w-4" />
                    </span>
                  </div>
                </label>
              )}
            </div>
          </div>

          <div className="mt-4 rounded-md border border-teal-100 bg-teal-50/70 p-3 text-sm leading-6 text-slate-700">
            <div className="font-medium text-teal-900">{selectedProvider.label}</div>
            <div>{selectedProvider.hint}</div>
          </div>

          <details className="mt-4 rounded-lg border border-line p-4">
            <summary className="cursor-pointer text-sm font-medium text-slate-600">更多连接选项 · 私有项目权限与保存位置</summary>
          <div className="mt-4 grid gap-4 lg:grid-cols-2">
            <label className="text-sm font-medium text-slate-700">
              接口地址
              <input
                className="mt-2 w-full rounded-md border border-line bg-white px-3 py-2 outline-none transition focus:border-teal-500 focus:ring-2 focus:ring-teal-100 disabled:bg-slate-100"
                value={apiBaseUrl}
                disabled={provider === "github"}
                onChange={(event) => setApiBaseUrl(event.target.value)}
              />
            </label>

            <label className="text-sm font-medium text-slate-700">
              个人访问令牌（可选）
              <input
                type="password"
                className="mt-2 w-full rounded-md border border-line bg-white px-3 py-2 outline-none transition focus:border-teal-500 focus:ring-2 focus:ring-teal-100"
                value={token}
                onChange={(event) => setToken(event.target.value)}
                placeholder="公开项目可留空，私有项目请填写访问令牌"
              />
            </label>

            {source === "remote" && (
              <label className="text-sm font-medium text-slate-700 lg:col-span-2">
                代码保存位置（可选）
                <input
                  className="mt-2 w-full rounded-md border border-line bg-white px-3 py-2 outline-none transition focus:border-teal-500 focus:ring-2 focus:ring-teal-100"
                  value={cloneParentDir}
                  onChange={(event) => setCloneParentDir(event.target.value)}
                  placeholder="例如 D:\\code\\repos，留空则使用默认缓存目录"
                />
              </label>
            )}
          </div>
          </details>

          <div className="mt-5 flex flex-wrap gap-3">
            <PrimaryButton
              onClick={connect}
              disabled={loading || !supportsRealConnect || (source === "remote" ? !owner.trim() || !repo.trim() : !localPath.trim())}
            >
              {loading ? "连接并同步中..." : "连接并自动同步"}
            </PrimaryButton>
          </div>

          {!supportsRealConnect && (
            <p className="mt-3 text-sm text-amber-700">当前平台已在界面预留，但真实 API 同步尚未实现。请选择 GitHub 或 兼容 GitHub 的服务。</p>
          )}

          {result && <div role="status" className="mt-4 rounded-lg border border-line bg-panel p-4 text-sm leading-6 text-slate-700">{result}</div>}
        </Card>

        <Card>
          <div className="flex items-center justify-between gap-3">
            <h2 className="font-semibold text-ink">已连接项目</h2>
            <span className="rounded-full bg-panel px-2.5 py-1 text-xs text-slate-500">{repos.length} 个</span>
          </div>
          <div className="mt-4 space-y-3">
            {repos.length === 0 && <p className="text-sm text-slate-600">还没有连接项目。填写左侧信息后，点击“连接并自动同步”。</p>}
            {repos.map((item) => (
              <div
                key={item.id}
                className={`rounded-lg border p-4 transition ${selectedRepoId === item.id ? "border-teal-300 bg-teal-50/70" : "border-line bg-white"}`}
              >
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <div className="font-medium text-ink">{item.full_name}</div>
                    <div className="mt-1 text-xs text-slate-500">
                      {item.provider || "github"} · {item.default_branch || "main"}
                    </div>
                    {item.local_path && <div className="mt-1 break-all text-xs text-slate-500">{item.checkout_mode === "local" ? "本地仓库" : "代码路径"}：{item.local_path}</div>}
                  </div>
                  <span className="rounded-full bg-panel px-2.5 py-1 text-xs text-slate-500">{selectedRepoId === item.id ? "当前查看" : "已连接"}</span>
                </div>
                <p className="mt-3 line-clamp-2 text-sm leading-6 text-slate-600">{item.description || "暂无仓库描述"}</p>
                <div className="mt-4 flex flex-wrap gap-2">
                  <button
                    onClick={() => selectRepo(item.id)}
                    className="rounded-md border border-line bg-white px-3 py-1.5 text-xs font-medium text-slate-700 transition hover:border-teal-200 hover:bg-teal-50"
                  >
                    设为当前查看
                  </button>
                  <button
                    onClick={() => refreshRepo(item.id)}
                    disabled={loading}
                    className="rounded-md bg-accent px-3 py-1.5 text-xs font-medium text-white transition hover:bg-teal-700 disabled:opacity-60"
                  >
                    立即刷新
                  </button>
                  <button
                    onClick={() => deleteRepo(item)}
                    disabled={loading}
                    className="inline-flex items-center gap-1 rounded-md border border-red-200 bg-white px-3 py-1.5 text-xs font-medium text-red-700 transition hover:bg-red-50 disabled:opacity-60"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                    删除
                  </button>
                </div>
              </div>
            ))}
          </div>
        </Card>
      </div>

      <Card className="mt-4">
        <details>
        <summary className="cursor-pointer font-semibold text-ink">了解项目如何保持更新</summary>
        <div className="mt-3 grid gap-3 text-sm leading-6 text-slate-600 md:grid-cols-3">
          <div className="rounded-md bg-panel p-3">
            <div className="font-medium text-ink">连接后自动同步</div>
            <p className="mt-1">仓库校验成功后，后端会立即调度一次后台同步。</p>
          </div>
          <div className="rounded-md bg-panel p-3">
            <div className="font-medium text-ink">实时更新通知</div>
            <p className="mt-1 break-all">GitHub 更新通知地址：{API_BASE_URL}/api/webhooks/github</p>
          </div>
          <div className="rounded-md bg-panel p-3">
            <div className="font-medium text-ink">定时同步兜底</div>
            <p className="mt-1">后端启动后会定时刷新已连接项目，默认 5 分钟一次。</p>
          </div>
        </div>
        </details>
      </Card>
    </>
  );
}
