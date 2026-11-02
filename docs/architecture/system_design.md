# 系统架构

[架构导读](../../ARCHITECTURE.md) · [项目首页](../../README.md) · [Agent 工作流](agent_workflow.md) · [RAG 流水线](rag_pipeline.md) · [数据模型](database_schema.md)

DevHarbor 是面向软件研发场景的 AI 工作台，围绕问题分析、代码审查、CI 故障排查和项目知识问答，组织代码与文档证据，输出可追溯的分析建议。当前实现接入 GitHub 仓库数据与本地代码工作区；GitHub 同步、Webhook 和写入接口属于具体的平台接入实现。

前端负责呈现证据和执行过程；FastAPI 组织数据同步、对话、专项分析、检索与操作草稿。外部写入经人工确认后执行当前支持的 GitHub 操作。部署形态是**单个后端应用 + 前端应用 + 数据服务**，面向本地或受控环境中的单用户演示。

细粒度视图：[模块依赖图](../assets/architecture.svg) · [任务调度图](../assets/agent-workflow.svg) · [检索流水线图](../assets/rag-pipeline.svg)。总览图与阅读路线见[架构导读](../../ARCHITECTURE.md)，本页重点解释图中连线对应的调用、数据和失败边界。

## 模块与代码入口

| 模块 | 职责与依赖 | 主要实现 |
| --- | --- | --- |
| 页面与 API 客户端 | 收集仓库、会话与检索参数；通过 HTTP / SSE 展示证据、事件和结果 | [`frontend/app`](../../frontend/app)、[`frontend/lib/api.ts`](../../frontend/lib/api.ts) |
| API 与运行时组装 | 校验请求、解析范围、绑定数据库与工具闭包；连接 ChatAgent、工作流和持久化 | [`main.py`](../../backend/app/main.py)、[`chat.py`](../../backend/app/api/routes/chat.py) |
| GitHub 同步 | 调用 GitHub API，将 Issue / PR / Review / Workflow / Job / 日志变成可分析的快照 | [`repos_sync.py`](../../backend/app/services/repos_sync.py)、[`github`](../../backend/app/services/github) |
| 工作区与项目索引 | 管理 checkout；读取文件、词法搜索；构建项目文档、符号与关系索引 | [`worktree_manager.py`](../../backend/app/services/worktree_manager.py)、[`project_indexing.py`](../../backend/app/services/project_indexing.py)、[`code_analysis.py`](../../backend/app/services/code_analysis.py) |
| 上下文与记忆 | 从原始消息、结构化记忆与证据投影组装输入；保留压缩边界和恢复线索 | [`chat_memory.py`](../../backend/app/services/chat_memory.py)、[`context_compression.py`](../../backend/app/services/context_compression.py) |
| ChatAgent | 绑定服务端工具；由模型产生 tool calls，再收集观察、引用和最终回答 | [`chat_agent.py`](../../backend/app/services/agents/chat_agent.py) |
| Skill Runtime | 按 `SKILL.md` 激活指令与资源，施加工具约束并记录校验事件 | [`skills/registry.py`](../../backend/app/services/skills/registry.py)、[`app/skills`](../../backend/app/skills) |
| 工程工作流 | 消费 `WorkflowSpec` 与专项工具，调度任务依赖，生成观察和综合报告 | [`workflow_orchestrator.py`](../../backend/app/services/agents/workflow_orchestrator.py) |
| RAG | 文本抽取、切分与索引；依赖关系库文本和 Milvus 向量进行召回 | [`document_processing.py`](../../backend/app/services/rag/document_processing.py)、[`retrieval.py`](../../backend/app/services/rag/retrieval.py)、[`knowledge_base.py`](../../backend/app/services/rag/knowledge_base.py) |
| 操作草稿与审计 | 保存写入意图；确认接口调用 GitHub 并记录执行结果 | [`action_drafts.py`](../../backend/app/api/routes/action_drafts.py)、[`permissions.py`](../../backend/app/services/permissions.py) |
| 评测 | 用固定题集执行 ChatAgent，保存证据与硬规则结果，按配置调用 Judge | [`ragas_runner.py`](../../backend/app/services/evals/ragas_runner.py)、[`evaluations.py`](../../backend/app/api/routes/evaluations.py) |

