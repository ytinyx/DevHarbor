# 测试与评测

[返回首页](../../README.md) · [运行指南](getting-started.md) · [RAG 架构](../architecture/rag_pipeline.md)

DevHarbor 把代码回归、固定样例检查和真实模型评测分开记录。一次测试通过，只能说明该测试环境与覆盖范围内的行为符合断言；仓库没有附带生产准确率、P95 延迟或已通过的真实模型评分报告。

## 三层验证

| 层级 | 入口 | 可以说明什么 | 不能说明什么 |
| --- | --- | --- | --- |
| 代码回归 | `pytest`、前端 lint/build | 模块行为、接口契约与构建回归 | 真实模型质量、生产负载、完整服务集成 |
| 基础 Eval | `POST /api/evals/run` | 固定样例中的分类、关键文件覆盖、schema、Skill 与上下文检查 | 通用任务准确率；其中 `tool_call_accuracy` 是 schema-ready 占位指标，不是工具选择实测准确率 |
| ChatAgent + RAGAS | `POST /api/evals/rag/run` 或 `/evals` 页面 | 实际回答、工具轨迹、证据、硬规则和语义指标 | 超出当前题集、模型、检索配置及数据范围的质量 |

基础 Eval 不传 `repo_id` 时主要运行内置样例和 `NoopLLM`；传入仓库后还会运行该仓库的 ChatAgent 检索评测（关闭 Judge），此部分仍可能使用已经配置的模型。

## 运行代码检查

Windows PowerShell，在 `backend` 目录执行：

```powershell
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m pytest app/tests -q -o asyncio_default_fixture_loop_scope=function
```

macOS / Linux 使用 `.venv/bin/python`。测试使用隔离 SQLite、确定性 Embedding 与模拟外部服务，不需要 Docker 或真实 API Key。CI 还显式清空外部服务凭据；具体环境见 [CI 工作流](../../.github/workflows/ci.yml)。`pip check` 只检查依赖兼容性，不是漏洞扫描。

在 `frontend` 目录执行：

```bash
npm ci
npm run lint
npm run build
npm audit --omit=dev --audit-level=high --registry=https://registry.npmjs.org
```

CI 在 push、pull request 和手动触发时执行后端测试及上述前端检查。它不部署应用，不执行项目的 GitHub 写入，也不使用项目 API 密钥。后端依赖的已知历史审计记录见[安全说明](../architecture/security.md)。

## 准备固定 RAGAS 题集

仓库提供 [5 条公开示例用例](../datas/evals/rag_cases.json)，覆盖本地演示范围、可复用知识、当前代码权威来源、Judge 异常和证据不足。题集 ID 为 `devharbor-real-project-rag-baseline`，保留该名称用于兼容已有记录，名称本身不表示生产实测或已通过。

1. 按[运行指南](getting-started.md)启动应用并连接目标仓库；本地演示也可选择虚构样例仓库。
2. 把 [`docs/datas/sources`](../datas/sources) 中的全部 3 个 Markdown 文件上传到**同一目标仓库**的知识库，保持原文件名。不要上传题集 JSON，以免把参考答案混入检索证据。
3. 等待文件处理完成；通过 `GET /api/evals/suites?repo_id=<repository-uuid>` 检查 `ready` 和 `missing_sources`。来源按当前仓库内的文件名匹配，另一仓库的同名文件不算就绪。
4. 配置可用的 ChatAgent 模型、Embedding 和 RAGAS Judge。完整向量链路还需要 Milvus；演示模式的结果应保留检索降级说明。

如果未选固定题集，系统会从当前文档临时出题（`auto-document-smoke`）。这可以验证链路，不能替代固定回归基线。

## Judge 与质量门槛

Judge 默认回退到 `LLM_API_KEY`、`LLM_BASE_URL`、`LLM_MODEL`，也可用 `RAGAS_JUDGE_API_KEY`、`RAGAS_JUDGE_BASE_URL`、`RAGAS_JUDGE_MODEL` 独立配置。`RAGAS_TIMEOUT_SECONDS` 默认 120，`RAGAS_JUDGE_MAX_TOKENS` 默认 8192；超时和缺失指标应记录为不完整，不能填成零分或通过。

