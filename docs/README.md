# DevHarbor 文档

[返回项目首页](../README.md)

DevHarbor 是面向软件研发场景的 AI 工作台，当前接入 GitHub 仓库数据与本地代码工作区。建议先看真实界面与系统图，再按问题进入对应文档。代码是实现的依据；流程图用于解释当前路径，不表示所有可选服务都已部署。

## 先了解项目

| 入口 | 你会看到什么 |
| --- | --- |
| [项目首页](../README.md) | 项目定位、实际界面、技术亮点与三张流程图 |
| [演示路线](guides/demo.md) | 本地演示的操作顺序、截图来源与可验证效果 |
| [简历与面试讲解](guides/resume-and-interview.md) | 简历表述模板、90 秒介绍、源码证据与设计追问 |

## 理解设计

| 文档 | 关注点 |
| --- | --- |
| [系统设计](architecture/system_design.md) | 界面、API、Agent、检索、业务存储和外部服务的模块关系 |
| [Agent 工作流](architecture/agent_workflow.md) | 对话工具循环、依赖任务调度、有限重规划与操作草稿 |
| [RAG 流程](architecture/rag_pipeline.md) | 数据边界、上传索引、双路召回、重排、上下文和引用 |
| [数据模型](architecture/database_schema.md) | 主要实体的职责与关联 |
| [安全与使用边界](architecture/security.md) | 单用户信任边界、GitHub 写入与待完善部分 |
| [图示源文件](diagrams/README.md) | SVG、Mermaid 与生成脚本的维护方式 |

## 运行与验证

| 文档 | 关注点 |
| --- | --- |
| [安装与启动](guides/getting-started.md) | Windows 轻量演示、macOS / Linux、完整服务与升级 |
| [配置说明](guides/configuration.md) | 数据库、GitHub、LLM、Embedding、Rerank 与上下文参数 |
| [评估指南](guides/evaluation.md) | 固定题集、来源准备、评分状态、重试与回归 |
| [开发说明](guides/development.md) | 本地检查、文档验证与发布前审查 |
| [API 导航](api/openapi.md) | 按功能分组的接口与运行时 OpenAPI 入口 |

项目使用 [MIT 许可证](../LICENSE)。漏洞报告见 [SECURITY.md](../SECURITY.md)，功能历史见 [VERSIONS.md](../VERSIONS.md)。
