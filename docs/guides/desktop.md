# 桌面运行与打包

[返回首页](../../README.md) · [浏览器运行指南](getting-started.md) · [配置说明](configuration.md)

DevHarbor 的 Electron 桌面版与浏览器版共用 React、Vite 和 React Router 页面。桌面窗口启动时会管理一个独立的 Python/FastAPI 后端，并在退出时关闭它；浏览器版继续连接自行启动的后端。

## 运行方式

以下命令从项目根目录执行。源码运行需要 Node.js 24、Python 3.11、`backend/.venv` 和已安装的前后端依赖：

```powershell
py -3.11 -m venv backend/.venv
.\backend\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
npm --prefix frontend ci
```

| 命令 | 用途 | 是否需要已有 Python 环境 |
| --- | --- | --- |
| `npm --prefix frontend run desktop:dev` | 自动启动 Vite、Electron 和 Python 后端；修改页面可热更新 | 需要 |
| `npm --prefix frontend run desktop` | 先构建静态页面，再用 Electron 加载本机 `app://localhost/` 页面 | 需要 |
| `npm --prefix frontend run dev` | 只启动浏览器开发页面 | 后端另行启动 |
| `npm --prefix frontend run preview` | 预览已经构建的浏览器静态页面 | 后端另行启动 |

桌面开发页面固定使用 `http://127.0.0.1:5174`。端口被占用时命令会报错，不会自动改端口或停止其他项目。浏览器开发可以用 `npm --prefix frontend run dev -- --port 5175` 选择其他端口；桌面开发入口与后端允许来源需要一起修改，不能只改 Vite 端口。

桌面后端由系统分配空闲的 `127.0.0.1` 端口，页面通过受限的桌面桥取得地址和本次启动令牌。浏览器开发默认仍调用 `http://127.0.0.1:8000`，可通过 `frontend/.env.local` 的 `VITE_API_BASE_URL` 修改。**在浏览器打开开发页面，不会自动取得桌面后端的数据或访问令牌。**

## 第一次使用

1. 在「我的项目」连接 GitHub 仓库或本地代码目录。
2. 点击左下角齿轮，在「API 配置」添加模型供应商并选定默认模型。
3. 在「智能体管理」查看预设角色、职责和接入状态，按需启停可选角色。
4. 回到「协作工作台」发起任务，查看分工计划并确认执行。

桌面版默认使用本地 SQLite 和 **BM25 关键词检索**。需要向量或混合检索时，可以连接已有的 PostgreSQL，启用 pgvector，并在「设置 → 检索模型」配置向量 API。

1. 打开「设置 → 数据库连接」，选择 PostgreSQL，填写数据库连接地址并测试。
2. 测试通过后保存并重启桌面应用。桌面版会从所选数据库读取项目和设置。切回 SQLite 就可以继续使用原本的本地数据。
3. 如需向量检索，确认目标数据库已启用 `vector` 扩展，再到「检索模型」选择「PostgreSQL（pgvector）」并配置向量模型。按页面提示重启后，到知识库重建向量索引。

安装包携带 PostgreSQL 客户端驱动。PostgreSQL 服务可运行在本机或远程机器上。连接凭据加密保存在桌面用户目录，数据库切换时需要单独迁移或导入原有资料。

## 数据与模型密钥

两端共享页面代码，**不自动同步项目、会话、上传文件、智能体配置或模型密钥**：

| 运行方式 | 默认数据位置 |
| --- | --- |
| 桌面版 | Electron `userData/backend` 下的独立 SQLite 与文件目录 |
| Windows 浏览器演示 | 项目根目录 `.data/devharbor-local-demo.db` 及演示文件目录 |
| 浏览器完整环境 | 根目录 `.env` 指定的数据库、上传和仓库路径 |

Windows 的桌面用户目录通常为 `%APPDATA%\DevHarbor`。主要内容包括：

- `backend/devharbor.db`：业务数据。
- `backend/repos`、`backend/uploads`：工作区和上传资料。
- `backend/secrets`：保护本地已保存凭据的加密密钥文件。
- `logs/backend.log`：桌面后台服务日志。

