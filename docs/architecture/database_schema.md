# 数据模型与持久化边界

[返回首页](../../README.md) · [系统架构](system_design.md) · [Agent 工作流](agent_workflow.md) · [RAG 流水线](rag_pipeline.md)

SQLite 或 PostgreSQL 保存业务对象、文本证据和执行记录。启用向量检索后，向量存入 Milvus 或当前 PostgreSQL 中的 pgvector 表。文件系统保存 checkout 与上传原件。总图包含 36 张 ORM 表，按需创建的 pgvector 表另见知识与检索图。[`models.py`](../../backend/app/db/models.py) · [`pgvector_store.py`](../../backend/app/services/rag/pgvector_store.py)

![36 张 ORM 表的外键与关键逻辑关联总图](../diagrams/svg/05_entity_relationship.svg)

[放大 SVG](../diagrams/svg/05_entity_relationship.svg) · [离线图集](../diagrams/00_打开图表.html)

## 1. GitHub 快照与项目索引

![仓库快照、Agent 配置、工程任务与审计字段](../diagrams/svg/05c_runtime_detail.svg)

[放大 SVG](../diagrams/svg/05c_runtime_detail.svg) · [离线图集](../diagrams/00_打开图表.html)

| 表 | 关键内容 | 阅读要点 |
| --- | --- | --- |
| `repositories` | 仓库标识、provider、API/clone 地址、checkout 模式、加密 Token、同步时间 | `full_name` 唯一；`last_sync_at` 用于判断快照新鲜度 |
| `issues` | number、正文、状态、labels、assignees、GitHub 时间 | 标签与负责人是 JSON 字段 |
| `pull_requests` | 分支、正文、状态、合并时间 | 文件与评论单独保存 |
| `pr_files` / `pr_review_comments` | patch、增删行数 / 评论、文件路径、行号 | 作为 PR 分析上下文；并非完整 Git 历史 |
| `workflow_runs` | status、conclusion、jobs、logs_text | `jobs` JSON 包含 Job / Step 信息 |
| `project_index_states` | 状态、fingerprint、索引统计、错误摘要 | 每个仓库至多一条记录 |
| `code_symbols` / `code_relations` | 文件、符号、行号、分支、PR 范围与关系 | `pr_id` 是普通 UUID 字段，未声明到 PR 表的外键；关系两端允许为空 |

`analysis_results` 通过 `target_type + target_id` 在应用层关联 Issue、PR 或 CI 等对象，保存输入快照、结构化分析和模型名。团队工作区以 `workspaces.repo_ids` 保存仓库 ID 列表，`created_by` 指向 `users.id`。多仓库周报从相关项目的 SQL 快照汇总，并写入各项目的知识记录。[`workspaces.py`](../../backend/app/api/routes/workspaces.py)

## 2. 知识与检索

![知识文档、索引、检索与评估字段](../diagrams/svg/05b_knowledge_detail.svg)

[放大 SVG](../diagrams/svg/05b_knowledge_detail.svg) · [离线图集](../diagrams/00_打开图表.html)

| 表或存储 | 保存内容 | 与其他模块的关系 |
| --- | --- | --- |
| `knowledge_base_configs` | Embedding 契约、检索方式、重排、Top-K、阈值和分块设置 | `repo_id` 唯一 |
| `retrieval_model_settings` | 全局检索模型、向量后端配置、加密凭据和配置修订标识 | 以 `kind` 区分 Embedding 与 Rerank 设置 |
| `knowledge_source_documents` | 原文件位置、checksum、类型、大小、处理状态和错误 | 可定位上传原件与处理进度 |
| `documents` | `source_type`、`source_id`、标题、内容与 `metadata` | 上传片段通过来源标识关联原文；不是外键 |
| Milvus collection | 向量、`repo_id`、`document_id`、来源和元数据 | `document_id` 对应关系表文档，跨存储没有数据库外键 |
| `rag_document_vectors` | pgvector 模式下按需创建，保存 `collection_name`、`document_id` 和 `embedding` | 主键为集合名与文档 ID，`document_id` 外键指向 `documents.id` 并级联删除 |
| `retrieval_test_runs` | 查询、检索参数、结果 JSON 和耗时 | 供检索实验复查 |
| `knowledge_graph_edges` | 知识对象之间的关系和元数据 | 与源码符号图的 `code_relations` 分开存储 |

`documents.metadata` 可包含路径、标题、页码、父子片段、checksum、分支、时间以及 Embedding 信息。模型中的 Python 属性为 `meta`。pgvector 通过 `document_id` 联接片段正文，并按集合、仓库、向量维度与来源类型过滤。片段和 pgvector 向量在同一个 PostgreSQL 事务中写入。[`pgvector_store.py`](../../backend/app/services/rag/pgvector_store.py)