API 路由目前承担部分工具与运行时装配，评测也复用其中的工具工厂。这使线上与评测执行路径保持接近，同时形成路由层与服务层之间的耦合；仓库并未实现严格的端口适配器分层。MCP 只承载三个内部记忆工具，其余工具直接调用应用服务。

## 两层执行控制

| 维度 | ChatAgent | 工程工作流 |
| --- | --- | --- |
| 入口 | 普通对话；`ChatOpenAI` 绑定 LangChain `StructuredTool` | `workflow.run_engineering_review`，或计划展示 / 执行接口 |
| 谁决定下一步 | 模型选择工具和参数 | 规则 Planner 产生带 `claim`、输入和依赖的 `WorkflowSpec` |
| 执行机制 | LangGraph 的 `model_decision → tool_action → model_decision` 循环；同轮待执行工具逐个运行 | 自定义 `asyncio` 调度器；仅运行依赖已成功的任务，按批次限制并行 |
| 收敛方式 | 最终回答、重复调用保护或步数耗尽 | Observer 检查证据缺口、失败与冲突；有限重规划后由 Synthesis 综合 |
| 预算与错误 | 当前最多 12 次模型决策；重复调用上限 2；可重试工具异常最多额外尝试 1 次 | 每任务超时；失败依赖使后继跳过；默认最多重规划 1 次，配置上限 2 次 |
| 输出与记录 | 回答、工具事件、引用、`completion` 与上下文诊断 | 任务结果、观察、决策、规格与 `AgentWorkflowRun` / `AgentTaskRun` |

Planner、Observer、Synthesis 当前是规则与结构化逻辑，专项分析工具才按各自配置调用模型。`claim` 明确任务的仓库与目标对象范围，不替代鉴权或进程隔离。已确认的计划走 `run_spec`，跳过初次规划；HTTP 执行入口仍使用默认的有限重规划，不能将“确认计划”理解为任务图绝不会调整。控制节点与依赖规则详见 [Agent 工作流](agent_workflow.md)。

## 从请求到记录

以 `/api/chat/stream` 中的一轮对话为例，顺序由 [`_conversation_sse`](../../backend/app/api/routes/chat.py) 组织：

| 阶段 | 控制流 | 数据流与提交边界 |
| --- | --- | --- |
| 解析范围 | 查找仓库，`ensure_conversation` 确定会话 | 仓库与会话标识进入工具闭包；会话初始化先提交 |
| 预留空间 | `ProgressiveContextManager.ensure_headroom` 检查压力 | 必要时保存压缩边界与恢复线索，再提交 |
| 接收问题 | `MessageStore.append` 保存原文；重建 `EvidenceStore` | 用户消息和证据投影在模型调用前提交 |
| 组装输入 | `ContextAssembler.assemble`，绑定工具与 Skill | 历史、记忆、证据按预算进入模型，不改写原始历史 |
| 取证与分析 | ChatAgent 选择工具；需要时进入工程任务图 | 工具事件经 SSE 到前端，观察结果进入下一次决策 |
| 生成结论 | 消费 `final`，保存 assistant 消息和 `AgentRun` | `SessionSealer` 封存 transcript、更新记忆；提交后才发送该 `final` |
| 外部操作 | 写入意图形成 `ActionDraft`，另行确认 | 确认接口执行 GitHub 操作，并提交结果与审计 |

前端收到 `tool_use` 表示开始尝试工具调用，不代表执行成功；收到回答也不代表所有工具成功。应结合 `completion`、工具结果、工作流阻塞项及引用判断结论。

GitHub 数据是**最近一次同步的快照**，工作区读取的是当前 checkout。判断“现在是否可合并”时，应先刷新相关数据并核对 GitHub；分析结果不等于持续实时监控。

## 三条取证路径

| 问题需要什么 | 取证路径 | 选择原因 |
| --- | --- | --- |
| 当前 checkout 的函数、文件和调用关系 | `workspace.list_files` / `read_file` / `search_code`，代码符号与关系索引 | 当前代码应以实际文件为准；全量源码不进入 RAG |
| Issue / PR / CI 状态、成员、周报等结构化事实 | 对应关系表、服务与 GitHub 同步 | 保持字段语义和对象范围，避免由相似文本推断状态 |
| 历史问题、PR 讨论、失败日志、项目说明与已批准知识 | RAG 文档召回 | 适合跨来源语义检索；召回结果仍是待核对的证据 |

