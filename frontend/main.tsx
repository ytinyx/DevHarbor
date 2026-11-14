import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { initializeApi } from "@/lib/api";
import App from "./App";
import "./app/globals.css";

const root = document.getElementById("root");
if (!root) throw new Error("找不到应用挂载节点。");

const application = createRoot(root);
application.render(<div role="status" className="grid min-h-screen place-items-center text-sm text-slate-500">正在启动 DevHarbor…</div>);

async function startApplication() {
  try {
    await initializeApi();
    application.render(<StrictMode><App /></StrictMode>);
  } catch {
    application.render(<div role="alert" className="mx-auto max-w-lg px-6 py-20 text-center">
      <h1 className="text-xl font-semibold">应用暂时无法启动</h1>
      <p className="mt-4 text-sm leading-7 text-slate-500">未能连接应用服务，请重试。若仍无法启动，请关闭后重新打开应用。</p>
      <button type="button" onClick={() => window.location.reload()} className="mt-6 rounded-xl bg-accent px-5 py-3 text-sm font-medium text-[#1b2712]">重试</button>
    </div>);
  }
}

void startApplication();
