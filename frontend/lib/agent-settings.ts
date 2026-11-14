import { apiGet, apiPatch } from "@/lib/api";

export type AgentGroup = "coordination" | "analysis" | "support";
export type AgentDefinition = {
  id: string;
  name: string;
  description: string;
  group: AgentGroup;
  implementation: "model" | "rules" | "tools" | "workflow";
  availability: "available" | "not_integrated";
  enabled: boolean;
  configurable: boolean;
  required: boolean;
  capabilities: string[];
  used_in: string[];
  note: string;
};

export type AgentCatalog = { agents: AgentDefinition[]; total: number };

const endpoint = "/api/settings/agents";

export const loadAgentSettings = () => apiGet<AgentCatalog>(endpoint);
export const setAgentEnabled = (id: string, enabled: boolean) =>
  apiPatch<AgentDefinition>(`${endpoint}/${encodeURIComponent(id)}`, { enabled });

export function agentSettingsError(reason: unknown): string {
  const message = reason instanceof Error ? reason.message : "";
  if (/Failed to fetch|NetworkError|fetch failed/i.test(message)) {
    return "暂时连接不到后端服务，请确认服务已启动后重试。";
  }
  return /[\u4e00-\u9fff]/.test(message) ? message : "智能体设置暂不可用，请稍后重试。";
}
