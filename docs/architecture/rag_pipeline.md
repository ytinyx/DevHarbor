# RAG：从项目资料到可核对的证据

[返回首页](../../README.md) · [系统架构](system_design.md) · [Agent 工作流](agent_workflow.md) · [配置指南](../guides/configuration.md) · [评测指南](../guides/evaluation.md)

DevHarbor 为非结构化项目知识提供检索流水线：保留来源与版本信息，组合向量和关键词候选，记录重排、去重、上下文压缩及回答门控过程。当前代码同时提供完整的知识问答链和较轻量的 Agent 检索工具，二者共享召回组件，调用范围不同。

![RAG 流水线：资料入库、双路召回、融合、重排、上下文与回答门控](../assets/rag-pipeline.svg)

*架构示意图。双路表示两个候选来源，不表示代码将两次召回并发执行；降级分支也应在结果中检查。*

## 1. 哪些数据进入 RAG

规则集中在 [`source_policy.py`](../../backend/app/services/rag/source_policy.py)。

| 类型 | 索引内容 | 必须保留的边界 |
| --- | --- | --- |
| `issue` | 标题和正文 | 状态、标签等字段只是同步快照 |
| `pull_request` | 标题、正文和 Review 评论 | 文件 diff 交给 PR/工作区分析，不将整份源码当知识文本 |
| `workflow_run` | 失败运行的日志，先脱敏再按长度截断分块 | 成功运行和空日志不走该索引分支；脱敏是规则匹配 |
| `project_doc` | 项目索引识别的文档 | 当前代码结论仍需检查 checkout |
| `knowledge_file` | 用户上传后解析、切分的资料 | 可追溯到原文件、checksum 和片段元数据 |
| `memory_note` | 经确认进入知识层的记忆笔记 | 待审核候选与普通对话历史不是同一类来源 |

项目概览、配置清单、团队成员、周报、聊天 session、会话记忆等结构化来源走直接读取。全量源码不参与向量召回。这个分流减少了“文本相似”被误当作“当前事实”的机会。

## 2. 上传资料入库

| 阶段 | 处理 | 记录与后继 |
| --- | --- | --- |
| 接收文件 | 检查文件类型和大小、按 SHA-256 检查重复 | 保存原文件与 `KnowledgeSourceDocument`；进入 `queued` |
| 格式解析 | TXT / Markdown / PDF / DOCX / JSON / CSV / 日志等文本提取 | `parsing`；无有效文本则失败 |
| 结构切分 | `chunk_document` 按结构生成片段与父子元数据 | `splitting`；保留标题、页码等可用定位信息 |
| 生成向量 | 按配置的 provider / model / dimensions 分批处理 | `embedding`；上传处理的批次上限为 64 |
| 双侧写入 | `Document` 保存文本与元数据，Milvus 保存向量和关联标识 | 原文件记录变为 `completed` |
| 错误处理 | 回滚当前数据库事务并记录错误摘要 | 记录 `failed`，供页面检查和重试 |

实现入口是 [`rag.py`](../../backend/app/api/routes/rag.py) 与 [`document_processing.py`](../../backend/app/services/rag/document_processing.py)。文本抽取和切分分别位于 [`document_extraction.py`](../../backend/app/services/rag/document_extraction.py)、[`chunking.py`](../../backend/app/services/rag/chunking.py)。GitHub 快照通过 [`indexing.py`](../../backend/app/services/rag/indexing.py) 形成另一条文档来源路径，不经过上传文件状态机。

上传接口先保存原文件和 `queued` 记录，再通过 FastAPI `BackgroundTasks` 在当前服务进程中处理。各阶段会分别提交状态；失败处理只回滚当前未提交事务，再将错误摘要写入 `failed`。重新处理接口会重新排队，不是持久消息队列的自动重试机制；服务退出后不能保证任务自行恢复。

双侧写入的顺序与约束可在 [`vector_store.py`](../../backend/app/services/rag/vector_store.py) 核对：先向关系数据库 `flush` 文档行，Milvus 启用时再执行向量写入，最后提交数据库事务。新片段与向量准备完成后，重处理会先删除对应来源的旧片段，再写入新片段。关系数据库、原文件和 Milvus 没有跨系统原子事务；失败或进程中断后需分别检查状态与索引，必要时重新处理，不能仅凭某个阶段状态推断所有存储一致。

`completed` 表示当前配置下的文档处理结束。Milvus 被关闭时仍可完成关系数据库中的片段保存；它不等于向量集合已可用，更不代表语义检索质量已验证。

## 3. 完整知识检索链

[`retrieve_knowledge`](../../backend/app/services/rag/knowledge_base.py) 用于检索实验和知识问答：

