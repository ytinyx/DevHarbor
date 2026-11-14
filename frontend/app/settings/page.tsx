import { Link } from "react-router-dom";
import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { ArrowLeft, ArrowRight, Check, Eye, EyeOff, LoaderCircle, Plus, RefreshCw, Trash2, X } from "lucide-react";

import styles from "./settings.module.css";
import { activateModelProvider, createModelProvider, deleteModelProvider, discoverProviderModels, loadModelProviders, modelProviderError, resetActiveModel, updateModelProvider, type ModelProvider, type ModelProviderInput, type ModelProviderSettings } from "@/lib/model-providers";

type ProviderPreset = { id: string; name: string; baseUrl: string; note: string; helpUrl: string };
const providerPresets: ProviderPreset[] = [
  { id: "deepseek", name: "DeepSeek", baseUrl: "https://api.deepseek.com", note: "填写你的 DeepSeek API 密钥，再获取或添加可用的聊天模型。", helpUrl: "https://api-docs.deepseek.com/en/" },
  { id: "qwen", name: "通义千问（北京）", baseUrl: "https://dashscope.aliyuncs.com/compatible-mode/v1", note: "此处预填北京地域地址。密钥与服务地域需要一致，其他地域请按官方说明修改地址。", helpUrl: "https://help.aliyun.com/en/model-studio/base-url" },
  { id: "kimi", name: "Kimi（月之暗面）", baseUrl: "https://api.moonshot.cn/v1", note: "填写月之暗面开放平台的 API 密钥，再选择支持聊天的模型。", helpUrl: "https://platform.kimi.com/docs/api/overview" },
  { id: "openai", name: "OpenAI", baseUrl: "https://api.openai.com/v1", note: "请选用支持 Chat Completions 和工具调用的聊天模型。列表中也可能包含其他用途的模型。", helpUrl: "https://developers.openai.com/api/reference/resources/models/methods/list" },
];
type EditorState = { provider: ModelProvider | null; name: string; baseUrl: string; apiKey: string; models: string[]; defaultModel: string; clearKey: boolean };
const emptyEditor = (): EditorState => ({ provider: null, name: "", baseUrl: "", apiKey: "", models: [], defaultModel: "", clearKey: false });
const inputClass = styles.input;
const secondaryButton = styles.button;

function validateBaseUrl(value: string): string | null {
  try {
    const url = new URL(value);
    if (!["http:", "https:"].includes(url.protocol) || url.username || url.password || url.search || url.hash) return "请填写完整的 http 或 https 接口地址，不要在地址中附带密钥、参数或账号密码。";
    if (/\/(chat\/completions|models|messages|responses)\/?$/i.test(url.pathname)) return "请填写 API 根地址，不需要添加 /chat/completions、/models 或其他接口路径。";
  } catch { return "请填写有效的 API 地址，例如 https://你的服务地址/v1。"; }
  return null;
}

