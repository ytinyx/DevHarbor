import { apiDelete, apiGet, apiPatch, apiPost } from "@/lib/api";

export type ModelProvider = {
  id: string;
  name: string;
  base_url: string;
  protocol: "openai_compatible";
  models: string[];
  default_model: string;
  has_api_key: boolean;
  created_at: string;
};
export type ActiveModel = { provider_id: string | null; model: string | null };
export type ModelProviderSettings = {
  providers: ModelProvider[];
  active: ActiveModel;
  environment: { configured: boolean; model: string | null; base_url: string | null };
};
export type ModelProviderInput = {
  name: string;
  base_url: string;
  protocol: "openai_compatible";
  api_key?: string;
  clear_api_key?: boolean;
  models: string[];
  default_model: string;
};

const endpoint = "/api/settings/model-providers";
export const MODEL_PROVIDERS_CHANGED_EVENT = "devharbor:model-providers-changed";

async function notifyModelProviderChange<T>(operation: Promise<T>): Promise<T> {
  const result = await operation;
  if (typeof window !== "undefined") window.dispatchEvent(new Event(MODEL_PROVIDERS_CHANGED_EVENT));
  return result;
}

export const loadModelProviders = () => apiGet<ModelProviderSettings>(endpoint);
export const createModelProvider = (input: ModelProviderInput) => notifyModelProviderChange(apiPost<ModelProvider>(endpoint, input));
export const updateModelProvider = (id: string, input: ModelProviderInput) => notifyModelProviderChange(apiPatch<ModelProvider>(`${endpoint}/${encodeURIComponent(id)}`, input));
export const activateModelProvider = (provider_id: string, model: string) => notifyModelProviderChange(apiPost<ActiveModel>(`${endpoint}/activate`, { provider_id, model }));
export const resetActiveModel = () => notifyModelProviderChange(apiPost<ActiveModel>(`${endpoint}/reset-active`, {}));
export const discoverProviderModels = (input: { provider_id?: string; base_url: string; api_key?: string }) => apiPost<{ models: string[] }>(`${endpoint}/discover-models`, input);

export async function deleteModelProvider(id: string): Promise<void> {
  await notifyModelProviderChange(apiDelete(`${endpoint}/${encodeURIComponent(id)}`));
}

export function modelProviderError(reason: unknown): string {
  const message = reason instanceof Error ? reason.message : "";
  if (/Failed to fetch|NetworkError|fetch failed/i.test(message)) return "暂时连接不到后端服务，请确认服务已启动后重试。";
  // The API deliberately returns sanitized Chinese errors. Do not surface upstream
  // English response bodies, which may contain connection or credential details.
  return /[\u4e00-\u9fff]/.test(message) ? message : "操作未完成，请检查填写的信息或稍后重试。";
}
