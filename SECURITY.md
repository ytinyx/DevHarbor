# 安全问题报告

请通过 [ytiny163@163.com](mailto:ytiny163@163.com) 私密报告安全问题，并提供受影响版本、脱敏后的复现步骤及影响范围。

不要在公开 Issue、Pull Request 或评论中贴出 API 密钥、GitHub Token、Webhook 地址、个人数据或可直接利用的敏感细节。若凭据已经泄露，请先撤销并更换，再报告问题；不要通过邮件发送仍有效的密钥。

当前版本的适用环境、GitHub 写入行为、凭据处理和已知依赖风险见 [安全与使用边界](docs/architecture/security.md)。运行或部署前请阅读该文档。

依赖更新由 Dependabot 按周创建 Pull Request，minor 和 patch 版本按组件分组。major 更新和安全更新不被忽略；更新需要经过 CI 检查和人工审查后合并，不自动合并。
