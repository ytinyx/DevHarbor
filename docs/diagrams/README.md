# 架构与流程图集

[返回文档导航](../README.md) · [打开离线图集](00_打开图表.html) · [项目目录与代码入口](../guides/project-layout.md)

15 张详细图依据当前 DevHarbor 代码绘制，提供 SVG、PNG 和 Mermaid 源码。浏览页可直接双击打开，无需联网或启动前后端；支持选图、缩放、适宽、全文搜索、节点高亮和源码查看。顶部完整工具区默认收起。

从 00 项目目录找源码入口，再读 01 / 02 理解模块与部署，读 03 / 04 跟踪一次请求。数据结构看 05 与 05a–c。排查工具和失败看 06 / 07 / 09，上下文、评估和 RAG 分别看 08 / 10 / 11。

## 详细图索引

| 编号 | 图表 | PNG | Mermaid |
| --- | --- | --- | --- |
| 00 | [项目目录与文件归属](svg/00_project_directory.svg) | [PNG](png/00_project_directory.png) | [源文件](source/00_project_directory.mmd) |
| 01 | [项目架构与模块职责](svg/01_project_architecture.svg) | [PNG](png/01_project_architecture.png) | [源文件](source/01_project_architecture.mmd) |
| 02 | [技术架构与进程通信](svg/02_technical_architecture.svg) | [PNG](png/02_technical_architecture.png) | [源文件](source/02_technical_architecture.mmd) |
| 03 | [在线执行与工程工作流](svg/03_execution_flow.svg) | [PNG](png/03_execution_flow.png) | [源文件](source/03_execution_flow.mmd) |
| 04 | [对话、协作计划与草稿确认时序](svg/04_chat_sequence.svg) | [PNG](png/04_chat_sequence.png) | [源文件](source/04_chat_sequence.mmd) |
| 05 | [业务数据模型 · 关系总图](svg/05_entity_relationship.svg) | [PNG](png/05_entity_relationship.png) | [源文件](source/05_entity_relationship.mmd) |
| 05a | [会话、工作区与记忆 · 字段细节](svg/05a_sessions_detail.svg) | [PNG](png/05a_sessions_detail.png) | [源文件](source/05a_sessions_detail.mmd) |
| 05b | [知识、索引与评估 · 字段细节](svg/05b_knowledge_detail.svg) | [PNG](png/05b_knowledge_detail.png) | [源文件](source/05b_knowledge_detail.mmd) |
| 05c | [仓库、运行与动作 · 字段细节](svg/05c_runtime_detail.svg) | [PNG](png/05c_runtime_detail.png) | [源文件](source/05c_runtime_detail.mmd) |
| 06 | [工具调用与确认执行](svg/06_tool_execution.svg) | [PNG](png/06_tool_execution.png) | [源文件](source/06_tool_execution.mmd) |
| 07 | [失败处理与恢复边界](svg/07_failure_recovery.svg) | [PNG](png/07_failure_recovery.png) | [源文件](source/07_failure_recovery.mmd) |
| 08 | [上下文、Skill、RAG 与记忆](svg/08_context_memory.svg) | [PNG](png/08_context_memory.png) | [源文件](source/08_context_memory.mmd) |
| 09 | [任务与记录状态](svg/09_task_state.svg) | [PNG](png/09_task_state.png) | [源文件](source/09_task_state.mmd) |
| 10 | [结果验收与离线评估](svg/10_delivery_evaluation.svg) | [PNG](png/10_delivery_evaluation.png) | [源文件](source/10_delivery_evaluation.mmd) |
| 11 | [文档入库与 RAG 问答](svg/11_rag_pipeline.svg) | [PNG](png/11_rag_pipeline.png) | [源文件](source/11_rag_pipeline.mmd) |

## 事实与关系约定

