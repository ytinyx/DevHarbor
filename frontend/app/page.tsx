import Link from "next/link";

export default function Home() {
  return (
    <section className="mx-auto max-w-4xl space-y-6 p-8">
      <p className="text-sm text-slate-500">v0.4.0</p>
      <h1 className="text-3xl font-semibold">DevHarbor</h1>
      <p>Issue、PR、CI Agent 和操作草稿</p>
      <ul className="space-y-3 text-teal-700">
        <li><Link href="/repos">repos</Link></li>
        <li><Link href="/workspaces">workspaces</Link></li>
        <li><Link href="/rag">rag</Link></li>
        <li><Link href="/knowledge">knowledge</Link></li>
        <li><Link href="/issues">issues</Link></li>
        <li><Link href="/pull-requests">pull-requests</Link></li>
        <li><Link href="/ci">ci</Link></li>
        <li><Link href="/reports">reports</Link></li>
        <li><Link href="/action-drafts">action-drafts</Link></li>
        <li><Link href="/code-graph">code-graph</Link></li>
      </ul>
      <p className="text-sm text-slate-500">后端健康检查：/health；API 文档：/docs。连接仓库和模型前，请配置本地环境。</p>
    </section>
  );
}
