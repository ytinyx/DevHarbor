# DevHarbor 本地演示的能力边界

这是随 DevHarbor 发布的公开项目说明，用于示例回归评测。依据是仓库中的 `scripts/start_rag.ps1` 和根目录 `README.md`，不包含生产运行结果。

Windows 本地演示通过 `scripts/start_rag.ps1` 启动。脚本要求已安装后端虚拟环境依赖和前端 npm 依赖，使用 SQLite 保存演示数据，设置 `EMBEDDING_PROVIDER=deterministic`，关闭 Milvus，并关闭仓库自动同步。默认还关闭 LLM 回答和 RAGAS Judge；只有显式指定 `-UseConfiguredLLM` 时才保留已配置的模型生成设置。

该演示可以检查页面、文档上传解析、关系库存储、Hybrid 检索的关键词分支以及引用展示。它停用演示仓库的分数阈值，避免关键词分支的候选全部被高阈值过滤。向量检索状态会显示 `degraded`，演示成功不能证明完整向量召回、混合向量检索或生产问答质量已经通过验证。

验证完整 RAG 需要启动相应基础设施并配置可用的 Embedding。项目的常规配置使用 PostgreSQL 和 Milvus；Milvus 依赖 etcd、MinIO。默认的本地 Qwen Embedding 需要额外安装 `backend/requirements-local-embedding.txt` 并准备对应模型。选择远程模型时还需配置服务地址与凭据。
