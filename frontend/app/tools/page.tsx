import { Link } from "react-router-dom";
import { ArrowUpRight, ChevronDown } from "lucide-react";

import { advancedTools, workTools, type ToolNavigationItem } from "@/lib/tool-navigation";

function ToolCard({ tool }: { tool: ToolNavigationItem }) {
  const Icon = tool.icon;
  const titleId = `tool-${tool.href.slice(1)}-title`;
  const descriptionId = `tool-${tool.href.slice(1)}-description`;

  return (
    <li className="min-w-0">
      <Link
        to={tool.href}
        aria-labelledby={titleId}
        aria-describedby={descriptionId}
        className="group flex h-full items-start gap-4 rounded-2xl border border-line bg-surface p-5 transition-colors hover:border-teal-300 hover:bg-teal-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-accent sm:p-6"
      >
        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-panel text-accent" aria-hidden="true">
          <Icon size={20} strokeWidth={1.7} />
        </span>
        <div className="min-w-0 flex-1">
          <h3 id={titleId} className="text-base font-medium text-ink">{tool.label}</h3>
          <p id={descriptionId} className="mt-2 text-sm leading-6 text-slate-500">{tool.description}</p>
        </div>
        <ArrowUpRight size={17} strokeWidth={1.7} className="mt-1 shrink-0 text-slate-400 transition-colors group-hover:text-accent" aria-hidden="true" />
      </Link>
    </li>
  );
}

export default function ToolsPage() {
  return (
    <div className="mx-auto w-full max-w-4xl pb-8">
      <header className="mb-9 pt-1">
        <h1 className="text-2xl font-semibold tracking-tight text-ink sm:text-3xl">工具箱</h1>
        <p className="mt-3 text-sm leading-6 text-slate-500">按需要选择工具，专注处理眼前的项目任务。</p>
      </header>

      <section aria-labelledby="work-tools-title">
        <h2 id="work-tools-title" className="mb-4 text-sm font-medium text-slate-600">日常工具</h2>
        <ul className="grid grid-cols-1 gap-3 md:grid-cols-2">
          {workTools.map((tool) => <ToolCard key={tool.href} tool={tool} />)}
        </ul>
      </section>

      <details className="group/advanced mt-8 border-t border-line pt-2">
        <summary className="flex cursor-pointer list-none items-center justify-between gap-4 rounded-lg py-4 text-sm text-slate-600 transition-colors hover:text-ink [&::-webkit-details-marker]:hidden">
          <span>进阶工具</span>
          <ChevronDown size={18} className="shrink-0 transition-transform group-open/advanced:rotate-180" aria-hidden="true" />
        </summary>
        <ul className="grid grid-cols-1 gap-3 pt-1 md:grid-cols-2">
          {advancedTools.map((tool) => <ToolCard key={tool.href} tool={tool} />)}
        </ul>
      </details>
    </div>
  );
}