- 这些图解释当前实现，不是未来功能承诺。没有画出未实现的进程重启续跑、身份认证或 exactly-once 外部执行能力。
- ChatAgent 工具循环、工程任务编排、ActionDraft 确认是不同路径。流式 `done`、数据库运行 `success` 和实际业务判断要分别解读。
- 数据图按 [SQLAlchemy 模型](../../backend/app/db/models.py) 绘制，覆盖 36 张表、371 个字段与 47 个声明外键。pgvector 的 `rag_document_vectors` 由后端按需创建，作为补充实体单独标出。
- 为避免 ER 标签互相遮挡，生成器会把冲突标签移至邻近空白区域，并用细虚线引回原关系中点；实体与关系本身不变。
- ER 标签中的 `FK` 表示模型声明外键；`LOGICAL` 表示普通 ID、JSON 或多态目标的应用层关联。Mermaid 的 `..` 表示非标识型关系，不能只凭虚实线判断是否为外键。
- 详细 ER 图保留字段、可空性、索引与约束；桥接实体仅展示主键。部分多字段关联合并标注，完整字段证据见 [model-evidence.json](source/model-evidence.json)。
- [flow-evidence.json](source/flow-evidence.json) 记录流程图的代码依据与边界。RAG 完整问答与 ChatAgent 轻量检索分别说明。

## 文件分工

```text
docs/diagrams/
├─ 00_打开图表.html       # 内嵌图与源码的离线浏览页
├─ README.md             # 图集索引与维护约定
├─ manifest.json         # 源码/成品 SHA256、尺寸、文本数量
├─ source/               # 15 张详细图的语义源、图清单、代码证据
├─ svg/                  # 原生文字矢量图，可无限放大
├─ png/                  # 便于预览与分享的位图
└─ overview/             # 4 张概览的 Mermaid 导出
```

首页封面位于 [docs/assets/hero.svg](../assets/hero.svg)。正文概览放在 `docs/assets/diagrams/`：[系统地图](../assets/diagrams/architecture.svg)、[工程工作流](../assets/diagrams/agent-workflow.svg)、[RAG 概览](../assets/diagrams/rag-pipeline.svg) 和 [项目目录图](../assets/diagrams/project-layout.svg)。项目目录图的 [Mermaid 导出](overview/project-layout.mmd) 可用于对照前端、后端、根目录脚本和文档的分工。

## 修改与重新生成

详细图先改 `source/*.mmd`，标题与顺序在 [atlas.json](source/atlas.json)。生成器从同一份 Mermaid 解析成 SVG，再用本机无界面浏览器导出 PNG 和离线浏览页。阅读成品不需要 Node 或浏览器自动化依赖。

在仓库根目录执行，首次安装需要网络：

```powershell
npm --prefix scripts/documentation-tools/diagrams ci
npm --prefix scripts/documentation-tools/diagrams run build
backend/.venv/Scripts/python.exe scripts/documentation-tools/validate_docs.py
```

生成需要 Node.js、本机 Chrome / Edge 或 Playwright Chromium。可用 `BROWSER_PATH` 指定浏览器。如果系统没有浏览器，在 `scripts/documentation-tools/diagrams` 目录运行 `npx playwright install chromium`。安装依赖后可离线生成图表。[制图依赖清单](../../scripts/documentation-tools/diagrams/package.json)

运行 `node scripts/documentation-tools/diagrams/build.cjs 03_execution_flow` 可重绘一张图。完整成品都存在时会同时重建浏览页。生成后核对文字边界、条件标签、箭头、数据库字段，并验证浏览页的搜索、源码和缩放。

概览使用 Python 标准库生成。[概览生成脚本](../../scripts/documentation-tools/render_docs.py)

```powershell
backend/.venv/Scripts/python.exe scripts/documentation-tools/render_docs.py
```

该脚本生成封面及 4 张概览 SVG、`overview/` 中的 Mermaid 导出；概览的 Python 定义是布局与文字的维护源，导出的 Mermaid 不另行手改。详细图不受该命令影响。

当前实际提供 SVG / PNG，未提供 PDF。SVG 无脚本、外部字体、远程图片或 `foreignObject`；中文显示依赖本机字体。超大 ER 图建议通过浏览页搜索字段，或用 SVG 放大阅读。