1. **解析范围与配置。** 固定 `repo_id`，叠加 `source_types`、路径、标签、分支与时间等元数据条件；读取知识库检索方式、Top-K、重排和阈值设置。
2. **准备查询向量。** 仅 `vector` / `hybrid` 且存在可向量化来源时调用 Embedding；与入库配置使用同一向量契约。当前校验要求知识库的 provider / model / dimensions 与全局配置一致，共享集合中的各仓库不能任意采用不同向量空间。
3. **向量召回。** Milvus 先按仓库与来源过滤，再由应用层处理其余元数据筛选。
4. **关键词召回。** 从当前仓库的 `Document` 候选计算 BM25 风格词项分数，对标题、路径、符号和正文等字段设置不同权重；不是独立 Elasticsearch 服务。
5. **候选融合。** Hybrid 对归一化分数加权，当前权重为向量 `0.62`、关键词 `0.30`、双路命中奖励 `0.08`；不是 RRF 算法。
6. **去重与父块限制。** 移除重复/近重复文本，限制同一个父块占据过多候选位置。
7. **重排与 Top-K。** 按配置调用 Qwen Rerank 或启发式重排；远程重排异常时记录 fallback 并使用启发式结果。
8. **父块上下文扩展。** 根据来源、父块和版本信息补充相邻子块；缺少父子元数据时保留原候选。
9. **阈值过滤。** 移除低于分数门槛的候选；不同重排方式的分数不能直接当作经过校准的概率。
10. **上下文压缩。** 按问题选取片段，限制单片段与总 Token 预算，保存实际入选信息。
11. **回答门控。** 检查无证据、关键名称未出现、冲突线索和问题歧义；产生 `answer`、`insufficient_evidence`、`conflict` 或 `ask_clarification`。
12. **生成与引用。** 知识问答只在门控允许时生成；有模型配置则调用 LLM，否则提供摘录式回答。返回编号来源、生成方式、门控与流水线信息。

[`answer_gate.py`](../../backend/app/services/rag/answer_gate.py) 采用规则与关键词线索，不是可靠性证明，也不能保证所有矛盾或幻觉都被识别。LLM 的编号引用来自提示约束，使用者仍应查看实际来源。

### 从结果追到哪一步丢失了证据

完整检索返回候选结果、配置轨迹和耗时。`pipeline.stages` 保留召回、重排、父块扩展、阈值、压缩与门控的信息；重排记录请求方式、实际方式及 fallback 原因。每条候选中的 `retrieval.answer_gate` 和 `retrieval.selected_for_context` 则说明门控是否允许其进入回答上下文。检索实验将这些结果连同查询与配置保存到 `RetrievalTestRun`。

调试时先看范围与候选数量，再看重排、阈值和压缩：没有初始候选通常应检查来源/索引/查询；有候选但阈值后为空应核对分数尺度；上下文有证据但拒答应查看门控理由。该轨迹把“检索返回了什么”和“最终用于回答什么”分开，避免只凭最后一段答案猜测问题。

## 4. ChatAgent 检索与知识问答的区别

| 入口 | 调用路径 | 适合观察什么 |
| --- | --- | --- |
| `/api/rag/{repo_id}/ask` | `answer_question → retrieve_knowledge → search_similar_documents`，然后门控与生成 | 完整召回、重排、邻块扩展、阈值、压缩与拒答路径 |
| 知识库检索实验 | `retrieve_knowledge`，保存 `RetrievalTestRun` | 检索参数变化、候选来源、分数和各阶段输出 |
| ChatAgent 预检索 | `ContextAssembler → EvidenceStore.search` | 原始问题在模型决策前带入的证据 |
| `rag.search_similar_documents` 工具 | `chat.py` 中的语义搜索调用轻量 `search_similar_documents` | 模型改写查询、多轮取证与工具引用；不会自动走完整知识问答门控 |

因此，不能把独立知识问答页上的阈值、Qwen 重排或门控行为，直接认定为每一次 ChatAgent 检索都会经过的步骤。ChatAgent 的最终回答还会综合工作区和其他工具观察。

## 5. 降级是可见状态

| 情况 | 当前行为 | 如何解释 |
| --- | --- | --- |
| Hybrid 中 Milvus 不可用 | 捕获 `MilvusUnavailableError`，保留关键词分支，轨迹标记向量 `unavailable` | 有结果不等于完成语义向量检索 |
| 纯 Vector 中 Milvus 不可用 | 向上传播异常，应用返回 503 | 不用关键词结果冒充向量结果 |
| Qwen Rerank 未配置或失败 | 回退启发式重排并记录原因类型 | 结果可用于演示；不等于远程重排已验证 |
| 完整知识问答/入库中的 Embedding 不可用 | 抛出错误，不静默切换向量空间 | 修复配置或明确更换集合并重建索引 |
| 没有可用于生成的模型配置 | 门控允许时返回摘录式答案 | 属于文本证据展示，不是模型生成质量验证 |
| 门控未通过 | 返回补充资料、澄清或证据冲突提示 | 先检查输入与检索范围，不应编造结论 |