对话记忆还有独立的精确读取路径：三个 `devharbor_*` 工具通过 stdio MCP 调用记忆服务，按仓库和会话范围读取证据、历史及封存的会话事件。MCP 在这里是**内部记忆工具协议**，并非所有工具调用的必经层。

## 上下文是原始记录的有预算投影

[`ContextAssembler`](../../backend/app/services/chat_memory.py) 分配系统信息、结构化记忆、证据与近期消息预算，并预留工具观察和回答空间。近期消息独立传入，不混成系统指令。当前问题先触发 `EvidenceStore.search` 预检索，进入模型后仍可改写查询继续取证。

| 压力处理 | 保留什么 | 实现依据 |
| --- | --- | --- |
| 输入裁剪与轻量压缩 | 近期消息、与问题相关的证据；移除可重新获取的旧工具上下文 | `compress_messages`、`microcompact_messages`、`compress_retrieval_results` |
| 正式历史压缩 | 摘要、压缩边界、关键路径 / 错误 / 待办与恢复信息；原始消息仍在数据库 | `ProgressiveContextManager`，连续压缩失败时停止继续尝试 |
| 模型溢出恢复 | 仅重新投影输入并重试失败的模型调用，避免把已执行工具整体重跑 | `ChatAgent._graph_model_decision` 的一次 aggressive retry |
| 精确追溯 | 原始消息与封存 session 的 transcript、工具事件 | `devharbor_get_thread_context`、`devharbor_read_session_events` |

算法与预算定义见 [`context_compression.py`](../../backend/app/services/context_compression.py)。这里的 Token 数主要是估算；摘要与记忆用于后续推理，原始记录才是复核依据。记忆抽取失败时，`SessionSealer` 可保留原文并标记 `sealed_with_warnings`，不能把摘要缺失误认为本轮没有发生。

## 检索与评估边界

混合检索在 [`retrieval.py`](../../backend/app/services/rag/retrieval.py) 中组合 Milvus 向量候选与关系库文本的 BM25 风格关键词候选，使用加权融合并去重。关键词分支适合错误名、文件名等精确线索；向量分支补充语义相似资料。它们是两种候选来源，并非两次必然并发执行的远程查询。

| 入口 | 执行范围 | 解读结果时的边界 |
| --- | --- | --- |
| ChatAgent 预检索 | `ContextAssembler → EvidenceStore.search` | 为当前问题提供初始证据，不等同于完整知识问答 |
| ChatAgent 检索工具 | `chat.py → search_similar_documents` | 模型可以改写查询、多轮检索；轻量路径不自动继承知识库问答全部重排 / 门控配置 |
| 知识库检索与问答 | `retrieve_knowledge`：召回、重排、父块扩展、阈值、压缩、回答门控；`answer_question` 生成 | 返回阶段轨迹与来源；规则门控不能保证识别所有冲突或幻觉 |
| ChatAgent + RAGAS 评测 | 独立评测会话运行实际 ChatAgent，捕获工具与证据，执行硬规则与可选 Judge | 用数据库 savepoint 回滚该次临时会话写入；另行保存评测结果，不证明真实外部服务已通过集成验证 |

完整流水线见 [RAG 文档](rag_pipeline.md)。评测入口 [`ragas_runner.py`](../../backend/app/services/evals/ragas_runner.py) 区分 `execution_status`、`quality_status`、`evaluation_complete`：硬规则全部通过且跳过 Judge 时为 `partial`，硬规则失败时为 `failed`；Judge 异常或必需指标缺失不能记为通过。重评分复用已保存回答与证据，重新完整执行才会检验修改后的 Agent 行为。固定题集、可比条件和评分配置见[评测指南](../guides/evaluation.md)。

## 数据与基础设施

