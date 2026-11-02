# 图示源文件与维护

这些图是根据当前代码绘制的架构说明。封面为架构主题插画，不是应用运行截图；没有使用虚构界面或模型生成的文字图片。

| 资产 | 阅读目的 | 对应语义源 |
| --- | --- | --- |
| [首页封面](../assets/hero.svg) | 项目定位、证据与行动的关系 | 使用下方 Python 源文件 |
| [系统地图](../assets/architecture.svg) | 请求入口、上下文、工具、数据与人工确认链 | [architecture.mmd](architecture.mmd) |
| [工程工作流](../assets/agent-workflow.svg) | 依赖就绪、并发批次、失败结果、有限重规划与持久化 | [agent-workflow.mmd](agent-workflow.mmd) |
| [RAG 流水线](../assets/rag-pipeline.svg) | 文件入库、混合召回、配置化精排与回答门控 | [rag-pipeline.mmd](rag-pipeline.mmd) |

## 修改与重新生成

[scripts/render_docs.py](../../scripts/render_docs.py) 是 SVG 和 Mermaid 的统一维护源。使用 Python 3.11 或更高版本即可运行，不需要第三方 Python 包或联网：

```bash
python scripts/render_docs.py
```

修改节点、说明和边关系后重新运行脚本，并一起提交生成的 `.svg`、`.mmd` 和脚本。SVG 使用精确布局；Mermaid 保留语义关系，方便快速查看或改造成演示材料。Mermaid 的自动布局不保证与 SVG 一致。

SVG 只使用原生文本、路径和基本形状，不包含脚本、外部字体、远程图片或 `foreignObject`。为保证 GitHub 渲染一致，标题和标签优先使用短句；长术语放在次级说明中。图形采用以下约定：

- 青绿实线：主流程、工具调用或数据流。
- 灰蓝虚线：支撑关系、按需能力或下一批调度。
- 琥珀色：异常分支、重规划或人工确认关口。
- 重复出现的 PostgreSQL 卡片代表同一个关系库的不同数据组，不代表多个数据库实例。

## 本地视觉检查

浏览器可以直接打开 SVG。已安装前端依赖时，也可使用 Next.js 依赖中的 `sharp` 生成仅供检查的 PNG；下面命令从仓库根目录运行，并将预览写入 Git 忽略的 `.codex_tmp`：

```bash
node -e "const fs=require('fs');const sharp=require('./frontend/node_modules/sharp');fs.mkdirSync('.codex_tmp/docs-preview',{recursive:true});(async()=>{for(const n of ['hero','architecture','agent-workflow','rag-pipeline'])await sharp('docs/assets/'+n+'.svg').png().toFile('.codex_tmp/docs-preview/'+n+'.png')})().catch(e=>{console.error(e);process.exit(1)})"
```

检查字体、文字边界、箭头方向和交叉线，也要在 GitHub README 的实际显示宽度下复核。遇到字体差异，以系统安装的中文字体为准；SVG 没有嵌入字体。

## 更新时核对的代码

- [ChatAgent](../../backend/app/services/agents/chat_agent.py)：LangGraph 的模型与工具循环、Skill 约束。
- [聊天路由](../../backend/app/api/routes/chat.py)：上下文组装、工具注册、工作流结果存储。
- [工作流编排器](../../backend/app/services/agents/workflow_orchestrator.py)：依赖调度、失败传播与有限重规划。
- [文档处理](../../backend/app/services/rag/document_processing.py)：入库状态、切片与 Embedding。
- [检索](../../backend/app/services/rag/retrieval.py) 与 [知识库](../../backend/app/services/rag/knowledge_base.py)：混合召回、重排、阈值、邻块扩展和门控。
- [草稿路由](../../backend/app/api/routes/action_drafts.py)：人工确认、真实写入与审计。

特别注意：ChatAgent 的 `search_similar_documents` 工具和知识库问答的 `retrieve_knowledge` 不是同一条完整流水线；不要把后者所有步骤画到每一次 Agent 检索调用上。
