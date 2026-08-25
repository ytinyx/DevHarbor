import Link from "next/link";

const navItems = [
  {
    "href": "/",
    "label": "DevHarbor"
  },
  {
    "href": "/repos",
    "label": "repos"
  },
  {
    "href": "/workspaces",
    "label": "workspaces"
  },
  {
    "href": "/rag",
    "label": "rag"
  },
  {
    "href": "/knowledge",
    "label": "knowledge"
  }
];

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <main className="min-h-screen">
      <div className="border-b border-line bg-white/85 px-4 py-3">
        <div className="flex flex-wrap items-center gap-2">
          <div className="mr-2 text-sm font-semibold text-ink">DevHarbor</div>
          {navItems.map((item) => (
            <Link key={item.href} href={item.href} className="rounded-md px-3 py-1.5 text-sm text-slate-600 transition hover:bg-teal-50 hover:text-teal-800">
              {item.label}
            </Link>
          ))}
        </div>
      </div>
      <div className="w-full p-3">{children}</div>
    </main>
  );
}
