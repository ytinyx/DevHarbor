import { useCallback, useEffect, useId, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Check, ChevronDown, Cpu, LoaderCircle, RefreshCw, Settings2 } from "lucide-react";

import {
  activateModelProvider,
  loadModelProviders,
  MODEL_PROVIDERS_CHANGED_EVENT,
  modelProviderError,
  resetActiveModel,
  type ModelProviderSettings,
} from "@/lib/model-providers";

type ComposerModelSelectorProps = {
  disabled?: boolean;
  onPendingChange?: (pending: boolean) => void;
};

export function ComposerModelSelector({ disabled = false, onPendingChange }: ComposerModelSelectorProps) {
  const [settings, setSettings] = useState<ModelProviderSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [pending, setPending] = useState(false);
  const [open, setOpen] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const containerRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const mountedRef = useRef(false);
  const pendingRef = useRef(false);
  const requestRef = useRef(0);
  const pendingCallbackRef = useRef(onPendingChange);
  pendingCallbackRef.current = onPendingChange;
  const panelId = useId();

  const refresh = useCallback(async () => {
    if (pendingRef.current) return;
    const request = ++requestRef.current;
    setLoading(true);
    try {
      const next = await loadModelProviders();
      if (mountedRef.current && request === requestRef.current) {
        setSettings(next);
        setError("");
      }
    } catch (reason) {
      if (mountedRef.current && request === requestRef.current) setError(modelProviderError(reason));
    } finally {
      if (mountedRef.current && request === requestRef.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    const refreshOnEvent = () => { void refresh(); };
    refreshOnEvent();
    window.addEventListener("focus", refreshOnEvent);
    window.addEventListener(MODEL_PROVIDERS_CHANGED_EVENT, refreshOnEvent);
    return () => {
      mountedRef.current = false;
      ++requestRef.current;
      window.removeEventListener("focus", refreshOnEvent);
      window.removeEventListener(MODEL_PROVIDERS_CHANGED_EVENT, refreshOnEvent);
      if (pendingRef.current) pendingCallbackRef.current?.(false);
    };
  }, [refresh]);

  useEffect(() => {
    if (!open) return;
    const closeOutside = (event: PointerEvent) => {
      if (event.target instanceof Node && !containerRef.current?.contains(event.target)) setOpen(false);
    };
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      event.preventDefault();
      setOpen(false);
      triggerRef.current?.focus();
    };
    document.addEventListener("pointerdown", closeOutside);
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("pointerdown", closeOutside);
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, [open]);

  useEffect(() => { if (disabled) setOpen(false); }, [disabled]);

  const activeProvider = settings?.providers.find((provider) => provider.id === settings.active.provider_id);
  const activeModel = settings?.active.provider_id
    ? settings.active.model
    : settings?.environment.configured ? settings.environment.model : null;
  const activeName = settings?.active.provider_id ? activeProvider?.name || "供应商不可用" : "环境配置";
  const activeInvalid = Boolean(settings?.active.provider_id && (!activeProvider || !activeModel || !activeProvider.models.includes(activeModel)));
  const label = pending ? "切换中…" : activeInvalid ? "模型配置失效" : activeModel || (loading ? "读取模型…" : error && !settings ? "读取失败" : "选择模型");
  const busy = disabled || pending || loading;

  async function selectModel(providerId: string | null, model: string) {
    if (!settings || busy || pendingRef.current) return;
    const valid = providerId === null
      ? settings.environment.configured && settings.environment.model === model
      : settings.providers.some((provider) => provider.id === providerId && provider.models.includes(model));
    if (!valid) return;
    if (settings.active.provider_id === providerId && activeModel === model) { setOpen(false); return; }
    pendingRef.current = true;
    ++requestRef.current;
    setPending(true);
    setError("");
    setNotice("");
    pendingCallbackRef.current?.(true);
    try {
      const active = providerId === null ? await resetActiveModel() : await activateModelProvider(providerId, model);
      if (!mountedRef.current) return;
      setSettings((current) => current ? { ...current, active } : current);
      setNotice(`已切换到 ${model}，后续对话与分析将使用此模型。`);
      setOpen(false);
      triggerRef.current?.focus();
    } catch (reason) {
      if (mountedRef.current) setError(modelProviderError(reason));
    } finally {
      pendingRef.current = false;
      if (mountedRef.current) {
        setPending(false);
        pendingCallbackRef.current?.(false);
      }
    }
  }

  function modelButton(providerId: string | null, model: string) {
    const selected = settings?.active.provider_id === providerId && activeModel === model;
    return <button
      key={model}
      type="button"
      disabled={busy}
      aria-pressed={selected}
      title={model}
      onClick={() => { void selectModel(providerId, model); }}
      className={`flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-left text-xs transition disabled:opacity-50 ${selected ? "bg-teal-50 text-accent" : "text-slate-600 hover:bg-white"}`}
    ><span className="min-w-0 flex-1 break-all">{model}</span>{selected && <Check className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />}</button>;
  }

  return <div ref={containerRef} className="relative min-w-0 max-w-[180px]">
    <button
      ref={triggerRef}
      type="button"
      disabled={disabled || pending}
      aria-haspopup="dialog"
      aria-expanded={open}
      aria-controls={open ? panelId : undefined}
      aria-label={activeModel ? `当前模型：${activeName} · ${activeModel}，切换模型` : "选择模型"}
      title={activeModel ? `${activeName} · ${activeModel}` : "选择模型"}
      onClick={() => setOpen((current) => !current)}
      className="inline-flex h-7 max-w-full items-center gap-1.5 rounded-lg px-2 text-xs text-slate-500 transition hover:bg-white hover:text-ink disabled:opacity-60"
    >
      {pending || loading ? <LoaderCircle className="h-3.5 w-3.5 shrink-0 animate-spin" aria-hidden="true" /> : <Cpu className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />}
      <span className="truncate">{label}</span><ChevronDown className="h-3 w-3 shrink-0" aria-hidden="true" />
    </button>
    <span className="sr-only" role="status">{notice}</span>
    {open && <div id={panelId} role="dialog" aria-label="选择模型" className="absolute bottom-full left-0 z-50 mb-2 rounded-xl border border-line bg-surface p-2 shadow-xl" style={{ width: "min(20rem, calc(100vw - 3rem))" }}>
      <div className="flex items-start justify-between gap-2 px-2 py-2">
        <div><p className="text-sm font-medium text-ink">选择模型</p><p className="mt-1 text-[11px] leading-5 text-slate-500">切换全局默认模型，后续对话与分析生效。</p></div>
        <button type="button" onClick={() => { void refresh(); }} disabled={busy} title="刷新模型列表" aria-label="刷新模型列表" className="rounded-md p-1.5 text-slate-500 hover:bg-white disabled:opacity-50"><RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} aria-hidden="true" /></button>
      </div>
      {error && <div role="alert" className="mx-2 mb-2 text-xs leading-5 text-amber-700">{error}<button type="button" onClick={() => { void refresh(); }} disabled={busy} className="ml-2 underline disabled:opacity-50">重试</button></div>}
      {activeInvalid && <p className="mx-2 mb-2 text-xs leading-5 text-amber-700">当前模型配置不可用，请重新选择。</p>}
      <div className="max-h-[min(42vh,18rem)] overflow-y-auto overscroll-contain">
        {loading && !settings && <p role="status" className="px-2 py-4 text-xs text-slate-500">正在读取可用模型…</p>}
        {settings?.providers.map((provider) => <div key={provider.id} role="group" aria-label={provider.name} className="mb-2">
          <p className="px-2.5 pb-1 pt-2 text-[11px] font-medium text-slate-500">{provider.name}</p>
          {provider.models.length ? provider.models.map((model) => modelButton(provider.id, model)) : <p className="px-2.5 py-2 text-xs text-slate-500">尚未添加模型</p>}
        </div>)}
        {settings?.environment.configured && settings.environment.model && <div role="group" aria-label="环境配置" className="mb-2"><p className="px-2.5 pb-1 pt-2 text-[11px] font-medium text-slate-500">环境配置</p>{modelButton(null, settings.environment.model)}</div>}
        {!loading && settings && !settings.providers.some((provider) => provider.models.length) && !(settings.environment.configured && settings.environment.model) && <p className="px-2 py-4 text-xs leading-6 text-slate-500">还没有可选模型，先添加一个模型供应商。</p>}
      </div>
      <Link to="/settings" onClick={() => setOpen(false)} className="mt-1 flex items-center gap-2 border-t border-line px-2 py-2.5 text-xs text-accent"><Settings2 className="h-3.5 w-3.5" aria-hidden="true" />管理模型供应商</Link>
    </div>}
  </div>;
}
