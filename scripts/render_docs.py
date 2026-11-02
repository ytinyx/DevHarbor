"""Render repository documentation SVGs and Mermaid sources (standard library only).

Run from any directory: python scripts/render_docs.py
The Python definitions below are the canonical editable source for the SVG assets.
No network requests, external fonts, or image-generation service is required.
"""
from __future__ import annotations

from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "docs" / "assets"
DIAGRAMS = ROOT / "docs" / "diagrams"
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

    def save(self):
        for y, number, title, note in self.sections:
            self.section(y, number, title, note, overlay=True)
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
        (DIAGRAMS / f"{self.name}.mmd").write_text("%% Generated by scripts/render_docs.py; semantic flow, SVG has curated layout.\n" + "\n".join(self.graph) + "\n", encoding="utf-8")


def architecture():
    c = Canvas("architecture", "系统地图 · 从上下文到工程行动", "细分调用入口、Agent 工具与证据存储；每个数据域都保留明确的来源。", 1390)
    c.section(216, "01", "请求入口与对话主链", "Next.js → FastAPI → context → model/tools")
    for key, x, title, sub in [
        ("ui",64,"Next.js 工作台","对话 · 知识库 · PR / CI"),
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
    c.section(819,"04","证据与持久化","PostgreSQL 框代表同一关系库中的不同逻辑数据组")
    stores = [
        ("checkout",64,"当前 checkout","本地仓库 · 隔离工作树\n路径校验后的只读检索"),
        ("memdb",326,"对话 / 长期记忆","PostgreSQL\n会话、消息、批准的笔记"),
        ("documents",588,"文档 / 向量","PostgreSQL Document\nMilvus · repo_id 隔离"),
        ("snapshot",850,"GitHub 同步快照","Issue / PR / CI · SQL\nGitHub REST API"),
        ("runs",1112,"运行 / 任务记录","PostgreSQL\nAgentWorkflowRun / TaskRun"),
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
    c.note(1186,"当前使用边界",["当前版本面向本地 / 可信内网单用户演示，未实现用户登录认证；DEMO_MODE 不会阻止已确认草稿的 GitHub 写入。","工作区代码走当前 checkout 工具；RAG 承载可复用的非结构化证据。图示为代码架构说明，不是产品界面截图。"],"amber",96)
    c.save()


def workflow():
    c = Canvas("agent-workflow","工程工作流 · 规划、执行、观察与综合","依赖图按就绪批次执行；报告生成后记录任务结果，最终随请求事务提交。",1436)
    c.section(216,"01","建立任务图","Planner / Observer / Synthesis 使用规则与结构化逻辑")
    xs=[64,394,724,1054]
    row=[("entry","ChatAgent 工具入口","workflow.run_engineering_review"),("planner","规则规划 Planner","目标 · 范围 · 验收标准"),("spec","WorkflowSpec","小任务 · dependencies\nmax_parallel_tasks / timeout"),("ready","依赖就绪筛选","成功依赖已完成 → ready")]
    for (key,title,sub),x in zip(row,xs): c.node(key,x,250,title,sub,w=282,h=112,tone="blue")
    for a,b in [("entry","planner"),("planner","spec"),("spec","ready")]: c.edge(a,b)
    c.section(421,"02","有界并行与结果归并","不是所有任务同时启动：只调度当前 ready 的批次")
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
    c.note(1185,"工程边界",["该工作流是进程内的有界任务调度，并不提供分布式队列或跨进程故障恢复；Planner / Observer / Synthesis 不是独立 LLM 调用。","Safety 分析可以给出待确认事项；真实写入仍通过 ActionDraft → 用户确认 → 权限校验 → GitHub 执行，详见系统地图。"],"blue",100)
    c.save()


def rag():
    c = Canvas("rag-pipeline","RAG 流水线 · 入库、混合召回与证据门控","本图的完整问答链对应知识库问答与检索实验；ChatAgent 检索工具有单独的轻量路径。",1960)
    c.section(216,"01","文档入库","进程内 BackgroundTasks；无持久队列或自动恢复")
    row=[("upload",64,"文件上传","TXT / MD / PDF / DOCX 等"),("hash",326,"SHA-256 去重","同仓库识别重复文件"),("queued",588,"后台入库登记","KnowledgeSourceDocument\nBackgroundTasks · 进程内\nqueued → parsing"),("parse",850,"格式提取","提取文本与文档结构"),("split",1112,"结构感知切片","父子块 · 标题 · 来源元数据")]
    for key,x,title,sub in row: c.node(key,x,250,title,sub,h=112,tone="blue")
    for a,b in [("upload","hash"),("hash","queued"),("queued","parse"),("parse","split")]: c.edge(a,b)
    row2=[("state",64,"处理结果状态","completed / failed\n完成不代表向量就绪"),("milvus",326,"Milvus 向量写入","仅 MILVUS_ENABLED=true\nrepo_id · source_id"),("sql",588,"Document 关系表","正文 · 切片 · 来源元数据"),("embed",850,"批量 Embedding","固定 provider / model / dims\n分批向量化"),("normalize",1112,"片段准备","父文档关联 · 内容规范化")]
    for key,x,title,sub in row2: c.node(key,x,430,title,sub,h=112,tone="teal")
    c.edge("split","normalize","down")
    for a,b in [("normalize","embed"),("embed","sql"),("sql","milvus"),("milvus","state")]: c.edge(a,b,"left")
    c.relate("sql","state",[(700,542),(700,562),(176,562),(176,542)],"未启用 Milvus：跳过写入",(438,563),dashed=True)
    c.note(577,"另一条入库入口：GitHub 同步",["Issue 正文、PR 说明 / Review 评论、失败 CI 日志 → 来源白名单（CI 日志脱敏）→ Document / Milvus。","当前源代码由 workspace.search_code / read_file 检索；实时状态回到数据库或 GitHub API 核查。"],"blue",98)
    c.section(735,"02","双路召回与候选整理","图示 hybrid；fulltext 只走关键词，vector 只走向量")
    c.node("scope",64,780,"问题与检索范围","repo_id · source_types\nmetadata filters",h=112,tone="blue")
    c.node("query",326,780,"Query Embedding","使用知识库向量配置",h=112)
    c.node("vector",588,780,"Milvus 召回","向量相似度候选",h=112)
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
    c.note(1720,"两条调用路径，避免混为一谈",["知识库问答 / 检索实验：retrieve_knowledge → 配置化重排、阈值、邻块扩展与 Answer Gate → 答案或澄清。","ChatAgent 工具：search_similar_documents → 混合召回、去重、启发式重排与压缩 → 模型继续使用工具验证证据。","deterministic embedding 与关闭 Milvus 的本地演示可验证流程，不代表真实语义召回质量或完整混合检索已通过验证。"],"amber",123)
    c.save()


def hero():
    # The cover is explicitly an architecture illustration, never a fabricated screenshot.
    c=Canvas("hero","DevHarbor | 软件研发 AI 工作台","面向软件研发场景，以代码和文档证据支持问题分析、代码审查、CI 排障与知识问答；当前接入 GitHub 和本地代码工作区。",540)
    # Replace the technical header with a compact editorial cover.
    c.parts=[c.parts[0].split("<defs>", 1)[0]]
    c.parts.append(f'''<defs><linearGradient id="hero-bg" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#0c1e32"/><stop offset="1" stop-color="#163c53"/></linearGradient><pattern id="dots" width="24" height="24" patternUnits="userSpaceOnUse"><circle cx="1" cy="1" r="1" fill="#8bc2d3" opacity=".12"/></pattern></defs><rect width="1400" height="540" fill="url(#hero-bg)"/><rect width="1400" height="540" fill="url(#dots)"/><g font-family="{FONT}">''')
    c.text(64,70,"SOFTWARE DEVELOPMENT × AI WORKSPACE",14,"#75d5d5",650,spacing=2)
    c.text(62,166,"DevHarbor",76,"#ffffff",750,spacing=-2)
    c.text(66,222,"软件研发 AI 工作台",30,"#e1eff7",600)
    c.text(66,270,"从问题、代码、CI 与项目知识出发，",20,"#adc9da")
    c.text(66,302,"组织证据，输出可追溯的分析与待确认行动。",20,"#adc9da")
    for x,w,label in [(66,140,"原生工具调用"),(220,148,"多 Agent 编排"),(382,146,"混合检索 RAG")]:
        c.rect(x,347,w,38,"#173d53","#316176",19)
        c.text(x+w/2,372,label,15,"#d7ebf1",550,"middle")
    c.text(66,424,"当前接入 GitHub 与本地代码工作区",15,"#a0bed0")
    c.text(66,458,"FASTAPI  /  NEXT.JS  /  POSTGRESQL  /  MILVUS",13,"#7fa7bd",600,spacing=1.1)
    c.text(66,493,"本地与可信内网演示 · 代码可核查 · MIT License",14,"#a0bed0")
    # Port-like connections: evidence enters a small, legible processing network.
    nodes=[(710,84,"Issue","需求与讨论"),(928,84,"Pull Request","变更与审查"),(1146,84,"CI Logs","失败与上下文")]
    for x,y,title,sub in nodes:
        c.rect(x,y,190,82,"#15334a","#3b647c",12)
        c.text(x+18,y+32,title,20,"#e1f1f6",650)
        c.text(x+18,y+58,sub,14,"#9ebfd0")
        c.parts.append(f'<path d="M{x+95} {y+82} V208 H1023 V240" fill="none" stroke="#3f8c9e" stroke-width="2"/>')
    c.rect(895,240,256,104,"#dff7f2","#83dfd3",16)
    c.text(1023,280,"Agent Workspace",24,"#123c47",700,"middle")
    c.text(1023,313,"检索 → 分析 → 证据",17,"#2c6973",550,"middle")
    for x,label,sub in [(774,"Evidence","来源 / 引用"),(1054,"Action Draft","人工确认后执行")]:
        c.parts.append(f'<path d="M1023 344 V378 H{x+115} V414" fill="none" stroke="#49bfb9" stroke-width="2"/>')
        c.rect(x,414,230,77,"#16374b","#4c8994",12)
        c.text(x+18,444,label,20,"#d8f1f1",650)
        c.text(x+18,470,sub,14,"#99c0ce")
    c.text(1336,521,"架构主题插画 · 非运行界面",11,"#7195aa",anchor="end")
    c.parts.append("</g></svg>\n")
    ASSETS.mkdir(parents=True,exist_ok=True)
    (ASSETS/"hero.svg").write_text("\n".join(c.parts),encoding="utf-8")


if __name__ == "__main__":
    hero()
    architecture()
    workflow()
    rag()
    print("Rendered 4 SVG assets and 3 Mermaid source diagrams.")
