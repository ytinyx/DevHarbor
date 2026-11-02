# API 导航

[返回首页](../../README.md) · [运行指南](../guides/getting-started.md) · [安全边界](../architecture/security.md)

本文是按使用场景整理的入口索引，完整参数、响应类型和约束以运行实例的 OpenAPI 为准。启动后端后访问 `http://127.0.0.1:8000/docs`，机器可读定义位于 `http://127.0.0.1:8000/openapi.json`。路由注册见 [`app/main.py`](../../backend/app/main.py)。

下文的 `repo_id`、`pr_id`、`issue_id` 等是 DevHarbor 数据库 UUID，通常不是 GitHub 的编号。当前 API 没有完整用户认证；角色检查使用演示用户，不能作为公网服务授权。部分读操作会返回私有仓库或本地文件内容，应在本机可信环境访问。

## 仓库与工作区

| 方法 | 路径 | 作用 |
| --- | --- | --- |
| GET | `/api/repos` | 查询已连接仓库 |
| POST | `/api/repos/connect` | 连接 GitHub 仓库或本地 checkout，初始化同步与分析 |
| POST | `/api/repos/{repo_id}/sync` | 同步 Issue、PR 与 CI 数据 |
| GET | `/api/repos/{repo_id}/sync-status` | 查看同步与本地分析状态 |
| POST | `/api/repos/{repo_id}/select` | 设置当前仓库 |
| DELETE | `/api/repos/{repo_id}` | 删除仓库及关联本地记录；操作前确认范围 |
| GET / POST | `/api/workspaces` | 列出 / 创建多仓库工作区 |
| POST | `/api/workspaces/multi-repo-report` | 生成多仓库报告 |
| POST | `/api/webhooks/github` | 接收 GitHub 事件，按支持的事件安排同步 |

Webhook 只有配置了 `GITHUB_WEBHOOK_SECRET` 才会校验签名。连接、同步和本地 checkout 可能访问网络并创建本地文件，不能把所有接口视为纯读操作。

## Issue、PR 与 CI

| 方法 | 路径 | 作用 |
| --- | --- | --- |
| GET | `/api/repos/{repo_id}/issues` | Issue 列表 |
| GET | `/api/issues/{issue_id}` | Issue 详情 |
| POST | `/api/issues/{issue_id}/analyze` | 分类、优先级、行动项等分析 |
| GET | `/api/issues/{issue_id}/similar` | 相似 Issue 候选 |
| GET | `/api/repos/{repo_id}/pull-requests` | PR 列表 |
| GET | `/api/pull-requests/{pr_id}` | PR 详情、文件与评论 |
| POST | `/api/pull-requests/{pr_id}/analyze` | PR 风险和变更分析 |
| POST | `/api/pull-requests/{pr_id}/review-checklist` | 生成审查清单 |
| POST | `/api/pull-requests/{pr_id}/snapshot` | 准备 PR 快照 |
| POST | `/api/pull-requests/{pr_id}/worktree` | 准备本地 PR worktree |
| GET | `/api/repos/{repo_id}/workflow-runs` | GitHub Actions 运行列表 |
| GET | `/api/workflow-runs/{run_id}` | 单次 CI 运行详情 |
| GET | `/api/workflow-runs/{run_id}/failed-jobs` | 失败 Job |
| POST | `/api/workflow-runs/{run_id}/analyze` | CI 失败定位与建议 |

Issue、PR、CI 的 `analyze` 路径也提供追加 `/stream` 的流式版本。

## Agent、会话与工程评审

| 方法 | 路径 | 作用 |
| --- | --- | --- |
| POST | `/api/chat` | 运行 ChatAgent 并返回完整结果 |
| POST | `/api/chat/stream` | 流式 Agent 对话 |
| GET | `/api/chat/history` | 查询对话历史 |
| POST | `/api/chat/plan` | 生成计划供查看 |
| POST | `/api/chat/plan/execute/stream` | 流式执行计划 |
| GET | `/api/chat/workflow-runs` | 查看工程评审运行和专家任务 |
| POST | `/api/chat/recommendations` | 生成下一步建议 |
| GET / POST | `/api/repos/{repo_id}/conversations` | 列出 / 创建会话 |
| DELETE | `/api/repos/{repo_id}/conversations/{conversation_id}` | 删除指定会话 |
| GET | `/api/skills` | 列出 Skill 元数据 |
| GET | `/api/skills/{skill_name}` | 单个 Skill 详情 |
| GET | `/api/skills/mcp-status` | MCP 工具状态 |
| POST | `/api/reports/weekly` | 周报生成 |
| POST | `/api/reports/repo-health` | 仓库健康分析 |

## 知识库、检索与源码索引

