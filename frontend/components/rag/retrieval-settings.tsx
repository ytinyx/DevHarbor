import { Check, FileSearch, Layers3, Search } from "lucide-react";
import { Link } from "react-router-dom";

import type { KnowledgeConfig, KnowledgeRuntime, ModelCatalog, RetrievalMethod } from "@/lib/rag";

type Props = {
  value: KnowledgeConfig;
  catalog: ModelCatalog | null;
  runtime?: KnowledgeRuntime;
  onChange: (value: KnowledgeConfig) => void;
  showChunking?: boolean;
};

const methods: { value: RetrievalMethod; label: string; note: string; icon: typeof Search }[] = [
  { value: "vector", label: "向量检索", note: "擅长理解语义相近的表达", icon: Layers3 },
  { value: "fulltext", label: "关键词检索", note: "适合专有名词与精确关键词", icon: FileSearch },
  { value: "hybrid", label: "混合检索", note: "融合语义与关键词结果", icon: Search }
];

export function RetrievalSettings({ value, catalog, runtime, onChange, showChunking = true }: Props) {
  const keywordOnly = runtime?.embedding.provider === "disabled";
  const rerankModels = catalog?.rerank_models ?? [];
  const rerankAvailable = !keywordOnly || rerankModels.some((model) => model.provider === "qwen_api" && model.available);
  const rerankEnabled = rerankAvailable && value.rerank_enabled;
  const update = <K extends keyof KnowledgeConfig,>(key: K, next: KnowledgeConfig[K]) => onChange({ ...value, [key]: next });

  return (
    <div className="space-y-7">
      {showChunking ? (
        <section>
          <h3 className="text-sm font-semibold text-ink">分段设置</h3>
          <p className="mt-1 text-xs text-slate-500">长文档会拆成小段，方便准确找到相关内容。不确定时保留当前设置。</p>
          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            <label className="text-xs font-medium text-slate-600">
              最大分段长度
              <input
                type="number"
                min={200}
                max={4000}
                value={value.chunk_size}
                onChange={(event) => update("chunk_size", Number(event.target.value))}
                className="mt-1.5 h-10 w-full rounded-md border border-line bg-white px-3 text-sm text-ink outline-none focus:border-teal-600"
              />
            </label>
            <label className="text-xs font-medium text-slate-600">
              分段重叠长度
              <input
                type="number"
                min={0}
                max={1000}
                value={value.chunk_overlap}
                onChange={(event) => update("chunk_overlap", Number(event.target.value))}
                className="mt-1.5 h-10 w-full rounded-md border border-line bg-white px-3 text-sm text-ink outline-none focus:border-teal-600"
              />
            </label>
          </div>
        </section>
      ) : null}

      <section>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="text-sm font-semibold text-ink">向量模型</h3>
          <Link to="/settings/retrieval" className="text-xs font-medium text-teal-700 hover:underline">配置检索模型</Link>
        </div>
        <p className="mt-2 break-words text-xs leading-6 text-slate-500">
          {keywordOnly ? "未启用语义检索，当前按关键词查找资料。" : `${runtime?.embedding.model ?? value.embedding_model} · ${runtime?.embedding.dimensions ?? value.embedding_dimensions} 维`}
        </p>
      </section>

      <section>
        <h3 className="text-sm font-semibold text-ink">检索设置</h3>
        <div className="mt-3 grid gap-2 sm:grid-cols-3">
          {methods.map((method) => {
            const Icon = method.icon;
            const disabled = keywordOnly && method.value !== "fulltext";
            const selected = (keywordOnly ? "fulltext" : value.retrieval_method) === method.value;
            return (
              <button
                key={method.value}
                type="button"
                disabled={disabled}
                aria-pressed={selected}
                onClick={() => update("retrieval_method", method.value)}
                className={`relative min-h-28 rounded-md border p-3 text-left transition disabled:opacity-50 ${selected ? "border-teal-600 bg-teal-50/60" : "border-line bg-white hover:enabled:border-slate-400"}`}
              >
                {selected ? <Check className="absolute right-2 top-2 h-4 w-4 text-teal-700" /> : null}
                <Icon className={`h-5 w-5 ${selected ? "text-teal-700" : "text-slate-500"}`} />
                <span className="mt-3 block text-sm font-medium text-ink">{method.label}</span>
                <span className="mt-1 block text-xs leading-5 text-slate-500">{disabled ? "需先启用语义模型" : method.note}</span>
              </button>
            );
          })}
        </div>
      </section>

      <section className="border-t border-line pt-5">
        <div className="flex items-center justify-between gap-4">
          <div>
            <h3 className="text-sm font-semibold text-ink">结果排序模型</h3>
            <p className="mt-1 text-xs text-slate-500">{rerankAvailable ? "将更相关的资料排在前面。模型服务不可用时，会使用基础规则排序。" : "配置并启用重排服务后，可对关键词检索结果重新排序。"}</p>
          </div>
          <button
            type="button"
            role="switch"
            aria-checked={rerankEnabled}
            aria-label="启用结果重排"
            disabled={!rerankAvailable}
            onClick={() => update("rerank_enabled", !value.rerank_enabled)}
            className={`relative h-6 w-11 shrink-0 rounded-full transition disabled:opacity-50 ${rerankEnabled ? "bg-teal-700" : "bg-slate-300"}`}
          >
            <span className={`absolute top-1 h-4 w-4 rounded-full bg-white transition ${rerankEnabled ? "left-6" : "left-1"}`} />
          </button>
        </div>
        {rerankEnabled ? (
          <select
            aria-label="选择重排模型"
            value={`${value.rerank_provider}::${value.rerank_model}`}
            onChange={(event) => {
              const [provider, model] = event.target.value.split("::");
              onChange({ ...value, rerank_provider: provider, rerank_model: model });
            }}
            className="mt-3 h-10 w-full rounded-md border border-line bg-white px-3 text-sm text-ink outline-none focus:border-teal-600"
          >
            {rerankModels.map((model) => (
              <option key={`${model.provider}-${model.model}`} value={`${model.provider}::${model.model}`}>
                {model.label}{model.available ? "" : " · 当前不可用"}
              </option>
            ))}
            {!rerankModels.some((model) => model.provider === value.rerank_provider && model.model === value.rerank_model) ? (
              <option value={`${value.rerank_provider}::${value.rerank_model}`}>{value.rerank_model}</option>
            ) : null}
          </select>
        ) : null}
      </section>

      <section className="grid gap-4 border-t border-line pt-5 sm:grid-cols-2">
        <label className="text-xs font-medium text-slate-600">
          最多返回几条资料
          <div className="mt-2 flex items-center gap-3">
            <input type="range" min={1} max={10} value={value.top_k} onChange={(event) => update("top_k", Number(event.target.value))} className="min-w-0 flex-1 accent-teal-700" />
            <input type="number" min={1} max={20} value={value.top_k} onChange={(event) => update("top_k", Number(event.target.value))} className="h-9 w-16 rounded-md border border-line text-center text-sm outline-none focus:border-teal-600" />
          </div>
        </label>
        <div>
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-600">最低相关程度</span>
            <input type="checkbox" checked={value.score_threshold_enabled} onChange={(event) => update("score_threshold_enabled", event.target.checked)} className="h-4 w-4 accent-teal-700" />
          </div>
          <div className="mt-2 flex items-center gap-3">
            <input type="range" min={0} max={1} step={0.01} disabled={!value.score_threshold_enabled} value={value.score_threshold} onChange={(event) => update("score_threshold", Number(event.target.value))} className="min-w-0 flex-1 accent-teal-700 disabled:opacity-40" />
            <span className="w-12 text-right text-sm text-slate-600">{value.score_threshold.toFixed(2)}</span>
          </div>
        </div>
      </section>
    </div>
  );
}
