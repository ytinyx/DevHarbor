# 配置参考

[返回首页](../../README.md) · [运行指南](getting-started.md) · [评测指南](evaluation.md)

配置契约来自 [`Settings`](../../backend/app/core/config.py) 与 [`.env.example`](../../.env.example)。下表挑选常用项，完整默认值以源码为准；示例中的模型名是项目默认配置，不表示当前账号有对应服务权限。

## 配置加载与路径

从 `backend` 启动后端时，Pydantic 依次读取 `../.env`、`.env`，后者同名项覆盖前者，进程环境变量优先于 dotenv 文件。Docker Compose 从项目根目录 `.env` 读取变量。前端单独读取 `frontend/.env.local`，公开变量会进入浏览器，不能放 Token 或 API Key。

| 参数 | 当前示例 / 默认值 | 用途 |
| --- | --- | --- |
| `DATABASE_URL` | `postgresql+psycopg://devharbor:devharbor@localhost:5432/devharbor` | 业务存储；本地演示脚本改用独立 SQLite |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | 均为 `devharbor` | Compose 数据库初始化值；修改时保持 URL 一致 |
| `CORS_ORIGINS` | localhost / 127.0.0.1 的前端端口列表 | 逗号分隔；非 production 模式还放行本机来源匹配规则 |
| `APP_ENV` | `development` | 设为 `production` 会收紧 CORS 匹配；不会自动启用认证 |
| `VITE_API_BASE_URL` | `http://127.0.0.1:8000` | 放入 `frontend/.env.local`，由 Vite 读取并写入浏览器构建产物；Electron 使用桌面桥提供的后台地址 |
| `REPO_CHECKOUT_DIR` | `.data/repos` | 托管 checkout 根目录 |
| `UPLOAD_DIR` | `.data/uploads` | 上传文件根目录 |

`API_HOST` / `API_PORT` 是配置字段；实际监听地址和端口由启动 Uvicorn 的命令决定。运行指南显式使用 `--host 127.0.0.1 --port 8000`。

## GitHub 与外部通知

| 参数 | 默认 / 示例值 | 行为 |
| --- | --- | --- |
| `GITHUB_TOKEN` | 空 | 未保存仓库专用 Token 时的客户端回退凭据 |
| `GITHUB_API_BASE_URL` | `https://api.github.com` | GitHub API 地址；仓库连接也可保存专用 API 地址 |
| `TOKEN_ENCRYPTION_KEY` | `change-me-in-local-dev` | 用于派生仓库 Token 的 Fernet 密钥；保存真实 Token 前换成独立随机值 |
| `DEMO_MODE` | `.env.example` 为 `false`，代码兜底为 `true` | 允许部分本地缓存/演示路径；**不会阻止草稿确认后的写入** |
| `AUTO_SYNC_ENABLED` | `true` | 启动周期性仓库同步 |
| `AUTO_SYNC_INTERVAL_SECONDS` / `AUTO_SYNC_LIMIT` | `300` / `50` | 同步间隔与单次请求上限 |
| `GITHUB_WEBHOOK_SECRET` | 空 | 非空时校验 `X-Hub-Signature-256`；空值不校验来源 |
| `FEISHU_FEEDBACK_WEBHOOK_URL` | 空 | 启用后把负面反馈通知发送到对应飞书机器人 |
| `FEEDBACK_TRACE_BASE_URL` | `http://localhost:8000` | 反馈通知中的 trace 链接来源；应与实际可访问地址一致 |

`.env`、Token、Webhook 地址、运行数据和日志均不应提交。更换加密密钥后，已有仓库 Token 需要迁移或重新输入。权限模型的当前限制见[安全说明](../architecture/security.md)。

## LLM、Embedding 与 Rerank

三者是独立能力：支持对话的 API 不一定提供 `/embeddings` 或 `/reranks`。先确认服务能力，再分别配置。

### 在界面添加模型供应商

打开左下角 **设置 → 模型供应商 → 添加模型供应商**。选择常用供应商，或切换到“自定义接口”，填写显示名称、API 根地址和密钥。无需密钥的本地模型服务可以留空密钥。

1. 点击“获取可用模型”，或手动填写供应商提供的模型标识。根地址不要追加 `/chat/completions` 或 `/models`。
2. 选择此供应商的默认模型，然后点击“保存供应商”。
3. 回到供应商列表，选择模型并点击“设为默认”。后续聊天、工程分析和知识库回答会使用它，无需重启；已开始的请求保持原配置。

