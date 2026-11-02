# 运行指南

[返回首页](../../README.md) · [配置说明](configuration.md) · [评测指南](evaluation.md) · [API 导航](../api/openapi.md)

DevHarbor 有两条运行路径：先用本地演示理解页面和数据流，再接入真实仓库、模型与向量服务。当前应用面向本机可信环境，后端和前端均应绑定 `127.0.0.1`；身份认证与 GitHub 写入边界见[安全说明](../architecture/security.md)。

## 1. 选择运行方式

| 路径 | 存储与检索 | 模型 | 适合验证 |
| --- | --- | --- | --- |
| Windows 本地演示 | 独立 SQLite、deterministic Embedding、Milvus 关闭；Hybrid 降级到关键词分支 | 默认关闭 LLM 与 RAGAS | 页面、样例 Issue/PR/CI、文件上传、关键词检索、结构化结果 |
| 完整开发环境 | PostgreSQL + Milvus；配置真实 Embedding | 自行配置兼容模型，Rerank 可选 | 仓库同步、向量召回、混合检索、Agent 工具调用、真实模型评测 |

演示模式的向量服务状态应显示 `degraded`。它不是完整向量 RAG 的验收结果，deterministic Embedding 也不是语义模型。

## 2. 安装基础依赖

使用 Python 3.11、Node.js 24 与 Git。完整开发环境还需要 Docker Compose。以下命令都从项目根目录开始；已有 `.env` 时保留原配置，不要覆盖。

Windows PowerShell：

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
py -3.11 -m venv backend/.venv
.\backend\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
Set-Location frontend
npm ci
Set-Location ..
```

macOS / Linux：

```bash
test -f .env || cp .env.example .env
python3.11 -m venv backend/.venv
backend/.venv/bin/python -m pip install -r backend/requirements.txt
cd frontend
npm ci
cd ..
```

基础依赖不包含本地 Qwen Embedding 模型运行库；完整环境继续阅读第 4 节。

## 3. Windows 本地演示

安装完成后，从项目根目录执行：

```powershell
.\scripts\start_rag.ps1
```

脚本会启动后台进程、写入虚构仓库 `devharbor-demo/devharbor-sample-api` 的样例数据，并输出进程 PID 与停止命令。浏览器访问 `http://127.0.0.1:3000`。需要其他端口时：

```powershell
.\scripts\start_rag.ps1 -BackendPort 8001 -FrontendPort 3001
```

脚本使用 `.data/devharbor-local-demo.db`，关闭自动同步和 Milvus；把演示仓库的分数阈值过滤关闭，避免关键词分支的候选被默认阈值全部过滤。进程日志保存在项目根目录 `.data/devharbor-*.log`。脚本结束后会恢复调用终端的原环境变量，子进程保留启动配置。

推荐按以下顺序体验：

1. 在仓库页选择样例仓库，查看 Issue、Pull Request 和 CI 页面。
2. 在项目知识库向该仓库上传 [示例 Markdown](../examples/rag_employee_handbook.md)，等待文件处理完成，查看分片。
3. 在检索测试或 RAG 问答页面查询该文件中的事实，检查来源、检索阶段和回答模式。
4. 打开 Agent 对话、工作流记录和操作草稿，理解工具轨迹与人工复核入口。
5. 按[评测指南](evaluation.md)准备固定用例来源；页面可用不代表真实模型评分已经完成。

如果已在 `.env` 配置可用模型，可执行：

```powershell
.\scripts\start_rag.ps1 -UseConfiguredLLM
```

该参数保留配置中的 LLM/RAGAS 设置，可能调用付费服务；SQLite、deterministic Embedding 和 Milvus 关闭的演示路径仍然保留。脚本不会清空 `.env` 中的 `GITHUB_TOKEN`，也不会将草稿确认变为只读：纯演示应使用空 GitHub Token，并保留虚构仓库。

## 4. 完整开发环境

### 配置模型与存储

编辑根目录 `.env`，按[配置说明](configuration.md)设置模型、Embedding 与独立的 Token 加密密钥。默认 Embedding 为本地 `Qwen/Qwen3-Embedding-0.6B`，安装额外依赖：

