import { Link, useLocation, useNavigate } from "react-router-dom";
import { useEffect, useState } from "react";
import { Anchor, BookOpen, CircleHelp, FolderGit2, Menu, Network, Plus, Settings, Wrench, X } from "lucide-react";
import { advancedTools, workTools } from "@/lib/tool-navigation";

const mainLinks = [
  { href: "/workspace", label: "协作工作台", icon: Network },
  { href: "/repos", label: "我的项目", icon: FolderGit2 },
  { href: "/knowledge", label: "项目知识", icon: BookOpen },
  { href: "/tools", label: "工具箱", icon: Wrench },
];
const toolLinks = [...workTools, ...advancedTools];
const settingsLinks = [{ href: "/settings", label: "设置", icon: Settings }];
const allLinks = [...mainLinks, ...toolLinks, ...settingsLinks];

export function AppShell({ children }: { children: React.ReactNode }) {
  const { pathname } = useLocation();
  const isSettings = pathname === "/settings" || pathname.startsWith("/settings/");
  const navigate = useNavigate();
  const [menuOpen, setMenuOpen] = useState(false);
  const [helpOpen, setHelpOpen] = useState(false);
  const current = allLinks.find((item) => item.href === pathname || (item.href !== "/" && pathname.startsWith(item.href + "/")));
  useEffect(() => {
    setMenuOpen(false);
  }, [pathname]);
  useEffect(() => {
    function close(event: KeyboardEvent) { if (event.key === "Escape") { setMenuOpen(false); setHelpOpen(false); } }
    window.addEventListener("keydown", close);
    return () => window.removeEventListener("keydown", close);
  }, []);
  function navigation(items: typeof mainLinks) {
    return items.map(({ href, label, icon: Icon }) => {
      const active = pathname === href || pathname.startsWith(href + "/") || (href === "/tools" && toolLinks.some((item) => pathname === item.href || pathname.startsWith(item.href + "/")));
      return <Link key={href} to={href} aria-current={active ? "page" : undefined} className={"shell-nav-link " + (active ? "is-active" : "")}><Icon size={18} strokeWidth={1.7} /><span>{label}</span>{active && <span className="nav-active-dot" />}</Link>;
    });
  }
  return (
    <div className={"app-shell" + (isSettings ? " settings-shell" : "") + (pathname === "/workspace" ? " workspace-shell" : "")}>
      <a href="#main-content" className="skip-link">跳到主要内容</a>
      {menuOpen && <button type="button" className="sidebar-backdrop" aria-label="关闭导航" onClick={() => setMenuOpen(false)} />}
      <aside className={"app-sidebar " + (menuOpen ? "is-open" : "")} aria-label="主导航">
        <Link to="/workspace" className="brand-lockup" aria-label="DevHarbor 工作台"><span className="brand-mark"><Anchor size={24} strokeWidth={1.7} /></span><span><strong>DevHarbor<span className="brand-dot">.</span></strong><small>多智能体研发助手</small></span></Link>
        <Link to="/workspace?new=1" onClick={(event) => { event.preventDefault(); setMenuOpen(false); navigate("/workspace?new=1&start=" + Date.now()); }} className="new-conversation"><Plus size={17} />新建任务</Link>
        <nav className="sidebar-navigation">
          {navigation(mainLinks)}
        </nav>
        <div className="sidebar-footer"><Link to="/settings" className={"sidebar-settings " + (isSettings ? "is-active" : "")} aria-label="设置" title="设置" aria-current={isSettings ? "page" : undefined} onClick={() => setMenuOpen(false)}><Settings size={20} strokeWidth={1.7} /></Link></div>
      </aside>
      <div className="app-main">
        <header className="app-topbar"><div className="topbar-location"><button type="button" className="mobile-menu-button" aria-label="打开导航" aria-expanded={menuOpen} onClick={() => setMenuOpen(true)}><Menu size={21} /></button><span className="topbar-prefix">工作空间</span><span className="topbar-divider">/</span><span>{current?.label || "研发助手"}</span></div><button type="button" className="topbar-help" onClick={() => setHelpOpen(true)}><CircleHelp size={16} /><span>使用指南</span></button></header>
        <main id="main-content" className={"app-content " + (pathname === "/workspace" ? "workspace-content " : "") + (isSettings ? "settings-content" : "")}>{children}</main>
      </div>
      {helpOpen && <div className="guide-backdrop" onClick={() => setHelpOpen(false)}><section role="dialog" aria-modal="true" aria-labelledby="guide-title" className="guide-dialog" onClick={(event) => event.stopPropagation()}><button type="button" className="guide-close" autoFocus aria-label="关闭使用指南" onClick={() => setHelpOpen(false)}><X size={20} /></button><span className="guide-eyebrow">从这里开始</span><h2 id="guide-title">三步，认识你的项目</h2><p className="guide-intro">不用记住专业术语，像和同事聊天一样描述你的问题。</p><ol className="guide-steps"><li><span>1</span><div><strong>连接一个项目</strong><p>在「我的项目」添加代码仓库，或进入已有项目。</p><Link to="/repos" onClick={() => setHelpOpen(false)}>管理我的项目 →</Link></div></li><li><span>2</span><div><strong>描述任务并确认分工</strong><p>例如“联合审查项目的上线风险”。先查看协作计划，确认后开始分析；简单问题也可以选择直接问答。</p><Link to="/workspace" onClick={() => setHelpOpen(false)}>打开协作工作台 →</Link></div></li><li><span>3</span><div><strong>查看协作结果与依据</strong><p>结果上方会展示实际参与的角色。需要写入外部系统的建议，会先放到「待确认操作」供你审查。</p></div></li></ol><div className="guide-glossary"><strong>术语说明</strong><p>Issue 用于跟踪问题与任务；PR（Pull Request）用于提交和审查代码变更；CI（持续集成）自动运行构建与测试；知识库保存可供助手查阅的项目资料。</p></div></section></div>}
    </div>
  );
}
