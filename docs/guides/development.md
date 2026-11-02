# 开发与文档维护

[文档导航](../README.md) · [安装与启动](getting-started.md)

## 回归检查

使用 Python 3.11 和 Node.js 24，与 [GitHub Actions](../../.github/workflows/ci.yml) 保持一致。下面从仓库根目录运行；macOS / Linux 把解释器路径替换为 `backend/.venv/bin/python`。

```powershell
Push-Location backend
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m pytest app/tests -q -o asyncio_default_fixture_loop_scope=function
Pop-Location
npm --prefix frontend ci
npm --prefix frontend run lint
npm --prefix frontend run build
npm --prefix frontend audit --omit=dev --audit-level=high --registry=https://registry.npmjs.org
```

测试的隔离策略见 [conftest.py](../../backend/app/tests/conftest.py)：使用 SQLite、deterministic Embedding，模拟外部服务。运行前应使用独立开发环境；不要给回归测试传入真实服务密钥。CI 的完整环境变量清单位于工作流文件。

`next.config.js` 将开发产物放在 `.next-dev`、生产构建放在 `.next`。`npm run lint` 当前还使用 Next.js 的 lint 命令；升级框架时需要一并检查 lint 入口与既有 Hook 依赖告警。

## 文档与图示

```powershell
python scripts/render_docs.py
python scripts/validate_docs.py
git diff --check
```

图示的源文件约定与预览方法见[图示说明](../diagrams/README.md)。文档校验脚本只使用 Python 标准库，检查本地链接、图片资源、Markdown 锚点与 SVG 安全结构；它不代替人工查看布局或核对代码事实，也不检查外部网站是否在线。

修改图示时同时确认：

1. 模块名、分支与连线在代码里有对应实现；数据流和控制流含义清楚。
2. 在 GitHub 正文宽度及单图放大时都能阅读，文字不出框、箭头不穿字。
3. 截图使用本地样例数据并说明模式，避免包含凭据、个人信息或私有仓库内容。
4. 若实现改变，同步更新架构说明、Mermaid 与 SVG；重新运行生成和校验命令。

## 解释验证结果

| 检查 | 能说明什么 | 不能据此推断什么 |
| --- | --- | --- |
| pytest | 现有自动化用例在该环境通过 | 真实模型质量、线上稳定性 |
| lint / build | 静态检查与生产构建结果 | 所有用户交互已覆盖 |
| 文档校验 | 本地资源引用与结构有效 | 图示语义、外链与实际服务可用 |
| 固定 RAGAS 评估 | 特定题集、数据与配置下的质量结果 | 未测场景的普遍准确率 |
| PostgreSQL / Milvus 集成验证 | 实际服务配置下的入库、召回和重建行为 | 高并发或容灾能力 |

发布前审阅本次差异，排除 `.env`、运行数据库、上传资料和临时文件。通过正常 PR 与分支保护检查合并，不将本地演示模式标为生产部署。
