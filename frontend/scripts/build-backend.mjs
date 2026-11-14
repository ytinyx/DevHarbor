import { existsSync, mkdirSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";

const projectRoot = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
const backendRoot = join(projectRoot, "backend");
const python = process.env.DEVHARBOR_BUILD_PYTHON || join(backendRoot, ".venv", process.platform === "win32" ? "Scripts/python.exe" : "bin/python");
const dataDir = join(projectRoot, ".data");
const buildDir = join(dataDir, "pyinstaller");
const cacheDir = join(dataDir, "pip-cache");

if (!existsSync(python)) {
  throw new Error(`未找到后端构建环境：${python}。请先创建 backend/.venv 并安装 requirements.txt 与 requirements-desktop.txt。`);
}
for (const path of [buildDir, cacheDir]) mkdirSync(path, { recursive: true });

const env = { ...process.env, PIP_CACHE_DIR: cacheDir, PYINSTALLER_CONFIG_DIR: join(dataDir, "pyinstaller-cache"), PYTHONIOENCODING: "utf-8" };
const check = spawnSync(python, ["-c", "import PyInstaller; assert PyInstaller.__version__ == '6.22.3', '请安装 backend/requirements-desktop.txt 中固定的 PyInstaller 版本'"], { cwd: backendRoot, env, encoding: "utf8", windowsHide: true });
if (check.status !== 0) {
  throw new Error(`请在 backend/.venv 中安装桌面构建依赖：python -m pip install -r backend/requirements-desktop.txt\n${check.stderr || check.error || ""}`);
}

console.log("正在打包 DevHarbor 本地服务…");
const result = spawnSync(python, ["-m", "PyInstaller", "--noconfirm", "--distpath", join(backendRoot, "dist"), "--workpath", buildDir, join(backendRoot, "devharbor-core.spec")], { cwd: backendRoot, env, stdio: "inherit", windowsHide: true });
if (result.error) throw result.error;
if (result.status !== 0) process.exit(result.status || 1);
const executable = join(backendRoot, "dist", "devharbor-core", process.platform === "win32" ? "devharbor-core.exe" : "devharbor-core");
if (!existsSync(executable)) throw new Error("打包进程结束，但未找到后端可执行文件。");
console.log(`本地服务已生成：${executable}`);
