# 安全与使用边界

[返回首页](../../README.md) · [运行指南](../guides/getting-started.md) · [配置参考](../guides/configuration.md) · [私密报告安全问题](../../SECURITY.md)

当前版本面向本机、单用户、可信环境下的开发和演示。安全设计的核心是约束工具读取范围、把外部写入停在待确认草稿、保留执行证据；这些机制尚未组成完整的身份与租户安全体系。

## 威胁模型与信任边界

需要保护的资产包括仓库 Token、模型密钥、本地源码、上传文档、对话与评估现场，以及 Token 对应的 GitHub 写入权限。应用假设操作者与宿主机可信；仓库正文、Issue/PR 评论、CI 日志、上传文件和模型输出都可能含错误、恶意指令或敏感内容。

| 边界 | 进入或离开的数据 | 主要风险 |
| --- | --- | --- |
| 浏览器 → FastAPI | 仓库、会话、上传、草稿与配置请求 | 无请求身份时，能访问 API 的人可能读取数据或触发操作。 |
| FastAPI → 本地工作区 / 解析器 | 路径、代码、PDF、DOCX、文本 | 越界读取、秘密混入源码、符号链接及解析资源消耗。 |
| 仓库与文档 → Agent 上下文 | 正文、日志、检索证据、历史记忆 | 提示注入、错误引用、敏感信息进入模型输入。 |
| FastAPI → GitHub / 模型 / 通知服务 | Token、请求内容、证据与反馈摘要 | 错误目的地址、数据外传、超时后的操作结果不确定。 |

系统分层图见 [系统设计](system_design.md)。下文中的“已实现”仅描述当前代码，不能推导出未验证的生产安全保证。

## 已实现控制与缺失控制

| 主题 | 当前已实现 | 当前缺口 |
| --- | --- | --- |
| 身份与权限 | [`permissions.py`](../../backend/app/services/permissions.py) 定义角色与权限；部分路由使用 `require_permission`。 | 该依赖选择数据库中最早的演示用户，必要时创建 `demo-owner`，没有校验请求者身份；并非所有路由都挂载角色检查。 |
| 仓库范围 | 聊天过滤客户端伪造的服务端上下文；MCP 参数覆盖为当前仓库/会话；Milvus 搜索带 `repo_id` 过滤。 | 请求中的仓库范围不等于用户有权访问该仓库，不能作为多租户授权。 |
| 外部写入 | 草稿与执行分离；确认接口检查待确认状态，记录执行结果和审计行。 | 确认者仍是演示用户；缺少独立审批身份、并发执行锁和外部幂等保障。 |
| 本地读取 | 直接工作区读取有路径解析、根目录检查、敏感文件名过滤、文本与大小限制。 | 没有操作系统沙箱；不同搜索/索引路径的检查不完全相同，不能保证所有符号链接与秘密文件都被隔离。 |
| Webhook | 配置 secret 后校验 HMAC-SHA256；仅对已连接仓库调度同步。 | secret 为空时跳过校验；未实现 delivery ID 去重、防重放或应用级限流。 |
| 可追溯性 | 保存工具调用、证据、反馈、评估现场及草稿审计记录。 | 无统一秘密脱敏与防篡改日志体系；记录存在不表示所有行为均通过安全检查。 |

`CORS_ORIGINS` 只控制浏览器跨域访问，不能阻止其他客户端直接调用 API。[`main.py`](../../backend/app/main.py) 在非 production 环境额外允许本机来源；`APP_ENV=production` 仅影响这一规则，不会自动启用登录认证。默认配置中的 `API_HOST` 是 `0.0.0.0`，应按 [启动指南](../guides/getting-started.md) 显式监听 `127.0.0.1`，并检查实际启动命令与容器端口映射。

## 工具执行、提示注入与外部写入

ChatAgent 通过服务端提供的工具映射执行读取、检索和专项分析；当前工作区工具是列文件、读文件和搜索代码，没有向模型开放通用 shell。服务端覆盖仓库/会话参数可以限制部分串库行为，但工具数量限制、风险分类、引用和提示词约定都不是提示注入防火墙。仓库内容可能诱导错误检索、泄露可读内容或生成有害建议，人工应核对证据、目标和最终草稿。[`SafetyAgent`](../../backend/app/services/agents/safety_agent.py) 是关键词风险分类器，不是完整的授权策略引擎。

Agent 生成 `ActionDraft` 时不会直接写入 GitHub。调用 `POST /api/action-drafts/{draft_id}/confirm` 后，后端使用仓库保存的 Token；未提供可用 Token 时，客户端可回退到 `GITHUB_TOKEN`。当前支持创建 Issue、发布 Issue/PR 评论、关闭 Issue 和添加标签。`send_report` 仅在本系统标记为已发送，未接入外部报告发送渠道。实现见 [`action_drafts.py`](../../backend/app/api/routes/action_drafts.py) 与 [`GitHubClient`](../../backend/app/services/github/client.py)。