export default function SettingsPage() {
  const [settings, setSettings] = useState<ModelProviderSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [pageError, setPageError] = useState("");
  const [notice, setNotice] = useState("");
  const [editor, setEditor] = useState<EditorState | null>(null);
  const [formError, setFormError] = useState("");
  const [formNotice, setFormNotice] = useState("");
  const [mode, setMode] = useState<"preset" | "custom">("custom");
  const [presetId, setPresetId] = useState("");
  const [showKey, setShowKey] = useState(false);
  const [modelDraft, setModelDraft] = useState("");
  const [saving, setSaving] = useState(false);
  const [discovering, setDiscovering] = useState(false);
  const [busyProvider, setBusyProvider] = useState<string | null>(null);
  const [modelChoices, setModelChoices] = useState<Record<string, string>>({});
  const [deleteTarget, setDeleteTarget] = useState<ModelProvider | null>(null);
  const editorHeading = useRef<HTMLHeadingElement>(null);
  const listHeading = useRef<HTMLHeadingElement>(null);
  const wasEditorOpen = useRef(false);
  const deleteDialog = useRef<HTMLDialogElement>(null);
  const formBusy = saving || discovering;
  const listBusy = loading || saving || Boolean(busyProvider);
  const editorOpen = Boolean(editor);
  const editingProviderId = editor?.provider?.id;
  const selectedPreset = providerPresets.find((item) => item.id === presetId);
  const deleteDialogOpen = Boolean(deleteTarget);

  const refresh = useCallback(async () => {
    const result = await loadModelProviders();
    setSettings(result);
    setModelChoices((current) => Object.fromEntries(result.providers.map((provider) => [provider.id, provider.models.includes(current[provider.id]) ? current[provider.id] : result.active.provider_id === provider.id && result.active.model ? result.active.model : provider.default_model])));
    return result;
  }, []);
  useEffect(() => {
    refresh().catch((reason) => setPageError(modelProviderError(reason))).finally(() => setLoading(false));
  }, [refresh]);
  useEffect(() => {
    if (editorOpen) editorHeading.current?.focus();
    else if (wasEditorOpen.current) listHeading.current?.focus();
    wasEditorOpen.current = editorOpen;
  }, [editingProviderId, editorOpen]);
  useEffect(() => {
    const dialog = deleteDialog.current;
    if (!deleteDialogOpen || !dialog) return;
    const previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const fallbackFocus = listHeading.current;
    dialog.showModal();
    return () => { dialog.close(); if (previousFocus?.isConnected) previousFocus.focus(); else fallbackFocus?.focus(); };
  }, [deleteDialogOpen]);

  const activeProvider = settings?.providers.find((provider) => provider.id === settings.active.provider_id);
  const editingUrlChanged = Boolean(editor?.provider && editor.baseUrl.trim().replace(/\/+$/, "") !== editor.provider.base_url.replace(/\/+$/, ""));
  const mustReplaceKey = Boolean(editor?.provider?.has_api_key && editingUrlChanged && !editor.clearKey);

  function beginCreate() {
    setEditor(emptyEditor()); setMode(providerPresets.length ? "preset" : "custom"); setPresetId(""); setShowKey(false); setModelDraft(""); setFormError(""); setFormNotice(""); setNotice("");
  }
  function beginEdit(provider: ModelProvider) {
    setEditor({ provider, name: provider.name, baseUrl: provider.base_url, apiKey: "", models: [...provider.models], defaultModel: provider.default_model, clearKey: false });
    setMode("custom"); setPresetId(""); setShowKey(false); setModelDraft(""); setFormError(""); setFormNotice(""); setNotice("");
  }
  function closeEditor() { if (!formBusy) { setEditor(null); setShowKey(false); setModelDraft(""); setFormError(""); setFormNotice(""); } }
  function patchEditor(patch: Partial<EditorState>) { setEditor((current) => current ? { ...current, ...patch } : current); setFormError(""); }
  function choosePreset(id: string) {
    setPresetId(id);
    const preset = providerPresets.find((item) => item.id === id);
    if (!preset) return;
    setEditor((current) => current ? { ...current, name: preset.name, baseUrl: preset.baseUrl, apiKey: "", models: [], defaultModel: "", clearKey: false } : current);
    setShowKey(false); setModelDraft(""); setFormError(""); setFormNotice("");
  }
  function addModel() {
    const model = modelDraft.trim();
    if (!editor || !model) return;
    if (editor.models.length >= 200) { setFormError("每个供应商最多保存 200 个模型，请先移除不需要的模型。"); return; }
    if (model.length > 300) { setFormError("模型标识过长，请核对供应商提供的名称（最多 300 个字符）。"); return; }
    if (/\s/.test(model)) { setFormError("模型标识中不能包含空格，请复制供应商给出的完整模型 ID。"); return; }
    if (editor.models.includes(model)) { setFormError("这个模型已经在列表中了。"); return; }
    patchEditor({ models: [...editor.models, model], defaultModel: editor.defaultModel || model }); setModelDraft("");
  }
  function removeModel(model: string) {
    if (!editor) return;
    const models = editor.models.filter((item) => item !== model);
    patchEditor({ models, defaultModel: editor.defaultModel === model ? models[0] || "" : editor.defaultModel });
  }
  function connectionError(): string | null {
    if (!editor) return "请先填写供应商信息。";
    const urlError = validateBaseUrl(editor.baseUrl.trim());
    if (urlError) return urlError;
    if (mustReplaceKey && !editor.apiKey.trim()) return "API 地址已修改。请重新输入此地址对应的密钥，或明确移除原密钥。";
    return null;
  }
  async function discoverModels() {
    if (!editor) return;
    const error = connectionError();
    if (error) { setFormError(error); return; }
    if (editor.clearKey && !editor.apiKey.trim() && editor.provider?.has_api_key && !editingUrlChanged) {
      setFormError("如需移除旧密钥，请先保存，再重新打开并获取模型。也可以直接手动添加模型。"); return;
    }
    setDiscovering(true); setFormError(""); setFormNotice("");
    try {
      const data = await discoverProviderModels({ ...(editor.provider && !editor.clearKey ? { provider_id: editor.provider.id } : {}), base_url: editor.baseUrl.trim(), ...(editor.apiKey.trim() ? { api_key: editor.apiKey.trim() } : {}) });
      const allModels = Array.from(new Set([...editor.models, ...data.models])).filter(Boolean);
      const models = allModels.slice(0, 200);
      setEditor((current) => current ? { ...current, models, defaultModel: current.defaultModel || models[0] || "" } : current);
      setFormNotice(data.models.length ? `已读取 ${data.models.length} 个模型。${allModels.length > 200 ? "目录最多保留 200 个，已优先保留原有模型。" : ""}请保留需要的模型，并选择一个默认模型。` : "接口没有返回模型。你仍可以手动填写供应商提供的模型标识。");
    } catch (reason) { setFormError(modelProviderError(reason)); } finally { setDiscovering(false); }
  }
  async function saveProvider(event: FormEvent) {
    event.preventDefault();
    if (!editor || formBusy) return;
    const error = connectionError();
    if (error) { setFormError(error); return; }
    if (!editor.name.trim()) { setFormError("请给供应商起一个方便辨认的名称。"); return; }
    if (!editor.models.length || !editor.models.includes(editor.defaultModel)) { setFormError("请至少添加一个模型，并选择默认模型。"); return; }
    if (modelDraft.trim()) { setFormError("还有一个模型尚未加入列表，请点击“添加模型”，或清空该输入框后保存。"); return; }
    setSaving(true); setFormError("");
    const wasActive = Boolean(editor.provider && settings?.active.provider_id === editor.provider.id);
    const input: ModelProviderInput = { name: editor.name.trim(), base_url: editor.baseUrl.trim(), protocol: "openai_compatible", models: editor.models, default_model: editor.defaultModel, ...(editor.apiKey.trim() ? { api_key: editor.apiKey.trim() } : {}), ...(editor.provider && editor.clearKey ? { clear_api_key: true } : {}) };
    try {
      const provider = editor.provider ? await updateModelProvider(editor.provider.id, input) : await createModelProvider(input);
      setSettings((current) => current ? {
        ...current,
        providers: current.providers.some((item) => item.id === provider.id) ? current.providers.map((item) => item.id === provider.id ? provider : item) : [...current.providers, provider],
        active: current.active.provider_id === provider.id && !provider.models.includes(current.active.model || "") ? { provider_id: provider.id, model: provider.default_model } : current.active,
      } : current);
      setModelChoices((current) => ({ ...current, [provider.id]: provider.models.includes(current[provider.id]) ? current[provider.id] : provider.default_model }));
      setEditor(null); setShowKey(false); setModelDraft("");
      setNotice(wasActive ? `已更新正在使用的“${provider.name}”，后续请求将使用最新设置；若移除了当前模型，将改用供应商的默认模型。` : `已保存“${provider.name}”。在下方选择模型并点击“设为默认”，之后的新请求就会使用它。`);
      try { await refresh(); } catch { setPageError("供应商已保存，但列表刷新失败，请点击刷新查看最新状态。"); }
    } catch (reason) { setFormError(modelProviderError(reason)); } finally { setSaving(false); }
  }
  async function activate(provider: ModelProvider) {
    const model = modelChoices[provider.id] || provider.default_model;
    setBusyProvider(provider.id); setPageError(""); setNotice("");
    try {
      const active = await activateModelProvider(provider.id, model);
      setSettings((current) => current ? { ...current, active } : current);
      setNotice(`已将“${provider.name} · ${model}”设为默认，下次对话和分析时生效。`);
    } catch (reason) { setPageError(modelProviderError(reason)); } finally { setBusyProvider(null); }
  }
  async function resetDefault() {
    setBusyProvider("reset"); setPageError(""); setNotice("");
    try {
      const active = await resetActiveModel();
      setSettings((current) => current ? { ...current, active } : current);
      setNotice("已取消界面中的默认模型，恢复使用服务端原有配置。");
    } catch (reason) { setPageError(modelProviderError(reason)); } finally { setBusyProvider(null); }
  }
  async function confirmDelete() {
    if (!deleteTarget) return;
    setBusyProvider(deleteTarget.id); setPageError("");
    try {
      await deleteModelProvider(deleteTarget.id);
      setSettings((current) => current ? { ...current, providers: current.providers.filter((provider) => provider.id !== deleteTarget.id), active: current.active.provider_id === deleteTarget.id ? { provider_id: null, model: null } : current.active } : current);
      setDeleteTarget(null); setNotice("供应商已删除。");
    } catch (reason) { setPageError(modelProviderError(reason)); setDeleteTarget(null); } finally { setBusyProvider(null); }
  }

  return (
    <>
      <section id="api-settings" className={styles.content} aria-label="API 配置">
        {editor ? (
          <form onSubmit={saveProvider}>
            <header className={styles.editorHeader}>
              <button type="button" onClick={closeEditor} disabled={formBusy} aria-label="返回供应商列表" className={styles.iconButton}><ArrowLeft size={20} /></button>
              <div><h2 ref={editorHeading} tabIndex={-1}>{editor.provider ? "编辑供应商" : "添加模型供应商"}</h2><p>填写接口信息，添加你想使用的模型。</p></div>
            </header>

            <fieldset disabled={formBusy} className={styles.fields}>
              {!editor.provider && <div className={styles.settingRow}>
                <div className={styles.label}><span>接入方式</span><p>选择常用供应商，或填写自己的接口。</p></div>
                <div className={styles.control}>
                  <div className={styles.segmented} role="group" aria-label="添加方式">
                    <button type="button" aria-pressed={mode === "preset"} onClick={() => setMode("preset")}>常用供应商</button>
                    <button type="button" aria-pressed={mode === "custom"} onClick={() => setMode("custom")}>自定义接口</button>
                  </div>
                  {mode === "preset" && <>
                    <label className="sr-only" htmlFor="provider-preset">选择供应商</label>
                    <select id="provider-preset" className={inputClass} value={presetId} onChange={(event) => choosePreset(event.target.value)}><option value="">选择供应商…</option>{providerPresets.map((preset) => <option key={preset.id} value={preset.id}>{preset.name}</option>)}</select>
                    {selectedPreset && <p className={styles.hint}>{selectedPreset.note} <a href={selectedPreset.helpUrl} target="_blank" rel="noreferrer">接入说明 ↗</a></p>}
                  </>}
                </div>
              </div>}

              <div className={styles.settingRow}>
                <label htmlFor="provider-name" className={styles.label}>显示名称<p>给这个供应商起一个好记的名字。</p></label>
                <input id="provider-name" className={inputClass} value={editor.name} onChange={(event) => patchEditor({ name: event.target.value })} placeholder="例如：我的 DeepSeek" maxLength={80} required autoComplete="off" />
              </div>
              <div className={styles.settingRow}>
                <label htmlFor="provider-url" className={styles.label}>API 地址<p>填写根地址，无需添加 /chat/completions。</p></label>
                <input id="provider-url" className={inputClass} value={editor.baseUrl} onChange={(event) => patchEditor({ baseUrl: event.target.value })} placeholder="https://你的服务地址/v1" type="url" required autoComplete="off" spellCheck={false} />
              </div>
              <div className={styles.settingRow}>
                <label htmlFor="provider-api-key" className={styles.label}>API 密钥<p>无需密钥的本地服务可以留空。</p></label>
                <div className={styles.control}>
                  <div className={styles.secretInput}>
                    <input id="provider-api-key" className={inputClass} type={showKey ? "text" : "password"} value={editor.apiKey} onChange={(event) => patchEditor({ apiKey: event.target.value, clearKey: false })} placeholder={editor.provider?.has_api_key && !editor.clearKey ? "已保存密钥，留空不更换" : "粘贴 API 密钥"} autoComplete="new-password" spellCheck={false} />
                    <button type="button" aria-label={showKey ? "隐藏输入的密钥" : "显示输入的密钥"} onClick={() => setShowKey(!showKey)} className={styles.iconButton}>{showKey ? <EyeOff size={17} /> : <Eye size={17} />}</button>
                  </div>
                  {mustReplaceKey && <p className={styles.warning}>地址已修改，请重新输入密钥。原密钥不会发送到新地址。</p>}
                  {editor.provider?.has_api_key && <label className={styles.checkbox}><input type="checkbox" checked={editor.clearKey} onChange={(event) => patchEditor({ clearKey: event.target.checked, apiKey: "" })} />移除已保存的密钥</label>}
                </div>
              </div>
              <div className={styles.settingRow}>
                <div className={styles.label}>接口协议</div>
                <div className={styles.protocol}>OpenAI 兼容接口<span>支持 Chat Completions，暂不支持原生 Anthropic 接口。</span></div>
              </div>

              <div className={`${styles.settingRow} ${styles.modelsRow}`}>
                <div className={styles.label}>模型目录<p>从接口获取，或手动添加模型标识。</p></div>
                <div className={styles.control}>
                  <div className={styles.modelToolbar}>
                    <span>{editor.models.length ? `${editor.models.length} 个模型` : "尚未添加模型"}</span>
                    <button type="button" onClick={discoverModels} disabled={!editor.baseUrl.trim()} className={styles.textButton}>{discovering ? <LoaderCircle size={14} className="animate-spin" /> : <RefreshCw size={14} />}获取可用模型</button>
                  </div>
                  {editor.models.length > 0 && <div className={styles.modelList}>{editor.models.map((model) => <div key={model} className={styles.modelItem}>
                    <span>{model}</span>{editor.defaultModel === model && <small>默认</small>}
                    <button type="button" onClick={() => removeModel(model)} aria-label={`移除模型 ${model}`} className={styles.iconButton}><X size={16} /></button>
                  </div>)}</div>}
                  <div className={styles.modelEntry}>
                    <label className="sr-only" htmlFor="new-model-id">添加模型标识</label>
                    <input id="new-model-id" value={modelDraft} onChange={(event) => { setModelDraft(event.target.value); setFormError(""); }} onKeyDown={(event) => { if (event.key === "Enter" && !event.nativeEvent.isComposing) { event.preventDefault(); addModel(); } }} placeholder="输入供应商提供的模型标识" autoComplete="off" spellCheck={false} className={inputClass} />
                    <button type="button" onClick={addModel} disabled={!modelDraft.trim()} className={secondaryButton}><Plus size={16} />添加</button>
                  </div>
                </div>
              </div>
              {editor.models.length > 0 && <div className={styles.settingRow}>
                <label htmlFor="provider-default" className={styles.label}>默认模型<p>此供应商优先使用的模型。</p></label>
                <select id="provider-default" value={editor.defaultModel} onChange={(event) => patchEditor({ defaultModel: event.target.value })} className={inputClass}>{editor.models.map((model) => <option key={model} value={model}>{model}</option>)}</select>
              </div>}
              <details className={styles.help}>
                <summary>接入说明</summary>
                <p>密钥由后端保存，不会在供应商列表中显示。模型标识需要与供应商提供的名称完全一致，部分接口不支持获取列表，可以手动添加。</p>
                <p>获取列表只读取模型信息，不发送聊天内容，也不代表对话一定可用。实际使用还取决于账号权限、额度和模型支持的功能。</p>
              </details>
            </fieldset>

            {formError && <p role="alert" className={styles.error}>{formError}</p>}
            {formNotice && <p role="status" className={styles.notice}>{formNotice}</p>}
            <footer className={styles.formFooter}>
              <p>{editor.provider && settings?.active.provider_id === editor.provider.id ? "保存后，后续请求会使用最新设置。" : "保存后，可在列表中设为默认。"}</p>
              <div><button type="button" onClick={closeEditor} disabled={formBusy} className={secondaryButton}>取消</button><button type="submit" disabled={formBusy} className={styles.primaryButton}>{saving && <LoaderCircle size={16} className="animate-spin" />}保存</button></div>
            </footer>
          </form>
        ) : <>
          <header className={styles.pageHeader}>
            <h2 ref={listHeading} tabIndex={-1}>API 配置</h2>
            <p>连接模型供应商，选择用于对话和分析的模型。</p>
          </header>
          {pageError && <p role="alert" className={styles.error}>{pageError}</p>}
          {notice && <p role="status" className={styles.notice}>{notice}<button type="button" onClick={() => setNotice("")} aria-label="关闭提示" className={styles.iconButton}><X size={16} /></button></p>}

          <div className={styles.sectionHeader}>
            <h3>模型供应商</h3>
            <button type="button" disabled={listBusy} onClick={() => { setLoading(true); setPageError(""); refresh().catch((reason) => setPageError(modelProviderError(reason))).finally(() => setLoading(false)); }} className={styles.iconButton} aria-label="刷新供应商列表" title="刷新供应商列表"><RefreshCw size={16} className={loading ? "animate-spin" : ""} /></button>
          </div>
          {loading ? <p className={styles.loading}><LoaderCircle className="animate-spin" size={17} />正在读取设置…</p> : settings && <>
            {!settings.providers.length && <p className={styles.empty}>尚未添加模型供应商。</p>}
            <div className={styles.providers}>
              {settings.providers.map((provider) => {
                const choice = modelChoices[provider.id] || provider.default_model;
                const selected = settings.active.provider_id === provider.id && settings.active.model === choice;
                return <article key={provider.id} className={styles.providerRow}>
                  <div className={styles.providerInfo}><h4>{provider.name}{settings.active.provider_id === provider.id && <span title="当前默认模型来自此供应商" aria-label="默认供应商" className={styles.activeDot} />}</h4><p title={provider.base_url}>{provider.base_url}</p></div>
                  <select className={inputClass} aria-label={`${provider.name} 的模型`} value={choice} disabled={listBusy} onChange={(event) => setModelChoices((current) => ({ ...current, [provider.id]: event.target.value }))}>{provider.models.map((model) => <option value={model} key={model}>{model}</option>)}</select>
                  <button type="button" onClick={() => activate(provider)} disabled={selected || listBusy || !choice} className={selected ? styles.selectedButton : styles.button}>{busyProvider === provider.id ? <LoaderCircle size={14} className="animate-spin" /> : selected ? <Check size={14} /> : null}{selected ? "当前默认" : "设为默认"}</button>
                  <div className={styles.providerActions}>
                    <button type="button" disabled={listBusy} onClick={() => beginEdit(provider)} aria-label={`编辑供应商 ${provider.name}`} className={styles.textButton}>编辑</button>
                    <button type="button" disabled={listBusy} onClick={() => setDeleteTarget(provider)} aria-label={`删除供应商 ${provider.name}`} className={styles.deleteButton}><Trash2 size={15} /></button>
                  </div>
                </article>;
              })}
              <button type="button" onClick={beginCreate} disabled={listBusy} className={styles.addProvider}><Plus size={18} />添加模型供应商</button>
            </div>

            {(activeProvider || settings.environment.configured) && <div className={styles.currentModel}>
              <div><span>当前模型</span><p>{activeProvider ? `${activeProvider.name} · ${settings.active.model}` : `${settings.environment.model}（服务端配置）`}</p></div>
              {activeProvider && <button type="button" disabled={listBusy} onClick={resetDefault} className={styles.textButton}>{busyProvider === "reset" ? "正在切换…" : "恢复服务端配置"}</button>}
            </div>}
            {(activeProvider || settings.environment.configured) && <div className={styles.listFooter}><Link to="/workspace?new=1" className={styles.textButton}>返回工作台<ArrowRight size={15} /></Link></div>}
          </>}
        </>}
      </section>

      {deleteTarget && <dialog ref={deleteDialog} aria-labelledby="delete-provider-title" aria-describedby="delete-provider-description"
        onCancel={(event) => { if (busyProvider) event.preventDefault(); else setDeleteTarget(null); }}
        onClick={(event) => { if (event.target === event.currentTarget && !busyProvider) setDeleteTarget(null); }}
        className={styles.dialog}>
        <div className={styles.dialogBody}>
          <h2 id="delete-provider-title">删除这个供应商？</h2>
          <p id="delete-provider-description">“{deleteTarget.name}”的接口、模型目录和已保存的密钥都会被移除。{settings?.active.provider_id === deleteTarget.id ? "当前默认模型也会取消，并恢复服务端原有配置。" : "其他供应商不受影响。"}</p>
          <div><button type="button" autoFocus disabled={Boolean(busyProvider)} onClick={() => setDeleteTarget(null)} className={secondaryButton}>取消</button><button type="button" disabled={Boolean(busyProvider)} onClick={confirmDelete} className={styles.dangerButton}>{busyProvider ? <LoaderCircle size={16} className="animate-spin" /> : <Trash2 size={16} />}确认删除</button></div>
        </div>
      </dialog>}
    </>
  );
}
