import { Suspense } from "react";
import { Outlet } from "react-router-dom";
import { AppShell } from "@/components/layout/app-shell";

export default function RootLayout() {
  return <AppShell><Suspense fallback={<div role="status" className="grid min-h-[60vh] place-items-center text-sm text-slate-500">正在打开页面…</div>}><Outlet /></Suspense></AppShell>;
}
