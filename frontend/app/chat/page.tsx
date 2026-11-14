import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { Card, PageTitle, PrimaryButton } from "@/components/ui/card";
import { apiGet, apiPostStream } from "@/lib/api";
import type { Repository } from "@/lib/types";

const samples = [
  "最近一次自动检查为什么失败？",
  "帮我看看最近一次代码变更有哪些风险",
  "最近这个问题适合由谁处理？",
  "帮我整理本周研发进展",
  "解释一下这个项目的工具调用流程",
];

export default function ChatPage() {
  const [repos, setRepos] = useState<Repository[]>([]);
  const [repoId, setRepoId] = useState("");
  const [message, setMessage] = useState("最近一次自动检查为什么失败？");
  const [result, setResult] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    apiGet<Repository[]>("/api/repos").then((items) => {
      setRepos(items);
      setRepoId((current) => current || items[0]?.id || "");
    }).catch(() => setError("暂时无法读取项目，请检查后端服务是否启动。"));
  }, []);

  async function send() {
    setLoading(true);
    setError("");
    setResult("");
    try {
      await apiPostStream("/api/chat/stream", { repo_id: repoId, message, context: { time_range: "7d", messages: [] } }, (event, rawData) => {
        if (event === "delta") {
          const data = rawData as { content?: string };
          if (data.content) setResult((current) => current + data.content);
        }
        if (event === "final") {
          const data = rawData as { answer?: string };
          if (data.answer) setResult(data.answer);
        }
      });
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "暂时无法回答，请稍后再试。");
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <PageTitle
        title="智能助手"
        description="选择项目，用自己的话描述问题。助手会查看相关代码和资料，并给出分析建议。"
      />
      <Card>
        {error && <p role="alert" className="mb-4 rounded-md bg-rose-50 p-3 text-sm text-rose-700">{error}</p>}
        <select
          aria-label="选择提问项目"
          className="mb-3 w-full rounded-md border border-line bg-white px-3 py-2 text-sm"
          value={repoId}
          onChange={(event) => setRepoId(event.target.value)}
        >
          {!repos.length && <option value="">请先在“连接项目”中添加项目</option>}
          {repos.map((repo) => (
            <option key={repo.id} value={repo.id}>{repo.full_name}</option>
          ))}
        </select>
        <textarea
          aria-label="输入你的问题"
          placeholder="用自己的话说说你想了解什么"
          className="h-32 w-full rounded-md border border-line bg-white px-3 py-3 text-sm leading-6 outline-none transition focus:border-teal-500 focus:ring-2 focus:ring-teal-100"
          value={message}
          onChange={(event) => setMessage(event.target.value)}
        />

        <div className="mt-3 flex flex-wrap gap-2 text-xs text-slate-500">
          {samples.map((sample) => (
            <button
              key={sample}
              onClick={() => setMessage(sample)}
              className="rounded-full border border-line bg-panel px-3 py-1.5 transition hover:border-teal-200 hover:bg-teal-50"
            >
              {sample}
            </button>
          ))}
        </div>

        <PrimaryButton onClick={send} disabled={loading || !repoId || !message.trim()} className="mt-4">
          {loading ? "正在分析…" : "发送问题"}
        </PrimaryButton>

        {result && <div className="markdown-body mt-4 max-h-[560px] overflow-auto rounded-md border border-line bg-panel p-5 text-sm leading-7 text-slate-700"><ReactMarkdown remarkPlugins={[remarkGfm]}>{result}</ReactMarkdown></div>}
      </Card>
    </>
  );
}