执行成功时草稿变为 `executed`，异常时变为 `failed`，并写入结果或错误。状态检查会拒绝顺序重复确认；它不保证并发请求只执行一次。外部请求与数据库提交不在同一事务中：超时或保存失败不代表 GitHub 一定没有执行，重建草稿或重试前先检查远端目标。

`DEMO_MODE=true` 不是全局只读开关，也不会禁止确认后的真实 GitHub 写入。确认界面是操作复核点，无法弥补缺失的身份认证。演示和自动测试使用虚构仓库及空 Token；连接真实仓库时只授予需要的最小权限。

## 文件读取、上传与解析

本地仓库接入会校验 Git 工作树，但路径由操作者指定，没有全局受信根目录白名单。直接工作区文件读取会解析真实路径并检查是否仍在工作区内，排除特定敏感文件名，拒绝二进制和大于 250,000 字节的文件；普通源码或非标准名称中的秘密仍可能进入上下文。项目文档索引另外支持 allowlist/exclude 和逐文件根目录检查；这些配置不等于所有工作区工具的权限规则。见 [`chat.py`](../../backend/app/api/routes/chat.py)、[`repos.py`](../../backend/app/api/routes/repos.py)、[`project_indexing.py`](../../backend/app/services/project_indexing.py)。

RAG 上传限制单文件 12 MiB、清洗文件名、限制扩展名，并进行仓库内 checksum 去重；解析器另有文本长度、PDF 页数、DOCX 展开大小等限制。上传与解析仍在应用权限范围内执行，没有恶意文件扫描、用户配额或隔离解析沙箱。只上传可信文件；不要把生产凭据、个人目录或不受信仓库直接作为演示工作区。限制的具体数值以 [`rag.py`](../../backend/app/api/routes/rag.py) 和 [`document_extraction.py`](../../backend/app/services/rag/document_extraction.py) 为准。

## 凭据、日志与模型数据

- **数据库中的 Token：** [`security.py`](../../backend/app/core/security.py) 用 `TOKEN_ENCRYPTION_KEY` 的 SHA-256 派生 Fernet 密钥。示例值 `change-me-in-local-dev` 公开且可预测；保存真实 Token 前设置独立随机值。更换密钥后旧密文需要迁移或重新输入，当前没有自动密钥轮换服务。
- **数据库以外的凭据：** [`code_analysis.py`](../../backend/app/services/code_analysis.py) 的托管 clone 路径会将 Token 放入 HTTP(S) clone URL，它可能进入进程参数和 checkout 的 Git 配置。Fernet 不覆盖这些位置；工作区、`.git`、备份和宿主机进程访问也应按敏感数据保护。`.env`、本地数据库、上传目录和日志不应提交到 Git。
- **模型服务：** 对话、代码片段和检索证据可能发送给配置的 LLM、Embedding 或 Rerank 服务；RAGAS Judge 还接收回答、参考答案和评估证据。只使用允许处理这些数据的服务，关闭 Judge 不会关闭其他模型请求。配置与数据流见 [配置参考](../guides/configuration.md) 和 [RAG 流程](rag_pipeline.md)。
- **脱敏的适用范围：** CI 日志进入部分检索和上下文路径前会通过 [`sanitize_ci_log`](../../backend/app/services/rag/indexing.py) 的规则脱敏并截断。这不是全局内容脱敏；原始同步数据、普通源码、用户问题、反馈和异常信息仍可能包含秘密。`secrets_redacted` 元数据只表示执行了该规则。
- **通知和审计：** 配置 `FEISHU_FEEDBACK_WEBHOOK_URL` 后，负面反馈会携带项目名、提问/回答摘要、反馈和 trace 地址发往飞书。审计行也可能包含草稿正文与外部结果。分享截图、数据库或日志前先检查和脱敏；引用与 trace 是核查线索，不是公开分享许可。

## 网络与 Webhook

当前仓库接入以 GitHub API 为实现，同时允许配置 GitHub-compatible API 地址；这不是已实现其他平台适配的声明。自定义 API 地址可收到请求与 Token，`GitHubClient` 跟随重定向，当前没有统一目的域名/IP 白名单或私网地址阻断。不要从不可信请求或文档中接受 API 地址、clone 地址、模型端点或通知 URL；在部署层约束出站访问，防止访问非预期内网服务或错误发送凭据。HTTP 超时不等于 SSRF 防护。

GitHub Webhook 仅在设置 `GITHUB_WEBHOOK_SECRET` 时校验签名，未设置时不会验证来源。接入前配置独立 secret，并在入口限制访问和请求频率。签名验证与“已连接仓库”匹配不能替代防重放、资源授权或可靠任务队列；重复事件仍可能安排重复同步。见 [`webhooks.py`](../../backend/app/api/routes/webhooks.py)。

## 安全运行与故障处理