```powershell
.\backend\.venv\Scripts\python.exe -m pip install -r backend/requirements-local-embedding.txt
```

macOS / Linux 将解释器路径换为 `backend/.venv/bin/python`。第一次加载本地模型可能下载模型权重；也可以配置独立的兼容 Embedding API。缺少本地依赖时系统会明确报错，不会自动切换到 deterministic 向量空间。

启动基础设施（Compose 只启动基础设施，不包含前后端应用）：

```bash
docker compose up -d postgres etcd minio milvus
docker compose ps
```

PostgreSQL 保存业务数据；Milvus 保存向量；etcd 与 MinIO 是 Milvus 依赖。Compose 中的 Redis 位于 `optional` profile，当前主链路不要求启动它。

### 启动后端

Windows PowerShell，新终端从项目根目录执行：

```powershell
Set-Location backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

macOS / Linux：

```bash
cd backend
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

### 启动前端

另一个终端从项目根目录执行：

```bash
cd frontend
npm run dev -- --hostname 127.0.0.1
```

| 入口 | 默认地址 |
| --- | --- |
| Web 工作台 | `http://127.0.0.1:3000` |
| 后端进程健康检查 | `http://127.0.0.1:8000/health` |
| 交互式 API 文档 | `http://127.0.0.1:8000/docs` |
| OpenAPI JSON | `http://127.0.0.1:8000/openapi.json` |

前端默认调用 `http://localhost:8000`。更改 API 地址时，在 `frontend/.env.local` 设置 `NEXT_PUBLIC_API_BASE_URL`，重启开发服务器或重新构建；Next.js 不会自动读取仓库根目录的 `.env`。

### 连接仓库与验证检索

在仓库页连接 GitHub 仓库或本地 checkout，并配置具有所需仓库权限的 Token。连接流程会同步选定的 Issue、PR、CI 数据，代码 checkout 与分析继续在后台执行；仓库同步状态、API 返回结果和工作流记录可用于核查。

在知识库上传文档后，通过 `GET /api/rag/{repo_id}/status` 查看向量服务状态，通过检索测试查看实际检索阶段、Rerank 是否回退、引用及回答模式。`/health` 返回 `ok` 只说明后端可响应，不代表 Milvus、Embedding 或 LLM 全部可用。

## 5. 常见问题

| 现象 | 排查步骤 |
| --- | --- |
| `sentence-transformers is not installed` | 安装 `requirements-local-embedding.txt`，或显式配置兼容 Embedding API；不要把 LLM API 地址默认视为 Embedding 服务 |
| `Embedding contract mismatch` / 维度错误 | 核对全局 provider、model、dimensions 与已有知识库配置；向量空间迁移见[配置说明](configuration.md) |
| 向量服务 `degraded` | 演示模式属预期；完整模式检查 `docker compose ps`、`docker compose logs milvus` 和 `MILVUS_URI` |
| 上传完成但检索无结果 | 检查文件处理状态、仓库选择、分数阈值和检索阶段；确认文档上传到当前仓库 |
| 访问页面成功但 API 请求失败 | 检查后端端口、`frontend/.env.local`、CORS 配置并重启前端 |
| Judge 异常或缺少指标 | 检查 Judge 凭据、模型、超时；按[评测指南](evaluation.md)只重试异常评分 |
| 端口已占用 | 停止此前启动的实例，或对演示脚本设置不同的前后端端口 |

## 6. 升级与数据保留

升级前备份数据库、上传文件及必要的运行数据，保留已有数据库名称、`MILVUS_COLLECTION` 和 Compose 项目/卷名称，除非正在进行明确的数据迁移。应用启动会建表并执行部分兼容性调整，当前没有完整的生产级数据库迁移流程。

从旧检索策略升级后，可对每个知识库调用 `POST /api/rag/{repo_id}/reindex` 清理历史源码、旧会话等不再进入 RAG 的文档。只重启进程不会完成该重建。该操作会重写索引，应先备份并确认目标仓库。

项目索引清单使用 `.devharbor/index.yml`，PR 快照元数据使用 `.devharbor-pr-snapshot.json`，MCP 工具前缀为 `devharbor_`。相关旧配置需要随迁移同步调整；已有持久化 UUID 的内部命名空间保持兼容。
