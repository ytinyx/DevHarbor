import Link from "next/link";

export default function Home() {
  return (
    <section className="mx-auto max-w-4xl space-y-6 p-8">
      <p className="text-sm text-slate-500">v0.1.0</p>
      <h1 className="text-3xl font-semibold">DevHarbor</h1>
      <p>基础配置、数据模型和应用骨架</p>
      <ul className="space-y-3 text-teal-700">

      </ul>
      <p className="text-sm text-slate-500">后端健康检查：/health；API 文档：/docs。连接仓库和模型前，请配置本地环境。</p>
    </section>
  );
}
