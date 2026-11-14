# DevHarbor 的检索来源与当前代码

这是随 DevHarbor 发布的公开项目说明，用于示例回归评测。依据是根目录 `README.md`、`backend/app/services/rag/source_policy.py` 和工作区代码工具的职责。

RAG 用于可复用的非结构化项目知识：Issue 描述、PR 说明与 Review 评论、失败 CI 日志、项目文档、上传知识，以及已批准的长期记忆。Issue 描述、PR 说明和 Review 评论适合参与语义召回；这不表示 Issue、PR 的所有字段都应向量化。

Issue、PR、CI 的当前状态和团队成员等结构化实时事实，应从数据库或 API 查询。RAG 返回的是候选证据，历史文本可能过期，不能单独证明某个 Issue 目前已经关闭或某次 CI 目前已经通过。

当前函数实现、源码和配置以当前 checkout 为准。`workspace.search_code` 用于查找当前代码，`workspace.read_file` 用于读取文件核验。上传文档里的旧代码片段可以作为历史背景；若它与当前 checkout 冲突，判断当前实现时应以当前 checkout 的源码为准。这里描述查询策略，不声明任何具体仓库的当前实现或运行状态。