| 组件 | 保存或提供什么 | 边界 |
| --- | --- | --- |
| PostgreSQL + SQLAlchemy | 业务快照、文档内容与元数据、会话、分析、工作流、草稿和审计 | 本地演示与测试可用 SQLite；不是向量相似度检索后端 |
| Milvus | 带 `repo_id` / `source_type` / `document_id` 的向量记录 | 负责向量检索；Embedding 模型和维度需匹配 |
| etcd + MinIO | Docker Compose 中 Milvus 的依赖 | 不承担应用消息队列职责 |
| 本地文件系统 | 仓库 checkout、上传的原始文档 | 路径由配置管理；工作区读取有边界检查 |
| OpenAI 兼容模型接口 | 对话工具决策及需要模型的分析/生成 | 模型能力依配置而定；没有 Key 时存在本地降级路径 |
| Embedding / Rerank 提供方 | 文本向量与候选重排 | 可选本地 Embedding；确定性向量仅适合测试/演示 |

Compose 使用带 pgvector 扩展的 PostgreSQL 镜像，但当前 `Document` 模型没有向量列，实际向量读写位于 `MilvusVectorStore`。可选 Redis 服务当前也不能作为“已实现分布式任务队列”的证明。

## 持久化与失败语义

关系库模型见 [`models.py`](../../backend/app/db/models.py)，实体关系见[数据模型](database_schema.md)。持久化业务记录与持久化执行引擎是两件不同的事：当前 LangGraph 未配置持久化 checkpointer；工作流在报告生成后才由 `_persist_engineering_workflow` 写入当前事务，随外层提交，不能自动从中断节点续跑。

| 情况 | 当前记录 / 行为 | 不能据此推断什么 |
| --- | --- | --- |
| ChatAgent 内部降级或预算耗尽后返回 `final` | 保留回答、事件与 `completion`；普通对话持久化分支仍把 `AgentRun.status` 写为 `success` | 单看该列不能判断模型、工具或业务目标全部成功 |
| SSE 执行阶段抛出普通异常 | 回滚当前未提交事务，再保存 `route=error` 的回答与错误运行记录，错误分支的 `tool_calls` 为空 | 已发送的中间事件不保证全部落库；输入准备阶段不在该异常捕获范围内，进程退出或连接取消也无自动续跑保证 |
| 工作流任务超时 / 依赖失败 | 任务记录 `error`；依赖失败的后继记录 `skipped`，观察与综合保留阻塞信息 | 汇总运行状态只检查 `error_count`；还需核对跳过任务与 observation，不能据此直接放行 |
| 文件入库或向量写入失败 | 记录文档处理状态和错误；关系库与 Milvus 分别写入 | 没有跨系统原子事务，需检查状态并按需重新索引 |
| Hybrid 中 Milvus 不可用 | 保留关键词结果，轨迹标记向量不可用；纯 Vector 路径向上传播并返回 503 | 检索有结果不证明向量服务可用；Embedding 错误还需区分完整 / 轻量入口 |
| GitHub 确认执行异常 | 草稿记为 `failed`，保存错误与审计；成功则记为 `executed`；只有待确认草稿能进入确认接口 | 外部请求与数据库提交不原子，超时不能证明 GitHub 未收到写入；再次操作前应核对外部结果，当前也无严格一次执行保证 |
| 后台同步、上传处理或评测被中断 | 任务在应用进程中执行，部分状态或进度可能已保存 | 后端重启不保证继续任务，也没有队列级重试保证 |

SSE 异常分支由 [`chat.py`](../../backend/app/api/routes/chat.py) 负责；上传和向量边界由 [`document_processing.py`](../../backend/app/services/rag/document_processing.py) 与 [`vector_store.py`](../../backend/app/services/rag/vector_store.py) 负责；草稿执行边界见 [`action_drafts.py`](../../backend/app/api/routes/action_drafts.py)。读取结果时应优先结合具体状态、阶段轨迹和来源，而非只检查 HTTP 成功或是否生成了回答。

## 设计取舍与演进条件