本地演示脚本显式使用确定性 Embedding 并关闭 Milvus，只能验证界面、存储、关键词检索等路径；完整语义检索需按[运行指南](../guides/getting-started.md)准备模型与向量服务。

轻量检索路径在向量存储函数内部生成查询向量时，会把 Embedding 异常包装为 `MilvusUnavailableError`；Hybrid 因而可能继续返回关键词结果。完整知识问答在召回前生成查询向量，失败会直接中断。定位降级原因时，应检查具体入口与服务日志。

## 6. 从检索实验到 Agent 评估

检索实验只观察候选与流水线；端到端评估运行正式 ChatAgent 的取证与回答路径。二者不能互相替代：较好的召回分数不能证明回答正确，一段合理回答也不能证明来源命中稳定。

| 阶段 | 实际执行 | 留存与判定 |
| --- | --- | --- |
| 装载固定题集 | 读取题集，记录原文件 SHA-256，按当前仓库解析预期来源 | 缺少对应来源时拒绝执行，避免在无关仓库上得到虚假的基线 |
| 构造每题现场 | 新建评估会话，使用 `EvidenceStore`、`ContextAssembler` 与正式工具注册表运行 `ChatAgent` | 保存实际回答、检索上下文、来源、工具观察、完成状态及逐题耗时 |
| 硬规则检查 | 检查来源命中、必需工具、工具错误、回答/上下文及题目指定文本条件 | 分题记录通过与失败原因 |
| RAGAS Judge | 按启用的模型和指标评分，保留缺失或异常指标 | 输出质量状态；任务运行结束不等于质量通过 |
| 基线对比 | 校验题集 Hash、Ragas 版本、Judge 模型与 Top-K | 避免把不同评估条件直接视作改进或回归 |
| 缺失指标重评分 | 复用保存的回答、上下文、来源和工具现场，创建新评估记录 | 只重试失败或缺失指标，不重新检索和生成回答 |

实现分别位于 [`suites.py`](../../backend/app/services/evals/suites.py)、[`ragas_runner.py`](../../backend/app/services/evals/ragas_runner.py) 和 [`evaluations.py`](../../backend/app/api/routes/evaluations.py)。每题用 SQL savepoint 隔离评估会话，结束后回滚；这用于避免评估对话污染日常会话，不能被当作外部调用副作用的安全沙箱。

结果应同时检查 `execution_status`、`quality_status`、`evaluation_complete` 和逐题错误。硬规则通过但未启用 Judge 时为 `partial`；启用 Judge 后，若硬规则与已有语义指标未失败，但必需指标缺少有效汇总分数或存在评分错误，则为 `incomplete`；规则或语义指标不满足时为 `failed`。因此关闭 Judge 的冒烟演示不构成模型质量或发布门禁已通过的证据。完整运行方法见[评测指南](../guides/evaluation.md)。

## 7. 验证入口

- [`test_rag_retrieval_pipeline.py`](../../backend/app/tests/test_rag_retrieval_pipeline.py)：候选融合、去重、父块扩展等行为。
- [`test_rag_project_isolation.py`](../../backend/app/tests/test_rag_project_isolation.py)、[`test_rag_source_policy.py`](../../backend/app/tests/test_rag_source_policy.py)：仓库范围与来源边界。
- [`test_chunking.py`](../../backend/app/tests/test_chunking.py)、[`test_vector_store.py`](../../backend/app/tests/test_vector_store.py)：分块与向量存储契约。
- [`test_rag_qa.py`](../../backend/app/tests/test_rag_qa.py)、[`test_rag_rerank.py`](../../backend/app/tests/test_rag_rerank.py)：问答与重排行为。
- [`test_eval_runner.py`](../../backend/app/tests/test_eval_runner.py)：正式 Agent 路径调用、评估会话回滚、保存证据重评分与同基线比较。
- [`test_bundled_eval_suite.py`](../../backend/app/tests/test_bundled_eval_suite.py)：固定题集与仓库来源匹配、缺失来源拒绝与题目约束。
- [评测指南](../guides/evaluation.md)：固定题集、ChatAgent 运行、RAGAS Judge 与可比回归结果。

这些本地回归测试大量使用隔离数据和替身服务。它们验证实现行为，不替代真实 Milvus、真实 Embedding 或真实模型的端到端评估。
