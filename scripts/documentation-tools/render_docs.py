"""Render repository documentation SVGs and Mermaid sources (standard library only).

Run from the repository root: python scripts/documentation-tools/render_docs.py
The Python definitions below are the canonical editable source for the SVG assets.
No network requests, external fonts, or image-generation service is required.
"""
from __future__ import annotations

from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / "docs" / "assets" / "diagrams"
DIAGRAMS = ROOT / "docs" / "diagrams" / "overview"
NAVY = "#10243b"
INK = "#17334c"
MUTED = "#5c7185"
TEAL = "#087f8c"
BLUE = "#4267b2"
AMBER = "#aa6421"
FONT = "'Segoe UI','Microsoft YaHei','PingFang SC',Arial,sans-serif"


class Canvas:
    def __init__(self, name: str, title: str, subtitle: str, height: int):
        self.name, self.height = name, height
        self.parts = [f'''<svg xmlns="http://www.w3.org/2000/svg" width="1400" height="{height}" viewBox="0 0 1400 {height}" role="img" aria-labelledby="title desc">
<title id="title">{escape(title)}</title><desc id="desc">{escape(subtitle)}</desc>
<defs>
 <marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M1 1 L7 4 L1 7" fill="none" stroke="{TEAL}" stroke-width="1.5"/></marker>
 <marker id="muted-arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M1 1 L7 4 L1 7" fill="none" stroke="#8aa2b6" stroke-width="1.5"/></marker>
 <marker id="amber-arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M1 1 L7 4 L1 7" fill="none" stroke="{AMBER}" stroke-width="1.5"/></marker>
 <linearGradient id="header" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#10243b"/><stop offset="1" stop-color="#173d54"/></linearGradient>
</defs>
<rect width="1400" height="{height}" fill="#f5f8fc"/>
<rect width="1400" height="174" fill="url(#header)"/>
<path d="M0 173 H1400" stroke="#35bec1" stroke-width="3"/>
<g font-family="{FONT}">''']
        self.text(64, 43, "DEVHARBOR  /  ENGINEERING NOTES", 13, "#87d9dc", weight=650, spacing=2)
        self.text(64, 93, title, 32, "#ffffff", weight=700)
        self.text(64, 133, subtitle, 17, "#c4d9e6")
        self.graph = ["flowchart TD"]
        self.nodes: dict[str, tuple[int, int, int, int]] = {}
        self.sections = []

    def text(self, x, y, value, size=18, fill=INK, weight=400, anchor="start", spacing=None):
        extra = f' letter-spacing="{spacing}"' if spacing else ""
        self.parts.append(f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" text-anchor="{anchor}" fill="{fill}"{extra}>{escape(str(value))}</text>')

    def rect(self, x, y, w, h, fill="white", stroke="#d9e4ee", radius=12):
        self.parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" fill="{fill}" stroke="{stroke}"/>')

    def section(self, y, number, title, note="", overlay=False):
        if not overlay:
            self.sections.append((y, number, title, note))
        else:
            width = 55 + sum(21 if ord(char) > 127 else 12 for char in title)
            self.rect(58, y - 24, width, 34, "#f5f8fc", "none", 0)
            if note:
                width = sum(14 if ord(char) > 127 else 7.5 for char in note)
                self.rect(1328 - width, y - 21, width + 16, 30, "#f5f8fc", "none", 0)
        self.rect(64, y - 20, 28, 26, TEAL, TEAL, 6)
        self.text(78, y - 1, number, 13, "white", 700, "middle")
        self.text(105, y, title, 21, INK, 650)
        if note:
            self.text(1336, y, note, 14, MUTED, anchor="end")

    def node(self, key, x, y, title, sub="", w=224, h=90, tone="default", tag=None):
        colors = {"default": ("#ffffff", "#d1dfea", TEAL), "blue": ("#eef4ff", "#bfcee9", BLUE), "teal": ("#e9f7f6", "#addbd7", TEAL), "amber": ("#fff6e9", "#e6c9a5", AMBER), "dark": (NAVY, NAVY, "#51d0ce")}
        bg, stroke, accent = colors[tone]
        self.rect(x, y, w, h, bg, stroke)
        self.parts.append(f'<path d="M{x + 15} {y + 20} V{y + h - 20}" stroke="{accent}" stroke-width="3" stroke-linecap="round"/>')
        self.text(x + 30, y + 34, title, 20, "white" if tone == "dark" else INK, 650)
        if sub:
            lines = sub.split("\n")
            for idx, line in enumerate(lines):
                self.text(x + 30, y + 60 + idx * 20, line, 14, "#bfd7e5" if tone == "dark" else MUTED)
        self.nodes[key] = x, y, w, h
        self.graph.append(f'  {key}["{title}<br/>{sub.replace(chr(10), " · ")}"]')

    def path(self, points, label="", label_at=None, dashed=False, amber=False, arrow=True):
        stroke = AMBER if amber else "#8aa2b6" if dashed else TEAL
        marker = "amber-arrow" if amber else "muted-arrow" if dashed else "arrow"
        d = "M" + " L".join(f"{x} {y}" for x, y in points)
        dash_attr = ' stroke-dasharray="6 5"' if dashed else ""
        marker_attr = f' marker-end="url(#{marker})"' if arrow else ""
        self.parts.append(f'<path d="{d}" fill="none" stroke="{stroke}" stroke-width="2" stroke-linejoin="round"{dash_attr}{marker_attr}/>')
        if label:
            lx, ly = label_at or points[len(points) // 2]
            # The quiet background prevents line-through-label collisions.
            label_w = sum(14 if ord(c) > 127 else 7.5 for c in label) + 16
            self.rect(lx - label_w / 2, ly - 17, label_w, 24, "#f5f8fc", "none", 4)
            self.text(lx, ly, label, 14, stroke, anchor="middle")

    def edge(self, start, end, direction="right", label="", dashed=False, amber=False):
        x, y, w, h = self.nodes[start]
        xx, yy, ww, hh = self.nodes[end]
        if direction == "right":
            pts = [(x+w, y+h/2), (xx, yy+hh/2)]
        elif direction == "left":
            pts = [(x, y+h/2), (xx+ww, yy+hh/2)]
        elif direction == "down":
            pts = [(x+w/2, y+h), (xx+ww/2, yy)]
        else:
            pts = [(x+w/2, y), (xx+ww/2, yy+hh)]
        midpoint = ((pts[0][0]+pts[-1][0])/2, (pts[0][1]+pts[-1][1])/2-10)
        self.path(pts, label, midpoint, dashed, amber)
        relation = "-.->" if dashed else "-->"
        self.graph.append(f'  {start} {relation}{"|" + label + "|" if label else ""} {end}')

    def relate(self, start, end, points, label="", label_at=None, dashed=False, amber=False):
        self.path(points, label, label_at, dashed, amber)
        self.graph.append(f'  {start} {"-.->" if dashed else "-->"}{"|" + label + "|" if label else ""} {end}')

    def note(self, y, title, lines, tone="blue", h=96):
        bg, border, accent = ("#eef4ff", "#d2def0", BLUE) if tone == "blue" else ("#fff6e9", "#ecd6b9", AMBER)
        self.rect(64, y, 1272, h, bg, border)
        self.text(86, y + 29, title, 17, accent, 650)
        for i, line in enumerate(lines):
            self.text(86, y + 55 + i * 23, line, 15, MUTED)

    def save(self, flow_legend=True):
        for y, number, title, note in self.sections:
            self.section(y, number, title, note, overlay=True)
        if flow_legend:
            self.path([(64, self.height-62), (116, self.height-62)], arrow=True)
            self.text(126, self.height-57, "主流程 / 数据流", 13, MUTED)
            self.path([(326, self.height-62), (378, self.height-62)], dashed=True)
            self.text(388, self.height-57, "支撑关系 / 按需分支", 13, MUTED)
            self.path([(632, self.height-62), (684, self.height-62)], amber=True)
            self.text(694, self.height-57, "异常 / 重规划 / 人工关口", 13, MUTED)
            self.text(1336, self.height-57, "CODE-ALIGNED  ·  EDITABLE SVG", 12, MUTED, anchor="end", spacing=1)
        self.parts.append("</g></svg>\n")
        ASSETS.mkdir(parents=True, exist_ok=True)
        DIAGRAMS.mkdir(parents=True, exist_ok=True)
        (ASSETS / f"{self.name}.svg").write_text("\n".join(self.parts), encoding="utf-8")
        (DIAGRAMS / f"{self.name}.mmd").write_text("%% Generated by scripts/documentation-tools/render_docs.py; semantic flow, SVG has curated layout.\n" + "\n".join(self.graph) + "\n", encoding="utf-8")


def architecture():
    c = Canvas("architecture", "系统地图 · 从上下文到工程行动", "Web 与 Electron 共用 React 工作台，分别连接各自的 FastAPI 后端。", 1415)
    c.section(216, "01", "请求入口与对话主链", "桌面后端由 Electron 启动，使用动态本机端口和启动令牌")
    for key, x, title, sub in [
        ("ui",64,"React 工作台","Web / Electron\n对话 · 知识库 · PR / CI"),
        ("api",326,"FastAPI 路由","请求校验 · 仓库 / 会话范围"),
        ("context",588,"ContextAssembler","历史 · 记忆 · 预检索证据"),
        ("chat",850,"ChatAgent","LangGraph · model ↔ tools"),
        ("llm",1112,"LLM 接口","OpenAI-compatible API"),
    ]:
        c.node(key,x,248,title,sub,tone="dark" if key=="chat" else "blue")
    for a,b in [("ui","api"),("api","context"),("context","chat"),("chat","llm")]: c.edge(a,b)
    c.section(405,"02","上下文与运行约束","虚线表示对主链的支撑")
    for key,x,title,sub in [
        ("scope",64,"仓库 / 会话定位","repo_id · conversation_id"),
        ("budget",326,"上下文预算管理","压缩历史 · 保留近期消息"),
        ("memory",588,"消息与证据投影","MessageStore / EvidenceStore"),
        ("skill",850,"SkillRegistry","按需激活 · 工具白名单"),
        ("trace",1112,"流事件与轨迹","SSE · 工具事件 · 引用"),
    ]: c.node(key,x,437,title,sub)
    c.relate("scope","api",[(176,437),(176,371),(438,371),(438,338)],"范围",(304,366),True)
    c.relate("budget","context",[(438,437),(438,391),(644,391),(644,338)],"预算",(533,386),True)
    c.edge("memory","context","up",dashed=True)
    c.edge("skill","chat","up",dashed=True)
    c.relate("chat","trace",[(1074,293),(1093,293),(1093,411),(1224,411),(1224,437)],dashed=True)
    c.section(596,"03","注册工具与专题能力","工具选择由模型决策；工程工作流另有依赖调度")
    tool_data = [
        ("workspace",64,"工作区工具","list_files · read_file\nsearch_code"),
        ("mcp",326,"MCP 记忆工具","devharbor_*\nstdio memory server"),
        ("rag",588,"RAG 检索工具","search_similar_documents\n候选证据与来源"),
        ("specialist",850,"专题分析 Agent","Issue · PR · CI\nReport · Safety"),
        ("workflow",1112,"工程工作流","Planner · Observer\nSynthesis · 任务运行记录"),
    ]
    for key,x,title,sub in tool_data: c.node(key,x,644,title,sub,h=112,tone="teal")
    c.path([(900,338),(900,365),(830,365),(830,567),(1380,567),(1380,621),(176,621)],arrow=False)
    for key,x,_,_ in tool_data:
        c.path([(x+112,621),(x+112,644)])
        c.graph.append(f"  chat --> {key}")
    c.section(819,"04","证据与持久化","业务库支持 SQLite 与 PostgreSQL；向量索引按配置启用")
    stores = [
        ("checkout",64,"当前 checkout","本地仓库 · 隔离工作树\n路径校验后的只读检索"),
        ("memdb",326,"对话 / 长期记忆","关系库\n会话、消息、批准的笔记"),
        ("documents",588,"文档 / 向量","Document → BM25\nMilvus / PostgreSQL pgvector\n按 repo_id 限定检索范围"),
        ("snapshot",850,"GitHub 同步快照","Issue / PR / CI · SQL\nGitHub REST API"),
        ("runs",1112,"运行 / 任务记录","关系库\nAgentWorkflowRun / TaskRun"),
    ]
    for key,x,title,sub in stores: c.node(key,x,851,title,sub,h=112,tone="blue")
    for tool,store in zip(tool_data,stores): c.edge(tool[0],store[0],"down")
    c.section(1028,"05","写入动作的确认链","Agent 生成草稿；人工确认接口执行真实 GitHub 写入")
    for key,x,title,sub in [
        ("safety",64,"SafetyAgent","把写意图变成结构化草稿"),
        ("draft",326,"ActionDraft","保存待确认的操作参数"),
        ("confirm",588,"人工确认 API","用户显式确认草稿"),
        ("permission",850,"权限校验","支持的动作 · 演示角色权限"),
        ("write",1112,"执行与审计","GitHub REST → AuditLog"),
    ]: c.node(key,x,1060,title,sub,tone="amber" if key=="confirm" else "default")
    for a,b in [("safety","draft"),("draft","confirm"),("confirm","permission"),("permission","write")]: c.edge(a,b,amber=a=="confirm" or b=="confirm")
    c.note(1186,"本机运行与仓库范围",["桌面默认 SQLite + BM25；可选 PostgreSQL 业务库，启动连接失败时可回退 SQLite。浏览器演示使用独立 SQLite。","当前代码走 checkout 检索；团队工作区按仓库列表聚合周报，GitHub 真实写入由操作草稿确认触发。"],"amber",96)
    c.save()


def workflow():
    c = Canvas("agent-workflow","工程工作流 · 规划、执行、观察与综合","依赖图按就绪批次执行；报告生成后记录任务结果，最终随请求事务提交。",1436)
    c.section(216,"01","建立任务图","ChatAgent 工具和已确认的计划都可以启动工程审查")
    xs=[64,394,724,1054]
    row=[("entry","工程审查入口","workflow.run_engineering_review\n或计划预览 → 用户确认执行"),("planner","规则规划 Planner","目标 · 范围 · 验收标准"),("spec","WorkflowSpec","小任务 · dependencies\nmax_parallel_tasks / timeout"),("ready","依赖就绪筛选","成功依赖已完成 → ready")]
    for (key,title,sub),x in zip(row,xs): c.node(key,x,250,title,sub,w=282,h=112,tone="blue")
    for a,b in [("entry","planner"),("planner","spec"),("spec","ready")]: c.edge(a,b)
    c.section(421,"02","有界并行与结果归并","只调度当前 ready 的任务批次")
    row2=[("results","归并任务结果","success / error / skipped"),("run","单任务执行","超时控制 · 异常归一化"),("runner","注册任务执行器","task_type → runner"),("batch","并发批次","asyncio.gather\n受 max_parallel_tasks 限制")]
    for (key,title,sub),x in zip(row2,xs): c.node(key,x,455,title,sub,w=282,h=112,tone="teal")
    c.edge("ready","batch","down")
    for a,b in [("batch","runner"),("runner","run"),("run","results")]: c.edge(a,b,"left")
    c.relate("results","ready",[(205,455),(205,394),(1380,394),(1380,306),(1336,306)],"更新依赖，调度下一批",(1040,389),True)
    c.text(64,621,"同一执行器协议下的细分任务",16,MUTED,650)
    tasks=[("issue","Issue 分析"),("pr","PR 审查"),("ci","CI 排障"),("knowledge","RAG 检索"),("health","仓库健康"),("safe","安全检查")]
    for i,(key,title) in enumerate(tasks):
        x=64+i*216
        c.node(key,x,652,title,"结构化 TaskResult",w=192,h=86)
        c.path([(x+96,637),(x+96,652)],dashed=True)
        c.graph.append(f"  runner -.-> {key}")
    c.path([(865,567),(865,637),(160,637)],dashed=True,arrow=False)
    c.path([(865,637),(1240,637)],dashed=True,arrow=False)
    c.section(807,"03","观察、有限重规划与最终综合","默认最多重规划 1 次；配置上限为 2 次")
    row3=[("observer","规则观察 Observer","失败 · 冲突 · 缺证据\n风险 · 人工确认事项"),("replan","重规划判断","需要补充任务且未达上限\n重复任务图则停止"),("synthesis","结构化综合 Synthesis","整合结论 · 风险 · 行动项"),("report","WorkflowReport","answer · citations · metrics\nagent_events · tool_calls")]
    for (key,title,sub),x in zip(row3,xs): c.node(key,x,841,title,sub,w=282,h=112,tone="amber" if key=="replan" else "blue")
    c.relate("results","observer",[(205,567),(205,597),(38,597),(38,897),(64,897)],label="本轮结果",label_at=(99,779))
    for a,b in [("observer","replan"),("replan","synthesis"),("synthesis","report")]: c.edge(a,b)
    c.relate("replan","planner",[(535,953),(535,993),(20,993),(20,229),(535,229),(535,250)],"新增任务，复用成功结果",(255,988),amber=True)
    c.node("persist",1054,1025,"报告后的结果记录","AgentWorkflowRun\nAgentTaskRun\nflush → 外层事务 commit",w=282,h=112,tone="dark")
    c.edge("report","persist","down")
    # This is a magnified explanation of the result collector above, not an
    # independent stage. A local reference avoids a long edge through the graph.
    c.rect(64,1025,612,132,"#fff6e9","#e6c9a5")
    c.text(86,1053,"归并任务结果的三类异常来源",18,AMBER,650)
    for y,lead,detail in [
        (1083,"依赖失败 → skipped","后继任务被失败依赖阻断"),
        (1110,"无可执行任务 → error","循环或缺失依赖"),
        (1137,"任务异常 / 超时 → error","转换为结构化错误结果"),
    ]:
        c.text(86,y,lead,16,INK,600)
        c.text(355,y,detail,15,MUTED)
    c.rect(724,1035,282,112,"#e9f7f6","#addbd7")
    c.text(748,1069,"归并任务结果",20,INK,650)
    c.text(748,1096,"对应上方同名节点",14,MUTED)
    c.text(748,1118,"统一进入后续观察与综合",14,MUTED)
    c.path([(676,1091),(724,1091)],amber=True)
    c.graph.extend([
        '  blocked["依赖失败 → skipped<br/>后继任务被失败依赖阻断"]',
        '  cycle["无可执行任务 → error<br/>循环或缺失依赖"]',
        '  error["任务异常 / 超时 → error<br/>转换为结构化错误结果"]',
        '  exceptions["三类异常来源<br/>统一形成结构化 TaskResult"]',
        "  ready --> blocked", "  ready --> cycle", "  run --> error",
        "  blocked --> exceptions", "  cycle --> exceptions",
        "  error --> exceptions", "  exceptions --> results",
    ])
    c.note(1185,"计划确认与操作确认",["计划入口先调用 /api/chat/plan 预览任务图；用户确认后由 /api/chat/plan/execute/stream 执行。","工程审查可以给出待确认事项；GitHub 写入通过 ActionDraft 的独立确认接口执行。"],"blue",100)
    c.save()


def rag():
    c = Canvas("rag-pipeline","RAG 流水线 · 入库、混合召回与证据门控","文档片段进入业务库供 BM25 使用，可选写入 Milvus 或 PostgreSQL pgvector。",1960)
    c.section(216,"01","文档入库","BackgroundTasks 在后端进程内处理；失败后可手动重试")
    row=[("upload",64,"文件上传","TXT / MD / PDF / DOCX 等"),("hash",326,"SHA-256 去重","同仓库识别重复文件"),("queued",588,"后台入库登记","KnowledgeSourceDocument\nBackgroundTasks · 进程内\nqueued → parsing"),("parse",850,"格式提取","提取文本与文档结构"),("split",1112,"结构感知切片","父子块 · 标题 · 来源元数据")]
    for key,x,title,sub in row: c.node(key,x,250,title,sub,h=112,tone="blue")
    for a,b in [("upload","hash"),("hash","queued"),("queued","parse"),("parse","split")]: c.edge(a,b)
    row2=[("state",64,"处理结果状态","completed / failed\n失败时记录错误"),("vector_store",326,"可选向量写入","Milvus / PostgreSQL pgvector\nrepo_id · source_id"),("sql",588,"Document 关系表","正文 · 切片 · 来源元数据"),("embed",850,"可选批量 Embedding","启用时固定模型与维度\n关闭时进入 indexing"),("normalize",1112,"片段准备","父文档关联 · 内容规范化")]
    for key,x,title,sub in row2: c.node(key,x,430,title,sub,h=112,tone="teal")
    c.edge("split","normalize","down")
    for a,b in [("normalize","embed"),("embed","sql"),("sql","vector_store"),("vector_store","state")]: c.edge(a,b,"left")
    c.relate("sql","state",[(700,542),(700,562),(176,562),(176,542)],"向量存储未启用：保存关键词索引资料",(438,563),dashed=True)
    c.note(577,"其他证据来源",["GitHub 同步按来源白名单处理 Issue、PR 与失败 CI 日志；CI 日志先脱敏。","当前源代码由 workspace.search_code / read_file 检索；实时状态可回到数据库或 GitHub API 核查。"],"blue",98)
    c.section(735,"02","双路召回与候选整理","hybrid 同时召回；fulltext 走 BM25，vector 走向量")
    c.node("scope",64,780,"问题与检索范围","repo_id · source_types\nmetadata filters",h=112,tone="blue")
    c.node("query",326,780,"Query Embedding","使用知识库向量配置",h=112)
    c.node("vector",588,780,"向量召回","Milvus / PostgreSQL pgvector\n按仓库与来源过滤",h=112)
    c.node("keyword",326,970,"BM25 召回","对文档文本计算词项分数",h=112)
    c.node("fusion",588,970,"加权融合","向量 / 词项 / 双命中奖励",h=112,tone="teal")
    c.node("dedup",850,970,"内容去重","文本指纹 · 近重复片段",h=112)
    c.node("parent",1112,970,"同父块限额","避免单文档占满候选",h=112)
    c.edge("scope","query"); c.edge("query","vector")
    c.relate("scope","keyword",[(176,892),(176,1026),(326,1026)],"同一问题 / 范围",(193,945))
    c.edge("vector","fusion","down",label="向量候选")
    c.edge("keyword","fusion",label="词项")
    c.edge("fusion","dedup"); c.edge("dedup","parent")
    c.rect(850,780,486,112,"#fff6e9","#ecd6b9")
    c.text(874,813,"向量后端不可用时",18,AMBER,650)
    c.text(874,843,"hybrid：保留 BM25，记录 unavailable",15,MUTED)
    c.text(874,868,"vector：向上抛出不可用错误（API 503）",15,MUTED)
    c.section(1150,"03","知识库精排与上下文准备","retrieve_knowledge：逐阶段保留 pipeline_trace")
    row3=[("compress",64,"上下文压缩","按 token 预算收敛证据"),("threshold",326,"分数阈值过滤","依据知识库配置启用"),("neighbors",588,"邻块扩展","同父文档 · 同一版本"),("topk",850,"Top-K 选择","限制进入上下文的候选"),("rerank",1112,"候选重排","Qwen rerank / heuristic\n远程失败记录 fallback")]
    for key,x,title,sub in row3: c.node(key,x,1184,title,sub,h=112,tone="blue")
    c.edge("parent","rerank","down")
    for a,b in [("rerank","topk"),("topk","neighbors"),("neighbors","threshold"),("threshold","compress")]: c.edge(a,b,"left")
    c.section(1365,"04","回答前的证据关口","引用跟随真实检索结果；不足时不强行拼接结论")
    c.node("gate",64,1399,"Answer Gate","判断证据充分性",h=112,tone="dark")
    c.node("answer",394,1399,"生成 / 摘录式回答","可用 LLM 或本地提取式回答",w=282,h=112,tone="teal")
    c.node("sources",724,1399,"编号引用与来源","答案 + sources + pipeline_trace",w=282,h=112,tone="teal")
    c.node("refuse",394,1576,"拒答 / 请求澄清","没有足够证据时明确说明",w=282,h=92,tone="amber")
    c.edge("compress","gate","down")
    c.edge("gate","answer",label="足够")
    c.edge("answer","sources")
    c.relate("gate","refuse",[(176,1511),(176,1622),(394,1622)],"不足",(282,1612),amber=True)
    c.note(1720,"知识库问答与对话检索",["知识库问答走 retrieve_knowledge，按配置重排、扩展邻块、应用阈值，然后由 Answer Gate 判断是否回答。","ChatAgent 工具直接走 search_similar_documents，返回候选证据供下一步模型决策。","关闭 Embedding 时采用 BM25；切换向量后端或向量模型后需重建索引。"],"amber",123)
    c.save()


def project_layout():
    c = Canvas("project-layout", "项目目录 · 从哪里开始找", "页面、后端、运行脚本和说明文档各有入口。", 765)
    c.rect(548, 207, 304, 62, NAVY, NAVY, 14)
    c.text(700, 247, "DevHarbor/", 27, "#ffffff", 700, "middle")
    c.graph.append('  root["DevHarbor/"]')
    cards = [
        ("frontend", 64, "frontend/", "页面和桌面窗口", BLUE, [
            ("app/", "各个页面"), ("components/", "复用组件"), ("lib/", "请求与工具"),
            ("electron/", "桌面宿主与桥接"), ("scripts/", "桌面构建"),
        ]),
        ("backend", 388, "backend/", "服务和智能体", TEAL, [
            ("app/api/", "请求入口"), ("app/services/", "业务处理"), ("app/db/", "数据表"),
            ("desktop.py", "本机后端"), ("desktop_database.py", "桌面数据库"),
        ]),
        ("scripts", 712, "scripts/", "运行脚本与文档工具", AMBER, [
            ("start_rag.ps1", "启动演示"), ("seed_demo_data.py", "示例数据"),
            ("check_github_access.py", "GitHub 检查"), ("init_pgvector.sql", "向量扩展"),
            ("documentation-tools/", "文档维护"),
        ]),
        ("docs", 1036, "docs/", "说明文档与图表", BLUE, [
            ("guides/", "安装与使用"), ("api/", "接口导航"), ("architecture/", "系统设计"),
            ("examples/", "示例资料"), ("diagrams/", "图集与图源"),
        ]),
    ]
    c.parts.append('<path d="M700 269 V304 M214 304 H1186 M214 304 V336 M538 304 V336 M862 304 V336 M1186 304 V336" fill="none" stroke="#aac0ce" stroke-width="2"/>')
    for key, x, title, subtitle, accent, rows in cards:
        c.rect(x, 336, 300, 285, "#ffffff", "#d2e0ea", 16)
        c.rect(x + 22, 360, 4, 50, accent, accent, 2)
        c.text(x + 40, 381, title, 25, INK, 700)
        c.text(x + 40, 406, subtitle, 17, accent, 650)
        c.parts.append(f'<path d="M{x + 23} 426 H{x + 277}" stroke="#e4ecf2"/>')
        c.graph.append(f'  root --- {key}["{title} · {subtitle}"]')
        for index, (filename, description) in enumerate(rows):
            y = 455 + index * 34
            c.text(x + 24, y, filename, 17, INK, 600)
            c.text(x + 276, y, description, 15, MUTED, anchor="end")
            c.graph.append(f'  {key} --- {key}_{index}["{filename} · {description}"]')

    c.rect(64, 652, 1272, 68, "#edf4f8", "#d2e0ea", 12)
    c.text(89, 693, "本地生成", 17, INK, 700)
    c.text(252, 693, "node_modules / .venv：依赖", 17, MUTED)
    c.text(548, 693, "dist / release：构建产物", 17, MUTED)
    c.text(815, 693, ".data：Web 演示数据  ·  Electron userData：桌面数据", 17, MUTED)
    c.graph.append('  root -.-> local["本地文件：依赖、构建产物、Web 演示数据与桌面数据"]')
    c.save(flow_legend=False)


def hero():
    cover = '''<svg xmlns="http://www.w3.org/2000/svg" width="1400" height="420" viewBox="0 0 1400 420" role="img" aria-labelledby="title desc">
  <title id="title">DevHarbor | 软件研发 AI 工作台</title>
  <desc id="desc">DevHarbor 将当前代码、CI 日志和项目文档组织为带来源的工程分析证据。</desc>

  <defs>
    <linearGradient id="background" x1="0" y1="0" x2="100%" y2="100%">
      <stop stop-color="#0d1d31"/>
      <stop offset="1" stop-color="#112c40"/>
    </linearGradient>
    <radialGradient id="glow" cx="82%" cy="44%" r="54%">
      <stop stop-color="#247780" stop-opacity=".36"/>
      <stop offset="1" stop-color="#247780" stop-opacity="0"/>
    </radialGradient>
    <pattern id="grid" width="28" height="28" patternUnits="userSpaceOnUse">
      <path d="M 28 0 H 0 V 28" fill="none" stroke="#9fd0de" stroke-opacity=".09"/>
    </pattern>
    <linearGradient id="grid-fade">
      <stop stop-color="white" stop-opacity="0"/>
      <stop offset=".35" stop-color="white"/>
      <stop offset="1" stop-color="white" stop-opacity=".32"/>
    </linearGradient>
    <mask id="grid-mask">
      <rect x="640" width="760" height="420" fill="url(#grid-fade)"/>
    </mask>
    <linearGradient id="evidence" x1="0" y1="0" x2="100%" y2="100%">
      <stop stop-color="#e8fbf7"/>
      <stop offset="1" stop-color="#b5ece3"/>
    </linearGradient>
  </defs>

  <rect width="1400" height="420" fill="url(#background)"/>
  <rect width="1400" height="420" fill="url(#glow)"/>
  <rect x="640" width="760" height="420" fill="url(#grid)" mask="url(#grid-mask)"/>

  <g font-family="'Segoe UI','Microsoft YaHei','PingFang SC','Noto Sans CJK SC',sans-serif">
    <path d="M 76 106 H 124" fill="none" stroke="#65d7cb" stroke-width="5" stroke-linecap="round"/>
    <text x="71" y="197" fill="#f4f9fc" font-size="88" font-weight="700" letter-spacing="-3">DevHarbor</text>
    <text x="76" y="260" fill="#d9f4f1" font-size="40" font-weight="600">软件研发 AI 工作台</text>
    <text x="77" y="312" fill="#b6ccd9" font-size="24">基于代码、CI 日志与项目知识分析工程问题</text>

    <g fill="none" stroke="#64cfc5" stroke-width="2">
      <path d="M 954 126 H 987 Q 999 126 999 138 V 198 Q 999 210 1011 210 H 1070"/>
      <path d="M 954 210 H 1011"/>
      <path d="M 954 294 H 987 Q 999 294 999 282 V 222 Q 999 210 1011 210"/>
      <path d="M 1062 202 L 1070 210 L 1062 218" stroke-linecap="round" stroke-linejoin="round"/>
    </g>

    <g fill="#17374a" stroke="#466b7a" stroke-width="1.5">
      <rect x="752" y="96" width="202" height="60" rx="12"/>
      <rect x="752" y="180" width="202" height="60" rx="12"/>
      <rect x="752" y="264" width="202" height="60" rx="12"/>
    </g>
    <g fill="none" stroke="#7fe4d8" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
      <path d="M 781 119 L 774 126 L 781 133 M 791 119 L 798 126 L 791 133 M 788 115 L 784 137"/>
      <path d="M 774 217 H 798 M 775 207 H 780 L 784 201 L 789 212 L 793 207 H 797"/>
      <path d="M 778 282 H 789 L 795 288 V 305 H 778 Z M 789 282 V 288 H 795 M 782 294 H 790 M 782 299 H 790"/>
    </g>
    <g fill="#e1f1f5" font-size="25" font-weight="600">
      <text x="814" y="135">当前代码</text>
      <text x="814" y="219">CI 日志</text>
      <text x="814" y="303">项目文档</text>
    </g>

    <rect x="1086" y="120" width="238" height="180" rx="18" fill="url(#evidence)"/>
    <text x="1112" y="171" fill="#173d45" font-size="30" font-weight="700">分析与引用</text>
    <path d="M 1112 190 H 1298" fill="none" stroke="#4d8c8d" stroke-opacity=".43"/>
    <g fill="none" stroke="#326d72" stroke-width="2" stroke-linecap="round">
      <path d="M 1116 218 L 1121 223 L 1129 214 M 1142 219 H 1287"/>
      <path d="M 1116 241 L 1121 246 L 1129 237 M 1142 242 H 1270"/>
      <path d="M 1116 264 L 1121 269 L 1129 260 M 1142 265 H 1280"/>
    </g>
  </g>
</svg>
'''
    ASSETS.parent.mkdir(parents=True, exist_ok=True)
    (ASSETS.parent / "hero.svg").write_text(cover, encoding="utf-8")


if __name__ == "__main__":
    hero()
    architecture()
    workflow()
    rag()
    project_layout()
    print("Rendered 5 SVG assets and 4 Mermaid source diagrams.")
