import { Link, Outlet, useLocation } from "react-router-dom";
import { Suspense } from "react";
import { Bot, Database, KeyRound, Search } from "lucide-react";
import styles from "./settings.module.css";

const categories = [
  { href: "/settings", label: "API 配置", icon: KeyRound },
  { href: "/settings/retrieval", label: "检索模型", icon: Search },
  { href: "/settings/database", label: "数据库连接", icon: Database, desktopOnly: true },
  { href: "/settings/agents", label: "智能体管理", icon: Bot },
];

export default function SettingsLayout() {
  const { pathname } = useLocation();
  return (
    <div className={styles.layout}>
      <aside className={styles.navigation} aria-label="设置分类">
        <h1>设置</h1>
        <nav className={styles.categoryLinks}>
          {categories.filter((item) => !item.desktopOnly || window.devharborDesktop).map(({ href, label, icon: Icon }) => <Link key={href} to={href} className={styles.navItem} aria-current={pathname === href ? "page" : undefined}><Icon size={19} /><span>{label}</span></Link>)}
        </nav>
      </aside>
      <Suspense fallback={<div role="status" className="py-4 text-sm text-slate-500">正在打开设置…</div>}><Outlet /></Suspense>
    </div>
  );
}