对话供应商使用 **OpenAI 兼容的 Chat Completions 协议**。用于助手工具调用时，模型还需要支持相应的工具调用能力。获取模型目录成功不代表所有模型都可用于聊天，也不代表账号额度和权限已经验证。Embedding 与 Rerank 在「设置 → 检索模型」中配置。Ragas 评估模型仍按其独立配置工作。

保存新供应商不会自动激活。编辑正在使用的供应商时，新的地址、密钥等配置会用于后续请求；如果从目录移除了当前模型，系统会切换到该供应商新的默认模型。点击“恢复服务端原有配置”，或删除当前供应商，会取消界面中的选择并回退到 `LLM_*` 环境配置；环境中未配置可用模型时，继续使用原有的无模型行为。

密钥由后端加密保存在数据库中，列表接口不返回密钥，浏览器也不会将其写入本地持久存储。编辑时密钥留空会保留原值；更换 API 地址时需重新填写密钥，或明确选择移除旧密钥。

「设置 → 检索模型」可以分别保存 Embedding 和 Qwen 兼容的重排服务。配置按 DevHarbor 实例保存在数据库里，密钥沿用上述加密方式。重启后端后，已保存的项目覆盖对应环境变量，恢复后端配置则重新读取启动时的设置。源码版的本地模型需要 `requirements-local-embedding.txt`。目前的桌面安装包包含规则检索和 API 重排所需的依赖，向量检索可通过网页版或源码启动的桌面版运行。

向量存储默认使用 Milvus。也可选「PostgreSQL（pgvector）」，复用 `DATABASE_URL` 指向的 PostgreSQL 数据库。该数据库需要启用 `vector` 扩展，且应用账号需要能创建或读写向量表。选择后可点击「测试连接」。SQLite 实例需要继续使用 Milvus 或关键词检索。

未设置独立 `TOKEN_ENCRYPTION_KEY` 时，系统会在首次保存密钥时生成随机密钥文件，默认位于**项目根目录**的 `.data/model-providers.key`。可用 `DEVHARBOR_PROVIDER_KEY_FILE` 指定其他位置；若已设置非默认的 `TOKEN_ENCRYPTION_KEY`，则优先用它加密。备份或迁移需要同时保留数据库与实际使用的密钥文件或加密配置。丢失或更换加密密钥后，需要重新输入供应商的 API 密钥。这些文件和配置不应提交到代码仓库。

| 参数 | 当前默认 / 示例值 | 用途 |
| --- | --- | --- |
| `LLM_API_KEY` | 空 | 对话与分析模型凭据 |
| `LLM_BASE_URL` / `LLM_MODEL` | `https://api.deepseek.com` / `deepseek-v4-pro` | OpenAI 兼容对话端点和模型 |
| `RAG_LLM_ENABLED` | `true`（代码默认） | 控制 RAG 问答生成；无模型时可返回摘录式回答 |
| `EMBEDDING_PROVIDER` | `qwen_local` | 支持 `qwen_local`、`local`、`openai_compatible`、`dashscope`、`deterministic` |
| `EMBEDDING_MODEL` / `EMBEDDING_DIMENSIONS` | `Qwen/Qwen3-Embedding-0.6B` / `1024` | 全局向量空间契约 |
| `LOCAL_EMBEDDING_DEVICE` | 空 | 本地模型运行设备；空值由模型库选择 |
| `EMBEDDING_BASE_URL` / `EMBEDDING_API_KEY` | 空 | 兼容 Embedding API 的独立端点与凭据 |
| `DASHSCOPE_API_KEY` | 空（代码支持） | `dashscope` Embedding 与 Qwen Rerank 的凭据 |
| `DASHSCOPE_EMBEDDING_BASE_URL` | `https://dashscope.aliyuncs.com/compatible-mode/v1` | DashScope Embedding 端点 |
| `RERANK_API_KEY` / `RERANK_BASE_URL` | 空（代码支持） | Qwen API 重排；Key 未配置时尝试 `DASHSCOPE_API_KEY` |
| `VECTOR_BACKEND` | `milvus` | 可选 `milvus` 或 `pgvector`，后者复用应用的 PostgreSQL |
| `MILVUS_ENABLED` / `MILVUS_URI` | `true` / `http://localhost:19530` | 向量服务开关与连接 |
| `MILVUS_TOKEN` / `MILVUS_COLLECTION` | 空 / `devharbor_rag_qwen1024` | Milvus 凭据与集合名称 |
| `PGVECTOR_COLLECTION` | `devharbor_rag_qwen1024` | pgvector 的向量索引命名空间 |

