import { lazy, useEffect } from "react";
import { BrowserRouter, Link, Navigate, Route, Routes, useLocation } from "react-router-dom";
import RootLayout from "./app/layout";
import SettingsLayout from "./app/settings/layout";

const WorkspaceEntryPage = lazy(() => import("./app/page"));
const WorkspacePage = lazy(() => import("./app/workspace/page"));
const ReposPage = lazy(() => import("./app/repos/page"));
const KnowledgePage = lazy(() => import("./app/knowledge/page"));
const KnowledgeDetailPage = lazy(() => import("./app/knowledge/[id]/page"));
const ToolsPage = lazy(() => import("./app/tools/page"));
const SettingsPage = lazy(() => import("./app/settings/page"));
const AgentSettingsPage = lazy(() => import("./app/settings/agents/page"));
const RetrievalModelsPage = lazy(() => import("./app/settings/retrieval/page"));
const DatabaseSettingsPage = lazy(() => import("./app/settings/database/page"));
const ActionDraftsPage = lazy(() => import("./app/action-drafts/page"));
const ChatPage = lazy(() => import("./app/chat/page"));
const CIPage = lazy(() => import("./app/ci/page"));
const CodeGraphPage = lazy(() => import("./app/code-graph/page"));
const EvalsPage = lazy(() => import("./app/evals/page"));
const IssuesPage = lazy(() => import("./app/issues/page"));
const PullRequestsPage = lazy(() => import("./app/pull-requests/page"));
const RAGPage = lazy(() => import("./app/rag/page"));
const ReportsPage = lazy(() => import("./app/reports/page"));
const WorkflowRunsPage = lazy(() => import("./app/workflow-runs/page"));
const WorkspacesPage = lazy(() => import("./app/workspaces/page"));

function RouteScroll() {
  const { pathname } = useLocation();
  useEffect(() => { window.scrollTo(0, 0); }, [pathname]);
  return null;
}

function NotFoundPage() {
  return <div className="mx-auto max-w-lg py-20 text-center">
    <p className="text-sm text-accent">404</p>
    <h1 className="mt-4 text-2xl font-semibold">找不到这个页面</h1>
    <p className="mt-4 text-sm leading-7 text-slate-500">链接可能有误，你可以回到工作台继续。</p>
    <Link to="/workspace" className="mt-6 inline-flex rounded-xl bg-accent px-5 py-3 text-sm font-medium text-[#1b2712]">返回工作台</Link>
  </div>;
}

export default function App() {
  return <BrowserRouter>
    <RouteScroll />
    <Routes>
        <Route element={<RootLayout />}>
          <Route index element={<WorkspaceEntryPage />} />
          <Route path="workspace" element={<WorkspacePage />} />
          <Route path="repos" element={<ReposPage />} />
          <Route path="knowledge" element={<KnowledgePage />} />
          <Route path="knowledge/:id" element={<KnowledgeDetailPage />} />
          <Route path="tools" element={<ToolsPage />} />
          <Route path="settings" element={<SettingsLayout />}>
            <Route index element={<SettingsPage />} />
            <Route path="agents" element={<AgentSettingsPage />} />
            <Route path="retrieval" element={<RetrievalModelsPage />} />
            <Route path="database" element={window.devharborDesktop ? <DatabaseSettingsPage /> : <Navigate to="/settings" replace />} />
          </Route>
          <Route path="action-drafts" element={<ActionDraftsPage />} />
          <Route path="chat" element={<ChatPage />} />
          <Route path="ci" element={<CIPage />} />
          <Route path="code-graph" element={<CodeGraphPage />} />
          <Route path="evals" element={<EvalsPage />} />
          <Route path="issues" element={<IssuesPage />} />
          <Route path="pull-requests" element={<PullRequestsPage />} />
          <Route path="rag" element={<RAGPage />} />
          <Route path="reports" element={<ReportsPage />} />
          <Route path="workflow-runs" element={<WorkflowRunsPage />} />
          <Route path="workspaces" element={<WorkspacesPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Route>
    </Routes>
  </BrowserRouter>;
}