桌面启动不会读取项目根目录 `.env`，也不会导入浏览器已经保存的密钥。因此第一次使用桌面版需要重新填写模型供应商和所需仓库凭据。备份时先退出应用，保留整个 `backend` 目录；仅备份数据库而丢失对应加密密钥，可能无法解密已保存的凭据。

开发测试可指定独立数据目录，避免测试记录进入常用桌面配置：

```powershell
$env:DEVHARBOR_USER_DATA_DIR = Join-Path $PWD ".data\desktop-dev-profile"
npm --prefix frontend run desktop:dev
Remove-Item Env:DEVHARBOR_USER_DATA_DIR
```

该覆盖仅对源码运行生效，正式打包应用使用其正常用户目录。

## Windows 打包

先在构建机的虚拟环境安装固定的打包依赖：

```powershell
.\backend\.venv\Scripts\python.exe -m pip install -r backend/requirements-desktop.txt
```

随后按目标选择命令：

```powershell
# 只冻结 Python 后端
npm --prefix frontend run desktop:backend

# 构建静态页面、冻结后端，生成未安装的应用目录
npm --prefix frontend run desktop:pack

# 构建静态页面、冻结后端，生成 Windows NSIS 安装包
npm --prefix frontend run desktop:dist
```

`desktop:pack` 和 `desktop:dist` 都会先运行后端冻结步骤，不依赖发布目录之外的开发虚拟环境。冻结后端输出为 `backend/dist/devharbor-core/devharbor-core.exe`，Electron 构建产物写入 `frontend/release`。发布包携带后端和所需 Python 运行文件，目标用户无需另行配置 `backend/.venv`。

使用仓库克隆、更新等代码管理功能时，系统仍需安装 Git 并使其可从 PATH 访问；安装包目前不携带 Git。

当前打包配置**未配置代码签名**。上述命令描述构建流程，不代表已通过安装、升级或干净机器启动验证；分发前应单独验证对应产物。不要把模型密钥、开发 `.env` 或个人数据库加入安装包。

打包诊断：PyInstaller 中间文件位于 `.data/pyinstaller`；缺失模块提示位于 `.data/pyinstaller/devharbor-core/warn-devharbor-core.txt`。构建日志输出到执行命令的终端。运行时出现后台错误，应查看桌面用户目录下的 `logs/backend.log`。

## 浏览器静态部署

```powershell
npm --prefix frontend run build
npm --prefix frontend run preview
```

浏览器静态产物位于 `frontend/dist`，预览默认使用 `http://127.0.0.1:4173`。它与 Electron 使用同一份页面，但仍通过浏览器配置的 API 地址读取数据。

生产静态服务器需为应用路由提供 SPA fallback：直接访问或刷新 `/settings/agents`、`/knowledge/<id>` 等地址时返回 `index.html`，实际缺失的 `/assets/...` 文件保持 404。Electron 自定义 `app://localhost` 协议已经按这一原则处理桌面页面路径。

## 自动检查的范围

```powershell
npm --prefix frontend run lint
npm --prefix frontend run test:desktop
npm --prefix frontend run build
```

`test:desktop` 检查本机页面信任范围、静态资源路径和后台进程生命周期，不启动图形窗口。CI 使用 `ELECTRON_SKIP_BINARY_DOWNLOAD=1` 安装 npm 依赖以跳过 Electron 二进制下载；这条 CI 路径不能用于证明桌面窗口或安装包已经验收通过。

### 本机验收记录（2026-11-11）

Windows x64 上已生成 NSIS 安装包，并运行 `frontend/release/win-unpacked/DevHarbor.exe` 验证随包后端启动、中文界面、模型设置和智能体列表；关闭窗口后后台正常退出并释放端口。源码桌面版的深层页面刷新、浏览器知识库动态路由与标签刷新、新任务草稿重置也已验证。

前端生产构建通过；桌面运行时 4 项、既有前端回归 13 项、冻结后端及资料路径 18 项测试通过。默认模型切换通过本机模拟模型服务验证，未调用真实付费模型。lint 无错误，有 4 条既有工作台告警。本轮未执行安装、升级或干净机器验收。
