# DevHarbor v0.5.0

集成工作台、多 Agent、会话和 MCP 技能。

## 启动

在项目根目录复制 `.env.example` 为 `.env`，配置数据库和可选外部服务。

```powershell
docker compose up -d postgres etcd minio milvus
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

另一终端进入 `frontend`，执行 `npm ci`、`npm run dev`。前端默认端口 3000，后端 8000，健康检查 `/health`，接口文档 `/docs`。

## 当前功能

已接入的 API 路由组：repos, workspaces, code_graph, webhooks, rag, knowledge, search, project_index, issues, pull_requests, ci, reports, action_drafts, chat, conversations, feedback, skills。

导航只包含本版本页面；共享数据模型、接口契约及依赖模块随需要引入。外部服务不可用时请使用独立 SQLite 数据库和显式的 deterministic embedding 演示配置，关闭 Milvus、自动同步及真实模型调用；这不能验证真实向量检索或模型质量。
