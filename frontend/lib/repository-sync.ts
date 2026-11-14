import type { Repository } from "./types";

// Identify only the bundled fixture created by scripts/seed_demo_data.py.
// Do not disable remote sync globally: real repositories can coexist with it.
export function isDemoRepository(repo: Repository | undefined): boolean {
  return repo?.full_name === "devharbor-demo/devharbor-sample-api"
    && repo.description === "Sample repository for the DevHarbor local demo"
    && (!repo.provider || repo.provider === "github");
}

export async function refreshRepositoryData(
  repo: Repository,
  actions: { sync: () => Promise<unknown>; reload: () => Promise<unknown> }
): Promise<void> {
  if (!isDemoRepository(repo)) await actions.sync();
  await actions.reload();
}

export function getRepositorySyncError(error: unknown): string {
  let message = error instanceof Error ? error.message : String(error);
  try {
    const payload = JSON.parse(message) as { detail?: unknown; message?: unknown };
    if (typeof payload?.detail === "string") message = payload.detail;
    else if (typeof payload?.message === "string") message = payload.message;
  } catch {
    // Older backends return a prefix followed by the GitHub JSON response.
  }
  if (/rate limit|secondary rate|abuse detection/i.test(message)) {
    return "GitHub 请求次数已达上限，暂时无法同步。可以继续查看已加载的数据，请稍后重试；连接真实仓库时可配置 GitHub Access Token。";
  }
  if (/failed to fetch|networkerror|network request failed/i.test(message)) {
    return "无法连接后端服务，暂时无法刷新。请确认后端已启动，已有页面数据仍可查看。";
  }
  return `刷新未完成：${message || "未知错误，请稍后重试。"}`;
}
