import { ClipboardCheck, FileText, FlaskConical, GitPullRequest, History, Network, Search, SearchCheck, Wrench, type LucideIcon } from "lucide-react";

export type ToolNavigationItem = {
  href: string;
  label: string;
  description: string;
  icon: LucideIcon;
};

export const workTools: ToolNavigationItem[] = [
  { href: "/issues", label: "Issue 分析", description: "梳理 Issue 中的问题与任务，找到排查方向和解决思路。", icon: SearchCheck },
  { href: "/pull-requests", label: "PR 审查", description: "查看 PR 的代码变更，了解合并风险与改进建议。", icon: GitPullRequest },
  { href: "/ci", label: "CI 排障", description: "查看 CI 运行结果，分析构建与测试失败的原因。", icon: Wrench },
  { href: "/action-drafts", label: "待确认操作", description: "检查助手准备的操作，再决定是否执行。", icon: ClipboardCheck },
  { href: "/workspaces", label: "研发报告", description: "整理项目进展，查看和生成研发报告。", icon: FileText },
];

export const advancedTools: ToolNavigationItem[] = [
  { href: "/rag", label: "知识检索", description: "检索项目资料，查看回答所依据的内容。", icon: Search },
  { href: "/workflow-runs", label: "任务记录", description: "回看任务的执行步骤、结果与异常。", icon: History },
  { href: "/code-graph", label: "关系图", description: "通过关系图了解代码与项目资料之间的联系。", icon: Network },
  { href: "/evals", label: "评估", description: "运行和查看评估，检查检索与回答效果。", icon: FlaskConical },
];