本地模型需安装 [`requirements-local-embedding.txt`](../../backend/requirements-local-embedding.txt)。上传和查询按全局 `EMBEDDING_MODEL` 加载对应本地模型；保留的 `LOCAL_EMBEDDING_MODEL` 不会覆盖知识库向量契约。

`openai_compatible` 的凭据按 `EMBEDDING_API_KEY → OPENAI_API_KEY → LLM_API_KEY` 回退，端点按 `EMBEDDING_BASE_URL → LLM_BASE_URL` 回退。建议明确填写独立的 Embedding 配置，避免调用不支持该能力的对话端点。远程服务不可用时不会静默生成另一种向量。

Rerank 的默认知识库配置为 `qwen_api` / `qwen3-rerank`。请求失败或未配置时可以回退到本地启发式重排，检索 trace 会保留 `fallback` 与原因；这与 Embedding 的严格契约不同。`RERANK_BASE_URL` 可以是完整 `/reranks` 地址，或由代码追加该后缀的基地址。

## 每个知识库的检索设置

通过 `PATCH /api/rag/repositories/{repo_id}/config` 或知识库页面修改。模型可用性目录见 `GET /api/rag/models`，实际运行状态见 `GET /api/rag/{repo_id}/status`。

| 字段 | 支持范围 | 作用 |
| --- | --- | --- |
| `retrieval_method` | `vector` / `fulltext` / `hybrid` | 向量、关键词或混合召回 |
| `top_k` | 1–20 | 知识库候选输出数量；`/search` 与 `/ask` 的单次请求参数上限为 10 |
| `rerank_enabled` | 布尔值 | 是否执行重排 |
| `rerank_provider` / `rerank_model` | API 或启发式配置 | 选择重排方式 |
| `score_threshold_enabled` / `score_threshold` | 布尔值 / 0–1 | 对候选执行最低分过滤 |
| `chunk_size` / `chunk_overlap` | 200–4000 / 0–1000 | 分片长度与重叠；overlap 必须小于 chunk_size |

通过界面更换向量模型或存储后，重启后端会切换到新的向量索引。进入各项目的知识库设置重建已有文档的向量索引，再切换到向量或混合检索。直接修改 `.env` 时，需要手动保持知识库配置与后端模型一致，并为新的向量空间指定独立索引。

## 上下文预算与评测

| 配置组 | 核心字段 | 说明 |
| --- | --- | --- |
| 输入预算 | `CONTEXT_MAX_INPUT_TOKENS=24000`、`CONTEXT_RESERVED_RESPONSE_TOKENS=3000` | 控制上下文组装预算，按估算 token 裁剪 |
| 自动压缩 | `CONTEXT_AUTO_COMPACT_ENABLED`、`CONTEXT_*BUFFER_TOKENS`、`CONTEXT_COMPACT_KEEP_RECENT_MESSAGES` | 控制压缩触发点、保留近期消息与结构化记忆 |
| 动态窗口 | `CONTEXT_DYNAMIC_MODEL_WINDOW_ENABLED`、`CONTEXT_MODEL_WINDOW_TOKENS` | 按模型窗口或显式配置调整预算 |
| Prompt 缓存 | `PROMPT_CACHE_ENABLED`、`PROMPT_CACHE_KEY`、`PROMPT_CACHE_RETENTION` | 请求层缓存提示；是否命中取决于模型服务支持 |
| 工作流超时 | `WORKFLOW_TASK_TIMEOUT_SECONDS=90`（代码默认） | 专家任务执行超时 |
| RAGAS | `RAGAS_ENABLED`、`RAGAS_JUDGE_*`、`RAGAS_*_MIN` | Judge、超时与通过门槛，详见[评测指南](evaluation.md) |

保持 `.env.example` 的完整上下文预算参数作为起点，通过实际 trace 调整；不能把配置中的 token 数或评分门槛当作实测性能/质量结论。