| 当前选择 | 得到什么 | 付出的代价 / 后续需要解决什么 |
| --- | --- | --- |
| 单个后端应用与进程内任务 | 本地启动、调试与演示路径直接，服务共享数据库和工具 | 长任务与 API 共享进程；生产任务恢复需要额外持久化调度和幂等设计 |
| 三类证据分流 | 保留代码、结构化状态和语义资料各自的权威来源 | 要维护同步与索引时效，并让结论明确证据范围 |
| 模型工具循环 + 规则任务图 | 开放式提问有灵活取证能力，综合任务有可测试的依赖与停止条件 | 规则无法覆盖任意新任务；新增任务类型需要扩展 schema、工具和测试 |
| 原始 transcript 与模型输入分离 | 可压缩上下文，同时保留复核和精确恢复入口 | 增加消息、摘要、证据投影之间的一致性维护成本 |
| 分离执行状态与质量评估 | 能定位召回、工具、回答或 Judge 的不同失败 | 固定题集覆盖有限，仍需记录代码 / 数据 / 模型版本并补充真实服务实验 |
| 人工确认外部操作 | 将建议和实际写入放在不同接口，保留审计 | 当前演示身份不提供真实登录隔离；`DEMO_MODE` 不会禁止确认后的 GitHub 写入 |

当前适合可信本机或受控环境的单用户演示。后台队列、真实身份边界、版本化数据库迁移和外部写入幂等恢复，属于扩大部署范围前需补足的能力；这里列出的是演进条件，不是已实现功能。操作与配置边界见[安全文档](security.md)。

## 验证依据

下表把架构约束对应到现有回归测试。它说明检查什么，不宣称本次或任意环境已经通过全部检查。

| 约束 | 代表性断言与测试 |
| --- | --- |
| 工具循环可以逐步取证并有停止条件 | [`test_chat_agent.py`](../../backend/app/tests/test_chat_agent.py)：文件列表到读取、工具开始事件、溢出仅重试模型调用、暂态错误重试、重复调用停止 |
| 压缩后仍能恢复原文 | [`test_context_compression.py`](../../backend/app/tests/test_context_compression.py)：预算、工具调用 / 结果配对；[`test_context_memory_projection.py`](../../backend/app/tests/test_context_memory_projection.py)：跨压缩边界原文恢复、封存失败保留 transcript |
| 工程任务的依赖、目标与失败可追踪 | [`test_workflow_orchestrator.py`](../../backend/app/tests/test_workflow_orchestrator.py)：显式对象范围、就绪并行、证据缺失重规划、已确认计划、任务超时、依赖跳过与任务记录 |
| 检索流水线与范围有明确契约 | [`test_rag_retrieval_pipeline.py`](../../backend/app/tests/test_rag_retrieval_pipeline.py)：融合公式、同源同版本父块扩展、重排失败轨迹、阶段完整性；[`test_rag_project_isolation.py`](../../backend/app/tests/test_rag_project_isolation.py)：仓库隔离 |
| 评测不会把执行结束当作质量通过 | [`test_eval_runner.py`](../../backend/app/tests/test_eval_runner.py)：真实 ChatAgent 路径与临时会话回滚、硬规则、复用证据重评分、可比条件；[`test_bundled_eval_suite.py`](../../backend/app/tests/test_bundled_eval_suite.py)：内置题集契约 |

[CI](../../.github/workflows/ci.yml) 使用隔离 SQLite、确定性 Embedding 与模拟外部服务运行后端测试，并执行前端 lint / build 等检查；它不验证真实 GitHub 写入、真实 Milvus、模型质量或生产负载。运行命令和真实模型评测方法见[测试与评测](../guides/evaluation.md)。

SSE 异常后的持久化、草稿并发确认及“外部已成功而本地提交失败”场景，目前没有对应的直接回归测试；上述失败边界来自源码审查。草稿现有测试覆盖的是 [`test_expansion_features.py`](../../backend/app/tests/test_expansion_features.py) 中 `send_report` 的本地记录路径，不能作为 GitHub 写入集成测试的证据。

## 推荐阅读顺序

先看[对话与工程工作流](agent_workflow.md)，再看[RAG 流水线](rag_pipeline.md)中召回、重排和降级的区别；需要追踪数据时查[数据库模型](database_schema.md)。接口以运行中的 `/docs` 与 `/openapi.json` 为准，静态索引见 [API 导航](../api/openapi.md)。启动与依赖配置见[运行指南](../guides/getting-started.md)。