| 方法 | 路径 | 作用 |
| --- | --- | --- |
| GET | `/api/rag/models` | 当前 Embedding / Rerank 配置与可用性 |
| GET | `/api/rag/repositories` | 仓库知识库列表 |
| GET | `/api/rag/repositories/{repo_id}` | 知识库概览 |
| PATCH | `/api/rag/repositories/{repo_id}/config` | 检索、重排、阈值与分片设置 |
| GET / POST | `/api/rag/repositories/{repo_id}/documents` | 列出 / 上传知识文件 |
| GET | `/api/rag/repositories/{repo_id}/documents/{document_id}/chunks` | 查看分片 |
| POST | `/api/rag/repositories/{repo_id}/documents/{document_id}/retry` | 重试文件处理 |
| DELETE | `/api/rag/repositories/{repo_id}/documents/{document_id}` | 删除文件及对应索引 |
| GET / POST | `/api/rag/repositories/{repo_id}/retrieval-tests` | 查询历史 / 执行检索测试 |
| GET | `/api/rag/{repo_id}/status` | 检索与生成运行状态 |
| POST | `/api/rag/{repo_id}/search` | 检索证据，返回来源与 trace |
| POST | `/api/rag/{repo_id}/ask` | 带证据回答，返回生成模式与回答门控 |
| POST | `/api/rag/{repo_id}/reindex` | 重建当前策略允许的知识索引 |
| POST | `/api/search` | 统一检索入口 |
| GET | `/api/repos/{repo_id}/memory-index/state` | 项目索引状态 |
| POST | `/api/repos/{repo_id}/memory-index/scan` | 扫描项目索引清单 |
| POST | `/api/repos/{repo_id}/code-graph/rebuild` | 重建源码符号与关系 |
| GET | `/api/repos/{repo_id}/code-symbols` | 查询源码符号 |
| GET | `/api/repos/{repo_id}/code-graph/search` | 查询代码关系 |

上传使用 `multipart/form-data` 的 `file` 字段，单个文件上限 12 MiB，支持扩展名以状态接口返回值和上传校验为准。接口通常先返回 HTTP 202 与 `queued` 记录，再由后台处理；相同仓库中非失败记录按 SHA-256 去重。查询文件列表确认处理状态后再检索。

`/search` 与 `/ask` 请求示例：

```json
{
  "question": "本地演示为什么显示 degraded？",
  "top_k": 5,
  "source_types": ["knowledge_file"],
  "metadata_filters": {}
}
```

`/ask` 的 `generation_mode` 为 `llm`、`extractive` 或 `no_evidence`；应连同 `sources`、`answer_gate` 和 `retrieval_config` 阅读。Milvus 不可用时，纯向量路径可返回 HTTP 503，Hybrid 可保留关键词分支并在 trace 标明向量不可用。完整 RAG 机制见[检索架构](../architecture/rag_pipeline.md)。

长期记忆、知识图谱和团队成员接口位于 `/api/repos/{repo_id}/knowledge*`、`/memory/*`、`/team-members`；完整细节见 OpenAPI。

## 操作草稿与审计

| 方法 | 路径 | 作用 |
| --- | --- | --- |
| GET / POST | `/api/action-drafts` | 列出 / 创建草稿 |
| GET | `/api/action-drafts/{draft_id}` | 查看草稿详情 |
| POST | `/api/action-drafts/{draft_id}/cancel` | 取消待确认草稿 |
| POST | `/api/action-drafts/{draft_id}/confirm` | **执行草稿，可能真实写入 GitHub** |
| GET | `/api/action-drafts/audit-logs` | 查看草稿操作审计 |

确认接口支持创建 Issue、发布 Issue/PR 评论、关闭 Issue 与添加标签。`send_report` 只记录为已发送，未接入外部报告渠道。`DEMO_MODE=true` 不是确认接口的只读保护；详情见[安全边界](../architecture/security.md)。

## 评测与反馈

| 方法 | 路径 | 作用 |
| --- | --- | --- |
| GET | `/api/evals/suites?repo_id=...` | 固定题集、来源就绪状态 |
| POST | `/api/evals/run` | 基础 Eval |
| POST | `/api/evals/rag/run` | 提交 ChatAgent + RAGAS 后台评测 |
| GET | `/api/evals` | 历史评测记录 |
| GET | `/api/evals/{eval_id}` | 状态、进度和逐题结果 |
| POST | `/api/evals/{eval_id}/rescore` | 复用现场，重试缺失或异常评分 |
| GET | `/api/evals/compare?base_eval_id=...&candidate_eval_id=...` | 配置可比性与回归差异 |
| POST | `/api/evals/{eval_id}/issue-draft` | 从评测结果创建 Issue 草稿 |
| GET / POST | `/api/chat/feedback` | 查询 / 提交回答反馈 |
| PATCH | `/api/chat/feedback/{feedback_id}` | 更新反馈处理状态 |
| GET | `/api/chat/feedback/metrics` | 反馈汇总 |
| GET | `/api/chat/feedback/trace/{run_id}` | 回看回答执行轨迹 |

固定来源上传、Judge 配置、`partial` / `error` 的含义和重评分流程见[评测指南](../guides/evaluation.md)。