1. 按 [启动指南](../guides/getting-started.md) 绑定本机地址；不要公开数据库、Milvus 或应用 API。反向代理认证若以后添加，也需要配套资源授权与后台服务隔离。
2. 用专用目录和最小权限服务账号运行，避免挂载个人主目录、凭据目录或生产配置；上传与 checkout 备份按项目敏感数据管理。
3. 连接真实服务前核对目标地址、Token 范围、随机加密密钥和允许发送的数据；首次验证优先使用测试仓库。未使用的自动同步、模型 Judge 和通知渠道保持关闭。
4. 确认草稿前检查仓库、目标编号、正文和外部影响；失败后先核对 GitHub 远端状态，再决定是否重试。
5. 怀疑泄露时先撤销相关凭据，隔离可疑输入并保留脱敏证据；通过 [SECURITY.md](../../SECURITY.md) 的私密渠道报告。重新配置 Token 不会自动删除旧日志、备份或 Git 配置中的副本。

## 验证依据与未覆盖范围

| 验证主题 | 现有测试或检查 | 不能据此宣称 |
| --- | --- | --- |
| 仓库范围与服务端上下文 | [`test_rag_project_isolation.py`](../../backend/app/tests/test_rag_project_isolation.py) | 已完成用户身份认证或跨租户授权。 |
| CI 日志脱敏、来源限制 | [`test_rag_source_policy.py`](../../backend/app/tests/test_rag_source_policy.py) | 所有来源、日志与秘密均被清除。 |
| 上传解析上限 | [`test_chunking.py`](../../backend/app/tests/test_chunking.py) | 文件无恶意内容或解析器没有漏洞。 |
| 项目文档选择与清理 | [`test_project_indexing.py`](../../backend/app/tests/test_project_indexing.py) | 所有文件访问路径与符号链接均受统一沙箱保护。 |
| 草稿记录与审计 | [`test_expansion_features.py`](../../backend/app/tests/test_expansion_features.py) 的 `send_report` 用例 | 真实 GitHub 写入、并发幂等和完整审批链均已验证。 |

[CI](../../.github/workflows/ci.yml) 使用隔离 SQLite、确定性 Embedding、空外部凭据和模拟服务运行后端测试，检查前端 lint、生产构建与生产依赖审计。它不验证真实 GitHub 写入、不运行付费模型评分，也不能替代 PostgreSQL/Milvus 集成验证、提示注入对抗测试或生产安全评审。运行命令见 [开发与验证](../guides/development.md)。

## 依赖审计记录（2026-10-31）

以下为该日期的历史审计快照，保留用于说明已做的检查与当时的限制，不代表后续日期的实时漏洞状态。复核时应记录依赖锁定版本、扫描时间和原始结果。

前端已升级到 Next.js 15.5.28、React 19.0.9，并修复可兼容升级的传递依赖。`npm audit --omit=dev` 为零漏洞；完整审计仍有 14 条中危记录，属于 ESLint / TypeScript-ESLint / minimatch 开发工具链，没有高危或严重记录。CI 当前阻止生产依赖中的高危和严重漏洞，未将开发工具链的中危项视作已修复。

后端已升级有可用修复的依赖并通过完整测试和依赖兼容性检查。`pip-audit` 仍报告以下 2 个唯一公告（原始结果有 4 条重复记录）；截至检查时，两项公告均没有已公布的修复版本，未通过忽略规则隐藏：

| 依赖 | 已知公告 | 当前调用路径与限制 |
| --- | --- | --- |
| diskcache 5.6.3 | [CVE-2025-69872](https://github.com/advisories/GHSA-w8v5-vhqr-4h9v)：可写缓存目录中的 pickle 反序列化 | 当前 RAGAS Judge 不启用 `DiskCacheBackend`，`llm_factory` 的缓存保持默认关闭。不要加载不可信的磁盘缓存；若以后启用，缓存目录必须只允许服务账号写入。 |
| ragas 0.4.3 | [CVE-2026-6587](https://github.com/advisories/GHSA-95ww-475f-pr4f)：多模态 Faithfulness 的 URL/本地文件处理 | 当前仅实例化固定文本指标，没有调用多模态 Faithfulness。保持这一边界，不开放多模态 URL/文件输入；部署时限制评测进程外连，并跟进上游修复。 |

调用路径判断来自 `backend/app/services/evals/ragas_runner.py` 的当前实现，不代表依赖本身不存在漏洞。升级依赖或启用新指标、缓存功能时必须重新审计。可使用隔离的审计工具从项目根目录复核：`uvx pip-audit -r backend/requirements.txt`；存在上述公告时，非零退出码是预期结果。CI 的依赖安全检查目前覆盖前端生产依赖，后端 `pip check` 仅验证兼容性。

Judge 的固定文本指标与缓存使用情况可继续核查 [`ragas_runner.py`](../../backend/app/services/evals/ragas_runner.py)；依赖审计记录和上文应用控制需要分别评估，不能互相替代。
