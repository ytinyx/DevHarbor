# 安全与使用边界

当前版本面向本机、单用户、可信环境下的开发和演示。它尚未实现登录认证或按请求用户进行授权：`require_permission` 会从数据库选择演示用户，并检查该用户的角色。角色检查和 CORS 都不能替代身份认证。请仅监听本机地址；在补齐身份认证、资源授权和隔离之前，不要将应用 API 直接开放到公网或不受信任的局域网。

## GitHub 写入行为

Agent 生成 `ActionDraft` 时不会直接写入 GitHub。调用 `POST /api/action-drafts/{draft_id}/confirm` 后，后端会使用仓库保存的 Token（未配置时回退到 `GITHUB_TOKEN`）执行草稿，支持创建 Issue、发布 Issue/PR 评论、关闭 Issue 和添加标签。确认界面只提供操作复核，不能弥补缺失的用户认证。

`send_report` 只记录为已发送，尚未接入外部报告发送渠道。`DEMO_MODE=true` 不是全局只读开关，也不会禁止草稿确认后的 GitHub 写入。演示和自动测试应使用虚构仓库及空 Token；连接真实仓库时只授予需要的最小权限。

## 凭据与数据

- API Key、GitHub Token 和 Webhook 地址通过环境变量或用户输入提供；`.env`、本地数据库、上传目录和日志不应提交到 Git。
- 持久化的仓库 Token 使用 Fernet 加密，密钥由 `TOKEN_ENCRYPTION_KEY` 派生。示例值 `change-me-in-local-dev` 公开且可预测；保存真实 Token 前应设置独立的随机值。更换密钥后，旧密文需要迁移或重新输入 Token。
- 配置模型服务后，对话、检索片段和相关仓库内容可能被发送到该服务；启用 RAGAS Judge 也会发送回答、参考答案与检索证据。只使用允许处理这些数据的服务。
- 配置 `FEISHU_FEEDBACK_WEBHOOK_URL` 后，负面反馈通知会发送到对应飞书机器人。日志、反馈和审计记录可能包含项目内容，分享前应检查并脱敏。
- GitHub Webhook 仅在设置 `GITHUB_WEBHOOK_SECRET` 时校验签名；未设置时不会验证请求来源。接入 Webhook 前必须配置签名密钥及相应访问控制。

## 自动检查范围

CI 使用 SQLite、确定性 Embedding 和模拟模型运行后端测试，并检查前端 lint、生产构建和依赖审计。它不连接真实 GitHub 仓库、不运行付费模型评分，也不能替代 PostgreSQL/Milvus 集成验证或生产安全评审。

## 依赖审计记录（2026-10-31）

前端已升级到 Next.js 15.5.28、React 19.0.9，并修复可兼容升级的传递依赖。`npm audit --omit=dev` 为零漏洞；完整审计仍有 14 条中危记录，属于 ESLint / TypeScript-ESLint / minimatch 开发工具链，没有高危或严重记录。CI 当前阻止生产依赖中的高危和严重漏洞，未将开发工具链的中危项视作已修复。

后端已升级有可用修复的依赖并通过完整测试和依赖兼容性检查。`pip-audit` 仍报告以下 2 个唯一公告（原始结果有 4 条重复记录）；截至检查时，两项公告均没有已公布的修复版本，未通过忽略规则隐藏：

| 依赖 | 已知公告 | 当前调用路径与限制 |
| --- | --- | --- |
| diskcache 5.6.3 | [CVE-2025-69872](https://github.com/advisories/GHSA-w8v5-vhqr-4h9v)：可写缓存目录中的 pickle 反序列化 | 当前 RAGAS Judge 不启用 `DiskCacheBackend`，`llm_factory` 的缓存保持默认关闭。不要加载不可信的磁盘缓存；若以后启用，缓存目录必须只允许服务账号写入。 |
| ragas 0.4.3 | [CVE-2026-6587](https://github.com/advisories/GHSA-95ww-475f-pr4f)：多模态 Faithfulness 的 URL/本地文件处理 | 当前仅实例化固定文本指标，没有调用多模态 Faithfulness。保持这一边界，不开放多模态 URL/文件输入；部署时限制评测进程外连，并跟进上游修复。 |

调用路径判断来自 `backend/app/services/evals/ragas_runner.py` 的当前实现，不代表依赖本身不存在漏洞。升级依赖或启用新指标、缓存功能时必须重新审计。可使用隔离的审计工具从项目根目录复核：`uvx pip-audit -r backend/requirements.txt`；存在上述公告时，非零退出码是预期结果。CI 的依赖安全检查目前覆盖前端生产依赖，后端 `pip check` 仅验证兼容性。
