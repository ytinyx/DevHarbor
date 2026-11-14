import { useEffect, useMemo, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { Card, PageTitle, PrimaryButton } from "@/components/ui/card";
import { apiGet, apiPost } from "@/lib/api";
import type { Repository } from "@/lib/types";

type WeeklyReportResponse = {
  report_markdown: string;
};

function toDateInput(date: Date) {
  return date.toISOString().slice(0, 10);
}

export default function ReportsPage() {
  const today = useMemo(() => new Date(), []);
  const weekStart = useMemo(() => {
    const date = new Date(today);
    date.setDate(date.getDate() - 6);
    return date;
  }, [today]);

  const [repos, setRepos] = useState<Repository[]>([]);
  const [repoId, setRepoId] = useState("");
  const [startDate, setStartDate] = useState(toDateInput(weekStart));
  const [endDate, setEndDate] = useState(toDateInput(today));
  const [report, setReport] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    apiGet<Repository[]>("/api/repos")
      .then((items) => {
        setRepos(items);
        setRepoId(items[0]?.id || "");
      })
      .catch(() => setRepos([]));
  }, []);

  async function generateReport() {
    if (!repoId) return;
    setLoading(true);
    try {
      const data = await apiPost<WeeklyReportResponse>("/api/reports/weekly", {
        repo_id: repoId,
        start_date: startDate,
        end_date: endDate
      });
      setReport(data.report_markdown);
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <PageTitle title="研发周报生成" description="选择项目和时间范围，汇总问题处理、代码变更和自动检查情况，生成研发周报。" />

      <div className="grid gap-4 lg:grid-cols-[360px_1fr]">
        <Card>
          <div className="grid gap-4">
            <label className="text-sm font-medium text-slate-700">
              仓库
              <select
                className="mt-2 w-full rounded-md border border-line bg-white px-3 py-2 outline-none transition focus:border-teal-500 focus:ring-2 focus:ring-teal-100"
                value={repoId}
                onChange={(event) => setRepoId(event.target.value)}
              >
                {repos.map((repo) => (
                  <option key={repo.id} value={repo.id}>
                    {repo.full_name}
                  </option>
                ))}
              </select>
            </label>

            <label className="text-sm font-medium text-slate-700">
              开始日期
              <input
                type="date"
                className="mt-2 w-full rounded-md border border-line bg-white px-3 py-2 outline-none transition focus:border-teal-500 focus:ring-2 focus:ring-teal-100"
                value={startDate}
                onChange={(event) => setStartDate(event.target.value)}
              />
            </label>

            <label className="text-sm font-medium text-slate-700">
              结束日期
              <input
                type="date"
                className="mt-2 w-full rounded-md border border-line bg-white px-3 py-2 outline-none transition focus:border-teal-500 focus:ring-2 focus:ring-teal-100"
                value={endDate}
                onChange={(event) => setEndDate(event.target.value)}
              />
            </label>

            <PrimaryButton onClick={generateReport} disabled={!repoId || loading}>
              {loading ? "生成中..." : "生成周报"}
            </PrimaryButton>
          </div>
        </Card>

        <Card>
          <h2 className="font-semibold text-ink">周报内容</h2>
          {report ? (
            <div className="markdown-body mt-4 max-h-[640px] overflow-auto rounded-md border border-line bg-panel p-5 text-sm leading-7 text-slate-700"><ReactMarkdown remarkPlugins={[remarkGfm]}>{report}</ReactMarkdown></div>
          ) : (
            <div className="mt-4 rounded-md border border-line bg-panel p-4 text-sm text-slate-600">选择仓库和时间范围后生成周报。</div>
          )}
        </Card>
      </div>
    </>
  );
}
