import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { LoaderCircle } from "lucide-react";
import { Link } from "react-router-dom";

import { apiGet, apiPost, apiPut } from "@/lib/api";
import { displayLabel } from "@/lib/display";
import styles from "../settings.module.css";

const endpoint = "/api/settings/retrieval-models";

type EmbeddingProvider = "openai_compatible" | "local";
type VectorBackend = "milvus" | "pgvector";
type EmbeddingModel = {
  provider: EmbeddingProvider;
  model: string;
  dimensions: number;
  base_url: string | null;
};
type VectorStoreInput =
  | { vector_backend: "milvus"; milvus_uri: string; milvus_token?: string; clear_milvus_token?: boolean }
  | { vector_backend: "pgvector" };
type VectorStoreTest = { ready: boolean; message: string };
type RerankInput = { base_url: string; model: string };
type RetrievalModels = {
  embedding: (EmbeddingModel & { vector_backend?: VectorBackend; milvus_uri?: string | null; has_api_key: boolean; has_milvus_token: boolean }) | null;
  rerank: (RerankInput & { has_api_key: boolean }) | null;
  restart_required: boolean;
  activation_error?: string | null;
};
type Update =
  | { embedding: (EmbeddingModel & VectorStoreInput & { api_key?: string }) | null }
  | { rerank: (RerankInput & { api_key?: string }) | null };
type Section = "embedding" | "rerank";

function embeddingDraft(saved: RetrievalModels["embedding"]) {
  const provider: EmbeddingProvider = saved?.provider ?? "openai_compatible";
  const vectorBackend: VectorBackend = saved?.vector_backend ?? "milvus";
  return {
    provider,
    vectorBackend,
    model: saved?.model ?? "",
    dimensions: saved ? String(saved.dimensions) : "",
    baseUrl: saved?.base_url ?? "",
    milvusUri: saved?.milvus_uri ?? "http://localhost:19530",
    apiKey: "",
    milvusToken: "",
    clearMilvusToken: false,
  };
}

function rerankDraft(saved: RetrievalModels["rerank"]) {
  return { baseUrl: saved?.base_url ?? "", model: saved?.model ?? "qwen3-rerank", apiKey: "" };
}

function sameAddress(previous: string | null | undefined, next: string, suffix?: string) {
  let address = next.trim().replace(/\/+$/, "");
  if (suffix && address.endsWith(suffix)) address = address.slice(0, -suffix.length);
  return previous === address;
}

function Field({ id, label, hint, children }: { id: string; label: string; hint?: string; children: ReactNode }) {
  return <div className={styles.settingRow}>
    <div className={styles.label}><label htmlFor={id}>{label}</label>{hint && <p id={`${id}-hint`}>{hint}</p>}</div>
    <div className={styles.control}>{children}</div>
  </div>;
}