| 必需语义指标 | 检查方向 | 当前配置门槛 |
| --- | --- | --- |
| Context Precision | 检索证据与问题的相关性 | `RAGAS_CONTEXT_PRECISION_MIN=0.75` |
| Context Recall | 参考答案所需信息的覆盖 | `RAGAS_CONTEXT_RECALL_MIN=0.80` |
| Faithfulness | 回答是否被检索证据支持 | `RAGAS_FAITHFULNESS_MIN=0.90` |
| Answer Relevancy | 回答是否切题 | `RAGAS_ANSWER_RELEVANCY_MIN=0.80` |
| Agent Goal Accuracy | 工具轨迹与回答是否完成目标 | `RAGAS_AGENT_GOAL_ACCURACY_MIN=0.80` |

用例定义了 `expected_tool_calls` 时，还会计算 Tool Call Accuracy / F1，对应默认门槛均为 0.90。这些数字是判定阈值，不是项目已达到的成绩。硬规则检查还覆盖来源命中、必需工具、工具错误、必含/禁含文本与回答正则等。

`RAGAS_ENABLED` 是内部调用未指定 `run_judge` 时的默认值。HTTP 请求的 `run_judge` 默认 `true`，页面也显式传入 `true`，会覆盖该默认值。要跳过 Judge，请在 API 请求中明确设置 `run_judge=false`；这只关闭评分模型，ChatAgent 仍可能调用已配置的模型服务。

## 提交、轮询与读取结果

在 `/evals` 页面选择仓库、固定题集和 Top-K 后运行，或发送：

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

接口返回 `queued` 和 `eval_id`。使用 `GET /api/evals/{eval_id}` 轮询 `result.progress`；评测在当前后端进程的后台任务中执行，刷新或离开前端页面不会取消它，但它不是具有断点恢复能力的持久化任务队列，后端重启可能中断运行。

| `status` | 含义 |
| --- | --- |
| `queued` / `running` | 等待或执行中，尚无最终结论 |
| `passed` | 硬规则通过、必需语义指标完整且达到门槛 |
| `failed` | 已发现硬规则或语义门槛不通过 |
| `partial` | 跳过 Judge 且硬规则通过；只有部分验证 |
| `error` | 任务异常或所需评分不完整；结合 `quality_status` 与逐题诊断判断 |
| `no_cases` | 无可评测用例 |

同时读取 `execution_status`、`quality_status`、`evaluation_complete` 和 `passed`。`error` 时仍可能已经发现硬规则失败，因此不能只看一个状态字段，也不能把“执行结束”理解为“质量通过”。

每次结果保存题集 Hash、Top-K、Judge/Ragas 信息、问题与回答、参考答案、来源证据、工具轨迹、硬规则、逐题诊断及测得耗时。耗时属于该次运行记录，不直接等于稳定性能基准。

## 从失败定位到回归

1. 展开失败 Case，查看实际回答、引用证据和工具轨迹，先区分召回问题、回答问题、工具问题与 Judge 问题。
2. Judge 超时或指标缺失时，调用 `POST /api/evals/{eval_id}/rescore`。系统新建一次评测记录，只重算缺失/异常评分，复用原回答与证据，不重新运行 ChatAgent。
3. 修复检索配置、文档或 Agent 后，重新执行完整评测。`GET /api/evals/compare?base_eval_id=...&candidate_eval_id=...` 会检查题集 Hash、Ragas 版本、Judge 模型和 Top-K 是否可比；代码与数据版本仍需由实验记录补充。
4. 需要跟进时，用 `POST /api/evals/{eval_id}/issue-draft` 创建 `create_issue` 草稿，将失败现场交给人工复核；只有确认草稿才会写入 GitHub。

对外展示结果时，应附 commit、题集 Hash、样本数、数据准备方式、模型/向量配置、完整或降级状态、运行时间与原始记录。简历优先描述已经实现的评测机制，获得可复现的实测报告后再填写效果数字。

## 实现入口

- [评测 API 与任务状态](../../backend/app/api/routes/evaluations.py)
- [RAGAS 指标、硬规则和重评分](../../backend/app/services/evals/ragas_runner.py)
- [固定题集加载与来源检查](../../backend/app/services/evals/suites.py)
- [基础 Eval 的样例与指标定义](../../backend/app/services/evals/runner.py)