## 3. 会话、记忆与执行轨迹

![工作区、会话、记忆与反馈字段](../diagrams/svg/05a_sessions_detail.svg)

[放大 SVG](../diagrams/svg/05a_sessions_detail.svg) · [离线图集](../diagrams/00_打开图表.html)

*图中可选父关系对应可空外键，主要用于兼容无显式会话范围的记录。跨实体的范围检查由应用处理。*

| 表 | 职责与关键字段 |
| --- | --- |
| `conversations` | 用户可见会话：标题、状态、消息计数和更新时间 |
| `chat_messages` | 原始 user / assistant 消息、route、tool_calls 和运行元数据 |
| `chat_sessions` | 一次交互封存后的 transcript、digest 和封存状态；消息 ID 字段是普通 UUID，并非 FK |
| `conversation_memories` | 会话范围的 facts、decisions、tasks、偏好、仓库上下文与 citations |
| `thread_memories` | 仓库范围的兼容记忆；`repo_id` 可空且唯一 |
| `evidence_items` | 用于上下文组装的证据投影，带范围、来源、正文和元数据 |
| `memory_candidates` | 从 session 提取的待审核记忆候选 |
| `recall_events` | 记录检索或记忆召回过程，便于追踪来源 |
| `agent_runs` | 单次对话执行的用户输入、route、tool_calls、最终回答和状态 |
| `agent_workflow_runs` | 工程工作流目标、完整规格、Observer 输出、报告和 metrics |
| `agent_task_runs` | 单项任务的 claim、输入、结果、状态、错误与起止时间 |
| `chat_feedback` | 对指定 assistant 消息的评价与反馈；可关联 AgentRun 和用户 |

`AgentRun.status` 不能单独代表所有工具成功：回答可能带有降级、工具错误或预算耗尽。排障时应同时读取消息元数据、工具事件和对应工作流任务结果。

## 4. 配置、草稿、审计与评测

| 表 | 用途 | 关联方式 |
| --- | --- | --- |
| `agent_settings` | 保存可配置 Agent 的启用状态 | `agent_id` 为主键 |
| `model_providers` | 模型供应商、协议、服务地址、模型列表与加密 API Key | 可由本机默认配置引用 |
| `model_provider_selection` | 保存本机当前默认供应商与模型 | `provider_id` 指向 `model_providers.id`，删除供应商时清空 |
| `users` | 演示用户、role 与加密 GitHub Token | 当前不是完整登录身份系统 |
| `action_drafts` | 待确认内容、风险、状态、确认人、执行结果或错误 | `repo_id`、`created_by`、`confirmed_by` 为 FK；目标采用类型 + ID |
| `audit_logs` | 操作、目标、请求/结果 JSON、状态、时间 | 可关联仓库和用户；目标 ID 为普通字符串 |
| `eval_runs` | 评测结果、进度、配置、逐题证据、指标和报告 | 主要内容位于 `result_json`，没有独立 `repo_id` 外键列 |

具体确认权限与 GitHub 写入行为见[安全文档](security.md)，评测状态及分数解释见[评测指南](../guides/evaluation.md)。

## 5. 维护约束

- **建表与迁移。** 当前启动过程调用 `Base.metadata.create_all`，并执行有限的兼容字段修补。它不是一套完整的版本化数据库迁移；升级前应备份并检查实际 schema。
- **删除与清理。** 部分 ORM 关系带 `delete-orphan`，其他关联由路由/服务显式清理，不能假设每条逻辑关系都具备级联删除。相关回归包括 [`test_repo_deletion.py`](../../backend/app/tests/test_repo_deletion.py) 与 [`test_conversation_deletion.py`](../../backend/app/tests/test_conversation_deletion.py)。
- **跨存储一致性。** Milvus 向量和上传原件各自独立于业务 SQL 事务。重建索引、删除和失败恢复需核对涉及的各层状态。
- **桌面数据库切换。** 数据库连接设置保存在桌面数据目录。重启后应用使用选定的 SQLite 或 PostgreSQL，原有数据保留在原数据库。更换向量后端或 Embedding 配置后，使用知识库的重建索引入口。 [桌面运行指南](../guides/desktop.md)
- **仓库范围。** 关系查询和向量过滤使用 `repo_id`；部分历史记录允许空范围。它是应用层范围控制，不等同于多租户授权系统。
- **持久化兼容。** 稳定来源 UUID 的历史命名空间应保持兼容；调整文件名、集合名或来源类型时，不应仅凭文档名称改动就重建所有标识。