export default function RetrievalModelsPage() {
  const [settings, setSettings] = useState<RetrievalModels | null>(null);
  const [embedding, setEmbedding] = useState(() => embeddingDraft(null));
  const [rerank, setRerank] = useState(() => rerankDraft(null));
  const [loadError, setLoadError] = useState("");
  const [busy, setBusy] = useState<Section | null>(null);
  const [feedback, setFeedback] = useState<{ section: Section; message: string; error: boolean } | null>(null);
  const [vectorStoreTest, setVectorStoreTest] = useState<VectorStoreTest | "checking" | null>(null);

  useEffect(() => {
    let disposed = false;
    apiGet<RetrievalModels>(endpoint).then((data) => {
      if (disposed) return;
      setSettings(data);
      setEmbedding(embeddingDraft(data.embedding));
      setRerank(rerankDraft(data.rerank));
    }).catch((reason: unknown) => {
      if (!disposed) setLoadError(reason instanceof Error ? reason.message : "无法读取检索模型配置。");
    });
    return () => { disposed = true; };
  }, []);

  const local = embedding.provider === "local";
  const useMilvus = embedding.vectorBackend === "milvus";
  const embeddingKeySaved = Boolean(settings?.embedding?.has_api_key && sameAddress(settings.embedding.base_url, embedding.baseUrl, "/embeddings"));
  const rerankKeySaved = Boolean(settings?.rerank?.has_api_key && sameAddress(settings.rerank.base_url, rerank.baseUrl, "/reranks"));
  const milvusTokenSaved = Boolean(settings?.embedding?.has_milvus_token);
  const milvusAddressChanged = milvusTokenSaved && !sameAddress(settings?.embedding?.milvus_uri, embedding.milvusUri);

  async function save(update: Update) {
    if (busy) return;
    const section = "embedding" in update ? "embedding" : "rerank";
    setBusy(section);
    setFeedback(null);
    try {
      const data = await apiPut<RetrievalModels>(endpoint, update);
      setSettings(data);
      if (section === "embedding") setEmbedding(embeddingDraft(data.embedding));
      else setRerank(rerankDraft(data.rerank));
      setFeedback({ section, message: "配置已保存。", error: false });
    } catch (reason) {
      setFeedback({ section, message: reason instanceof Error ? reason.message : "保存失败。", error: true });
    } finally {
      setBusy(null);
    }
  }

  function changeProvider(provider: EmbeddingProvider) {
    setEmbedding({
      ...embedding,
      provider,
      model: provider === "local" ? "Qwen/Qwen3-Embedding-0.6B" : "",
      dimensions: provider === "local" ? "1024" : "",
      baseUrl: "",
      apiKey: "",
    });
  }

  async function testPgvector() {
    if (vectorStoreTest === "checking") return;
    setVectorStoreTest("checking");
    try {
      setVectorStoreTest(await apiPost<VectorStoreTest>(`${endpoint}/test-vector-store`, { vector_backend: "pgvector" }));
    } catch (reason) {
      setVectorStoreTest({ ready: false, message: reason instanceof Error ? reason.message : "测试连接失败。" });
    }
  }

  function saveEmbedding(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (useMilvus && milvusAddressChanged && !embedding.milvusToken.trim() && !embedding.clearMilvusToken) {
      setFeedback({ section: "embedding", message: "Milvus 地址已修改。请填写新地址的令牌，或移除原令牌。", error: true });
      return;
    }
    const vectorStore: VectorStoreInput = useMilvus ? {
      vector_backend: "milvus",
      milvus_uri: embedding.milvusUri.trim(),
      ...(embedding.milvusToken.trim() ? { milvus_token: embedding.milvusToken.trim() } : {}),
      ...(embedding.clearMilvusToken ? { clear_milvus_token: true } : {}),
    } : { vector_backend: "pgvector" };
    void save({ embedding: {
      provider: embedding.provider,
      model: embedding.model.trim(),
      dimensions: Number(embedding.dimensions),
      base_url: local ? null : embedding.baseUrl.trim(),
      ...(!local && embedding.apiKey.trim() ? { api_key: embedding.apiKey.trim() } : {}),
      ...vectorStore,
    } });
  }

  function saveRerank(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void save({ rerank: {
      base_url: rerank.baseUrl.trim(),
      model: rerank.model.trim(),
      ...(rerank.apiKey.trim() ? { api_key: rerank.apiKey.trim() } : {}),
    } });
  }

  function feedbackFor(section: Section) {
    if (feedback?.section !== section) return null;
    return <div role={feedback.error ? "alert" : "status"} className={feedback.error ? styles.error : styles.notice}>{feedback.message}</div>;
  }

  return <section className={styles.content} aria-labelledby="retrieval-models-heading">
    <header className={styles.pageHeader}>
      <h2 id="retrieval-models-heading">检索模型</h2>
      <p>为当前应用配置知识库使用的向量模型与重排模型。</p>
    </header>
    {loadError && <div role="alert" className={styles.error}>{loadError}</div>}
    {!settings && !loadError && <p role="status" className={styles.loading}><LoaderCircle size={16} className="animate-spin" />正在读取配置…</p>}
    {settings?.activation_error && <div role="alert" className={styles.error}>{settings.activation_error}</div>}
    {settings?.restart_required && <div role="status" className={styles.notice}>配置已保存。退出并重新打开桌面应用，或重启当前后端服务后生效。</div>}

    {settings && <>
      <form className={styles.retrievalForm} aria-labelledby="embedding-heading" onSubmit={saveEmbedding}>
        <div className={styles.retrievalSectionHeader}>
          <h3 id="embedding-heading">向量模型（Embedding）</h3>
          <p className={styles.hint}>更换向量模型或存储并重启后，在<Link to="/knowledge">项目知识</Link>中重建已有资料的向量索引。</p>
        </div>
        <fieldset className={styles.fields} disabled={busy !== null}>
          <Field id="embedding-provider" label="接入方式" hint={local ? "本地模型需要在后端 Python 环境安装 sentence-transformers。" : "使用提供 OpenAI 兼容 /embeddings 接口的服务。"}>
            <select id="embedding-provider" aria-describedby="embedding-provider-hint" className={styles.input} value={embedding.provider} onChange={(event) => changeProvider(event.target.value as EmbeddingProvider)}>
              <option value="openai_compatible">OpenAI 兼容 API</option>
              <option value="local">本地模型</option>
            </select>
          </Field>
          {!local && <>
            <Field id="embedding-url" label="API 地址">
              <input id="embedding-url" type="url" className={styles.input} required autoComplete="off" spellCheck={false} value={embedding.baseUrl} onChange={(event) => setEmbedding({ ...embedding, baseUrl: event.target.value })} placeholder="https://你的服务地址/v1" />
            </Field>
            <Field id="embedding-key" label="API 密钥">
              <input id="embedding-key" type="password" className={styles.input} required={!embeddingKeySaved} autoComplete="new-password" spellCheck={false} value={embedding.apiKey} onChange={(event) => setEmbedding({ ...embedding, apiKey: event.target.value })} placeholder={embeddingKeySaved ? "已保存密钥，留空保留" : "粘贴向量接口的 API 密钥"} />
            </Field>
          </>}
          <Field id="embedding-model" label="模型标识">
            <input id="embedding-model" className={styles.input} required maxLength={240} autoComplete="off" spellCheck={false} value={embedding.model} onChange={(event) => setEmbedding({ ...embedding, model: event.target.value })} placeholder={local ? "Qwen/Qwen3-Embedding-0.6B" : "填写服务商提供的模型 ID"} />
          </Field>
          <Field id="embedding-dimensions" label="向量维度" hint="填写模型实际输出的维度。">
            <input id="embedding-dimensions" type="number" min={64} max={4096} step={1} className={styles.input} required aria-describedby="embedding-dimensions-hint" value={embedding.dimensions} onChange={(event) => setEmbedding({ ...embedding, dimensions: event.target.value })} />
          </Field>
          <Field id="vector-backend" label="向量存储" hint={useMilvus ? "需要运行 Milvus，后端需安装 PyMilvus。" : "使用当前后端连接的 PostgreSQL，需要启用 vector 扩展。"}>
            <select id="vector-backend" className={styles.input} aria-describedby="vector-backend-hint" value={embedding.vectorBackend} disabled={vectorStoreTest === "checking"} onChange={(event) => {
              setEmbedding({ ...embedding, vectorBackend: event.target.value as VectorBackend });
              setVectorStoreTest(null);
            }}>
              <option value="milvus">{displayLabel("milvus")}</option>
              <option value="pgvector">{displayLabel("pgvector")}</option>
            </select>
            {!useMilvus && <div className={styles.vectorStoreCheck}>
              <button type="button" className={styles.button} disabled={vectorStoreTest === "checking"} onClick={() => void testPgvector()}>
                {vectorStoreTest === "checking" && <LoaderCircle size={14} className="animate-spin" />}
                {vectorStoreTest === "checking" ? "正在测试…" : "测试连接"}
              </button>
              {vectorStoreTest && vectorStoreTest !== "checking" && <p role={vectorStoreTest.ready ? "status" : "alert"} className={vectorStoreTest.ready ? styles.vectorStoreReady : styles.warning}>{vectorStoreTest.message}</p>}
            </div>}
          </Field>
          {useMilvus && <>
            <Field id="milvus-uri" label="Milvus 地址">
              <input id="milvus-uri" type="url" className={styles.input} required autoComplete="off" spellCheck={false} value={embedding.milvusUri} onChange={(event) => setEmbedding({ ...embedding, milvusUri: event.target.value })} placeholder="http://localhost:19530" />
            </Field>
            <Field id="milvus-token" label="Milvus 令牌（可选）">
              <input id="milvus-token" type="password" className={styles.input} disabled={embedding.clearMilvusToken} autoComplete="new-password" spellCheck={false} value={embedding.milvusToken} onChange={(event) => setEmbedding({ ...embedding, milvusToken: event.target.value })} placeholder={milvusTokenSaved && !milvusAddressChanged && !embedding.clearMilvusToken ? "已保存令牌，留空保留" : "服务开启认证时填写"} />
              {milvusTokenSaved && <label className={styles.checkbox}><input type="checkbox" checked={embedding.clearMilvusToken} onChange={(event) => setEmbedding({ ...embedding, clearMilvusToken: event.target.checked, milvusToken: "" })} />移除已保存的令牌</label>}
            </Field>
          </>}
        </fieldset>
        {feedbackFor("embedding")}
        <div className={styles.formFooter}>
          <p>{settings.embedding ? "已保存自定义配置" : "当前使用应用默认配置"}</p>
          <div>
            {settings.embedding && <button type="button" className={styles.button} disabled={busy !== null} onClick={() => void save({ embedding: null })}>恢复默认</button>}
            <button type="submit" className={styles.primaryButton} disabled={busy !== null}>{busy === "embedding" ? "正在保存…" : "保存向量设置"}</button>
          </div>
        </div>
      </form>

      <form className={styles.retrievalForm} aria-labelledby="rerank-heading" onSubmit={saveRerank}>
        <div className={styles.retrievalSectionHeader}>
          <h3 id="rerank-heading">重排模型（Rerank）</h3>
          <p className={styles.hint}>重启后，在项目的知识库设置里启用「结果排序模型」。关键词检索也可以使用重排。</p>
        </div>
        <fieldset className={styles.fields} disabled={busy !== null}>
          <Field id="rerank-url" label="API 地址" hint="使用兼容 Qwen /reranks 的接口。">
            <input id="rerank-url" type="url" className={styles.input} required autoComplete="off" spellCheck={false} aria-describedby="rerank-url-hint" value={rerank.baseUrl} onChange={(event) => setRerank({ ...rerank, baseUrl: event.target.value })} placeholder="https://你的服务地址/reranks" />
          </Field>
          <Field id="rerank-key" label="API 密钥">
            <input id="rerank-key" type="password" className={styles.input} required={!rerankKeySaved} autoComplete="new-password" spellCheck={false} value={rerank.apiKey} onChange={(event) => setRerank({ ...rerank, apiKey: event.target.value })} placeholder={rerankKeySaved ? "已保存密钥，留空保留" : "粘贴重排接口的 API 密钥"} />
          </Field>
          <Field id="rerank-model" label="模型标识">
            <input id="rerank-model" className={styles.input} required maxLength={240} autoComplete="off" spellCheck={false} value={rerank.model} onChange={(event) => setRerank({ ...rerank, model: event.target.value })} placeholder="qwen3-rerank" />
          </Field>
        </fieldset>
        {feedbackFor("rerank")}
        <div className={styles.formFooter}>
          <p>{settings.rerank ? "已保存自定义配置" : "当前使用应用默认配置"}</p>
          <div>
            {settings.rerank && <button type="button" className={styles.button} disabled={busy !== null} onClick={() => void save({ rerank: null })}>恢复默认</button>}
            <button type="submit" className={styles.primaryButton} disabled={busy !== null}>{busy === "rerank" ? "正在保存…" : "保存重排模型"}</button>
          </div>
        </div>
      </form>
    </>}
  </section>;
}
