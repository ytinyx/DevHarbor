# DevHarbor

当前版本：`v1.0.1`。维护者：[小样（ytinyx）](https://github.com/ytinyx)。

DevHarbor 是一个面向 GitHub PR / Issue 研发协作的全栈 AI Agent 项目。系统会连接仓库数据，分析 Issue、PR diff、CI 日志、项目知识库和本地工作区代码，并返回结构化建议与安全的操作草稿。

项目目录：`DevHarbor`。在项目根目录执行以下启动命令。各版本包含的功能见 [VERSIONS.md](VERSIONS.md)。

当前版本用于本机可信环境下的单用户开发和演示，尚未实现用户登录认证。Agent 生成草稿后，用户确认会触发真实 GitHub 写入；`DEMO_MODE` 不会禁止这些写入。运行前请阅读 [安全与使用边界](docs/architecture/security.md)。

旧部署升级时，请先备份数据，并在 `.env` 中保留已有数据库和 `MILVUS_COLLECTION` 设置；Docker Compose 的项目名、卷名也应保留原值或先完成数据迁移。新安装默认使用 `devharbor` 名称。项目索引配置路径为 `.devharbor/index.yml`，PR 快照元数据为 `.devharbor-pr-snapshot.json`，MCP 工具前缀为 `devharbor_`；已有配置、快照和客户端需同步迁移。持久化 UUID 的内部命名空间保持兼容。

## 核心能力

- 连接并同步 GitHub 仓库中的 Issue、Pull Request、PR 文件、Review 评论、Workflow Run、Job 和日志。
- Issue 分析：分类、优先级、复杂度、推荐负责人、重复候选和行动项。
- PR 审查：摘要、关键变更、风险点、检查清单、测试建议和需要重点关注的文件。
- CI 排障：失败类型、可能原因、排查步骤和相关上下文。
- Agent 对话：`ChatAgent` 使用原生工具调用，串联工作区、记忆、RAG、Issue、PR、CI、周报和安全工具。
- 多 Agent 工作流审查：`WorkflowOrchestrator` 构建 Planner -> 专用 Agent -> Observer -> Synthesis 的闭环，用于 PR 就绪度、阻塞项、优先级和跨领域工程决策。
- Skill Runtime：按用户显式指定或触发条件选择 `SKILL.md`，只向当前任务加载完整指令与受限资源；显式 Skill 校验允许工具，多 Agent 中的专用 Agent 分别加载自己的 Skill，并把版本、激活原因、指令摘要和执行校验写入 trace。
- 工作区代码工具：安全地列出文件、读取文件和搜索本地代码。
- RAG 聚焦 Issue 描述、PR 说明与 Review 评论、失败 CI 日志、项目文档、上传知识和已批准的长期记忆；当前代码走工作区/词法检索，团队与实时状态走结构化查询。
- 生成工程周报。
- 基础 Eval 覆盖 Issue 分类、PR 覆盖度、RAG 命中率、工具 schema 就绪度和结构化输出校验。

## 技术栈

- 后端：Python、FastAPI、Pydantic、SQLAlchemy、PostgreSQL、Milvus、httpx、LangChain。
- Agent 编排：原生工具调用 + 专用分析 Agent。
- 前端：Next.js、TypeScript、Tailwind CSS、React Query。
- 基础设施：Docker Compose 与 `.env` 配置。

## 架构

```mermaid
flowchart TD
    FE["Next.js 前端"] --> API["FastAPI 后端"]
    API --> DB["PostgreSQL"]
    API --> Milvus["Milvus 向量库"]
    API --> GH["GitHub REST API"]
    API --> LLM["OpenAI 兼容 LLM API"]
    API --> Conv["对话 Agent"]
    Conv --> Workflow["工作流编排器"]
    Workflow --> Planner["规划 Agent"]
    Workflow --> Observer["观察 Agent"]
    Workflow --> Synthesis["综合 Agent"]
    Conv --> Workspace["工作区工具"]
    Conv --> Memory["记忆 / RAG 工具"]
    Conv --> Issue["Issue 分析 Agent"]
    Conv --> PR["PR 审查 Agent"]
    Conv --> CI["CI 排障 Agent"]
    Conv --> Report["周报 Agent"]
    Conv --> Safety["安全 Agent"]
    Conv --> Skills["Skill 注册中心"]
```

## 快速开始

环境要求：Python 3.11、Node.js 24，以及 Docker Compose（完整 PostgreSQL/Milvus 环境）。Windows PowerShell：

```powershell
Copy-Item .env.example .env
docker compose up -d postgres etcd minio milvus

cd backend
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --reload
```

macOS / Linux：

```bash
cp .env.example .env
docker compose up -d postgres etcd minio milvus
cd backend
python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --reload
```

另开一个终端：

```bash
cd frontend
npm ci
npm run dev -- --hostname 127.0.0.1
```

根目录 `.env` 由后端和 Docker Compose 读取。前端默认连接 `http://localhost:8000`；如需修改 API 地址，在 `frontend/.env.local` 设置 `NEXT_PUBLIC_API_BASE_URL`，然后重启开发服务或重新构建。Next.js 不会自动读取根目录的 `.env`。

默认地址：

- 后端：http://localhost:8000
- API 文档：http://localhost:8000/docs
- 前端：http://localhost:3000

## RAG 知识问答系统

项目内置 RAG 系统，支持知识库管理、文档解析、段落感知切片、Embedding、向量/关键词混合检索、重排、召回测试、问答工作室、上下文组装、基于证据生成和编号引用。支持 TXT、Markdown、PDF、DOCX、JSON、CSV 与日志文件；重复文件会按 SHA-256 跳过。

对话链路采用混合 RAG：`ContextAssembler` 会在调用 ChatAgent 前按原始问题检索并注入证据；进入推理循环后，模型仍可把 `rag.search_similar_documents` 当作工具，改写查询、连续补查不同资料，并根据多次工具结果交叉验证答案。

项目不会把所有私域数据都向量化。只有需要跨来源语义召回、会反复使用的非结构化知识进入 RAG；源码与配置以当前 checkout 为准，优先通过 `workspace.search_code` 和 `workspace.read_file` 检索；Issue、PR、CI 的状态字段、团队成员和周报等结构化或派生数据直接查数据库/API。RAG 返回的是候选证据，涉及实时状态和当前代码时仍要回到权威数据源核验。

从旧版本升级后，请对每个知识库调用一次 `POST /api/rag/{repo_id}/reindex`。重建会按新边界清理历史向量和旧会话 Document；只部署代码不会主动删除已有索引。

如果只想先验证页面、结构化数据和无模型兜底回答，Windows 本地可以用下面的脚本启动 SQLite 演示环境：

```powershell
.\scripts\start_rag.ps1
```

脚本会关闭 Milvus，使用 deterministic embedding 和启发式重排，并停用演示知识库的 `0.8` 分数阈值，避免只有关键词分支时全部候选都被过滤。因此它可以验证页面、上传解析、关系库存储、Hybrid 的关键词分支和引用展示，但向量检索状态会明确显示 `degraded`，不能用来证明完整 RAG 已经跑通。要验证向量召回、混合检索和重建索引，仍需先按“快速开始”启动 PostgreSQL、etcd、MinIO 和 Milvus。

知识库默认选择 `Qwen/Qwen3-Embedding-0.6B` 与 `qwen3-rerank`。安装 `backend/requirements-local-embedding.txt` 后可运行本地 Qwen Embedding；配置 `DASHSCOPE_API_KEY`、`RERANK_BASE_URL` 后可切换百炼 `text-embedding-v4` 与 `qwen3-rerank`。默认 Embedding 依赖缺失时系统会明确报错，不会在生产配置下静默改用另一套向量空间；只有上面的本地演示脚本会显式选择 deterministic embedding。已经配置 `LLM_API_KEY` 时，可用 `.\scripts\start_rag.ps1 -UseConfiguredLLM` 启用模型生成。

RAG API：

```text
GET  /api/rag/repositories
GET  /api/rag/repositories/{repo_id}
PATCH /api/rag/repositories/{repo_id}/config
POST /api/rag/repositories/{repo_id}/documents
POST /api/rag/repositories/{repo_id}/retrieval-tests
GET  /api/rag/{repo_id}/status
POST /api/rag/{repo_id}/search
POST /api/rag/{repo_id}/ask
POST /api/rag/{repo_id}/reindex
```

## ChatAgent RAGAS 评测

启动主应用后打开 `http://127.0.0.1:3000/evals`，选择仓库、固定评测集和 Top-K，再点击“运行固定 RAGAS 评测”。评测会在隔离会话中真实运行生产 ChatAgent 和工具集，收集预检索与 Agent 二次检索证据，然后使用 Ragas 0.4 Collections API 计算 Context Precision、Context Recall、Faithfulness、Answer Relevancy 和 Agent Goal Accuracy。结果会保存评测集 Hash、阈值、逐题工具轨迹、检索证据、硬规则与失败诊断，便于对同一基线做回归。

仓库随附 [公开项目示例回归基线](docs/datas/evals/rag_cases.json)，包含 5 条有公开文档依据的用例，覆盖本地演示、检索策略、评测异常和证据不足判断。它保留 `devharbor-real-project-rag-baseline` 作为兼容标识，不代表曾通过生产评测，也不附带质量分数。复现前需要：

1. 按前面的启动说明安装依赖并连接待评测仓库；本地演示也可选择脚本创建的 `devharbor-demo/devharbor-sample-api`。
2. 打开“项目知识”并进入**同一个仓库**，点击“添加文件”，上传 [docs/datas/sources](docs/datas/sources) 中的全部 3 个 Markdown 文件，保留文件名。也可逐个调用 `POST /api/rag/repositories/{repo_id}/documents`，使用 multipart 字段 `file` 上传。JSON 评测集不需要上传到知识库，以免将参考答案混入检索证据。
3. 等待文件处理完成，再打开评测页。`GET /api/evals/suites?repo_id=<repository-uuid>` 会显示该基线的 `ready` 和 `missing_sources`；来源未就绪时不能运行。来源按当前仓库内的文件名匹配，上传到另一个仓库不算就绪。上传和索引会使用当前 Embedding 配置；远程提供商会产生服务调用，本地演示使用 deterministic Embedding。
4. 要执行完整语义评分，需配置可用的 ChatAgent 模型、Embedding 和 RAGAS Judge，并启用 `RAGAS_ENABLED`。默认 Judge 复用 `LLM_API_KEY`、`LLM_BASE_URL` 和 `LLM_MODEL`；也可以通过 `.env` 中的 `RAGAS_JUDGE_API_KEY`、`RAGAS_JUDGE_BASE_URL`、`RAGAS_JUDGE_MODEL` 单独配置。以下请求会真实调用已配置的模型服务。仅运行本地测试、导入评测集或上传说明文件不等于完成质量评分；`run_judge=false` 只关闭 Judge，ChatAgent 仍可能调用已配置的模型。

准备完成后，可在评测页运行，或手动提交：

```http
POST /api/evals/rag/run
Content-Type: application/json

{
  "repo_id": "<repository-uuid>",
  "run_judge": true,
  "top_k": 5,
  "suite_id": "devharbor-real-project-rag-baseline"
}
```

提交接口会立即返回 `queued` 状态和 `eval_id`，ChatAgent 与 RAGAS 在后台继续运行。通过 `GET /api/evals/{eval_id}` 轮询 `result.progress`；状态变为 `passed`、`failed`、`error` 或 `no_cases` 时结束。网页会自动轮询，刷新或离开页面不会中断已经提交的任务。

整体通过要求硬规则全部满足，并且五项语义指标都达到 `.env` 中对应的 `RAGAS_*_MIN` 门槛。页面把“执行状态”和“质量状态”分开显示：低分是质量失败；Judge 调用失败或指标缺失是评测不完整，不能伪装成质量结论。

评测失败后可以直接在同一页面继续处理：

- 展开 Case 查看实际回答、参考答案、检索来源、工具轨迹和可执行诊断；
- 对 Judge 超时或缺失指标点击“仅重试异常评分”，复用已经保存的回答和证据，不重新运行 ChatAgent；
- 选择两个相同评测集 Hash、Ragas/Judge 配置和 Top-K 的结果做回归对比；
- 生成 `create_issue` 类型的 ActionDraft，把失败 Case、证据和建议带入人工确认流程，不会直接写入 GitHub。

## 开发检查

后端在 `backend` 目录运行（Windows；macOS / Linux 将解释器路径替换为 `.venv/bin/python`）：

```powershell
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m pytest app/tests -q -o asyncio_default_fixture_loop_scope=function
```

测试使用隔离的 SQLite、确定性 Embedding 和模拟外部服务，不需要 Docker 或真实 API Key。测试通过表示代码回归检查通过，不代表已完成真实模型评分或 PostgreSQL/Milvus 集成验证。

前端在 `frontend` 目录运行：

```bash
npm ci
npm run lint
npm run build
npm audit --omit=dev --audit-level=high --registry=https://registry.npmjs.org
```

[GitHub Actions CI](.github/workflows/ci.yml) 在 push 和 pull request 时执行这些检查，也支持手动运行。它只读取仓库内容，不发布应用、不执行 GitHub 写入，也不使用项目 API 密钥。

## 许可证

本项目采用 [MIT 许可证](LICENSE)。
