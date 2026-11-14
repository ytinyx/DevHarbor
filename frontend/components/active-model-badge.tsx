import { Link } from "react-router-dom";
import { useEffect, useState } from "react";
import { Settings2 } from "lucide-react";
import { apiGet } from "@/lib/api";
import { MODEL_PROVIDERS_CHANGED_EVENT } from "@/lib/model-providers";

type ModelStatus = {
  providers: Array<{ id: string; name: string }>;
  active: { provider_id: string | null; model: string | null };
  environment: { configured: boolean; model: string | null };
};

export function ActiveModelBadge() {
  const [status, setStatus] = useState<ModelStatus | null>(null);
  useEffect(() => {
    let live = true;
    const refresh = () => { void apiGet<ModelStatus>("/api/settings/model-providers").then((data) => { if (live) setStatus(data); }).catch(() => { if (live) setStatus(null); }); };
    refresh();
    window.addEventListener("focus", refresh);
    window.addEventListener(MODEL_PROVIDERS_CHANGED_EVENT, refresh);
    return () => { live = false; window.removeEventListener("focus", refresh); window.removeEventListener(MODEL_PROVIDERS_CHANGED_EVENT, refresh); };
  }, []);
  const provider = status?.providers.find((item) => item.id === status.active.provider_id);
  const model = status?.active.model || (status?.environment.configured ? status.environment.model : null);
  const title = model ? `${provider?.name || "环境配置"} · ${model}` : status ? "尚未配置模型，点击添加供应商" : "打开模型设置";
  return <Link to="/settings" title={title} className="inline-flex min-w-0 max-w-full items-center gap-1.5 rounded-lg border border-line px-2.5 py-1.5 text-xs text-slate-500 transition hover:border-teal-300 hover:text-accent"><Settings2 className="h-3.5 w-3.5 shrink-0" /><span className="truncate">{model ? `模型：${model}` : "配置模型"}</span></Link>;
}
