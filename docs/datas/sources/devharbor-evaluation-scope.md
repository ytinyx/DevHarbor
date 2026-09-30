# DevHarbor 评测结果的解释边界

这是随 DevHarbor 发布的公开项目说明，用于示例回归评测。依据是根目录 `README.md`、`backend/app/services/evals/ragas_runner.py` 和评测 API 的设计。

固定评测会在隔离会话中运行 ChatAgent，收集检索上下文、来源与工具轨迹。RAGAS Judge 评估 Context Precision、Context Recall、Faithfulness、Answer Relevancy 和 Agent Goal Accuracy。评测结果保留评测集 Hash、阈值和逐题诊断，只有硬规则全部满足且完整的五项必需语义指标都达到设置的门槛，才能给出整体通过结论。

Judge 超时、调用失败或必需指标缺失应视为评测不完整，不能把执行错误当作质量通过或质量失败。可以使用“仅重试异常评分”复用已经保存的回答和证据，不重新运行 ChatAgent；仍失败时应检查 Judge 配置与超时。完整评分结果低于阈值才支持相应的质量失败判断。

随仓库提供的 `devharbor-real-project-rag-baseline` 是公开项目示例回归基线，该标识保留用于兼容既有调用。基线提供用例和公开来源文档，没有附带生产部署的问答准确率、P95 响应延迟或已通过的生产评测报告。仅凭这些资料无法确定上述生产指标，也不能编造具体数值；需要对应部署、数据集、模型配置和测量条件下的真实报告。
