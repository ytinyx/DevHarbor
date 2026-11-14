const { app, BrowserWindow, dialog, ipcMain, protocol, shell } = require('electron');
const { randomBytes } = require('node:crypto');
const fs = require('node:fs');
const fsp = require('node:fs/promises');
const path = require('node:path');
const { DESKTOP_DEV_RESTART, isTrustedPage, resolveAsset, startBackend } = require('./runtime.cjs');

app.setName('DevHarbor');
// Development/test profiles stay separate from the installed application.
if (!app.isPackaged && process.env.DEVHARBOR_USER_DATA_DIR) {
  const profile = path.resolve(process.env.DEVHARBOR_USER_DATA_DIR);
  fs.mkdirSync(profile, { recursive: true });
  app.setPath('userData', profile);
}
protocol.registerSchemesAsPrivileged([{ scheme: 'app', privileges: { standard: true, secure: true, supportFetchAPI: true, corsEnabled: true, stream: true } }]);

let window;
let backend;
let quitting = false;
let restarting = false;
let shutdownComplete = false;
let runtime;
const developmentUrl = !app.isPackaged ? process.env.DEVHARBOR_RENDERER_URL : undefined;
const token = randomBytes(32).toString('hex');
const dataDirectory = path.join(app.getPath('userData'), 'backend');
const logDirectory = path.join(app.getPath('userData'), 'logs');
fs.mkdirSync(logDirectory, { recursive: true });
const logFile = path.join(logDirectory, 'backend.log');

function openExternal(url) {
  try {
    const target = new URL(url);
    if (['https:', 'http:'].includes(target.protocol) && !target.username && !target.password) void shell.openExternal(target.href);
  } catch { /* Ignore invalid or privileged URLs. */ }
}

function backendCommand() {
  if (app.isPackaged) return { command: path.join(process.resourcesPath, 'backend', process.platform === 'win32' ? 'devharbor-core.exe' : 'devharbor-core'), args: [], cwd: dataDirectory };
  const backendDirectory = path.resolve(__dirname, '../../backend');
  const localPython = path.join(backendDirectory, '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
  return { command: process.env.DEVHARBOR_PYTHON || (fs.existsSync(localPython) ? localPython : process.platform === 'win32' ? 'python' : 'python3'), args: [path.join(backendDirectory, 'desktop.py')], cwd: backendDirectory };
}

function requireTrustedFrame(event) {
  if (!window || event.sender !== window.webContents || event.senderFrame !== window.webContents.mainFrame || !isTrustedPage(event.senderFrame?.url, developmentUrl)) {
    throw new Error('不允许修改或读取桌面配置。');
  }
}

async function run() {
  if (developmentUrl) {
    const dev = new URL(developmentUrl);
    if (dev.protocol !== 'http:' || !['127.0.0.1', 'localhost'].includes(dev.hostname) || dev.port !== '5174') throw new Error('开发页面地址必须是本机 5174 端口。');
  }
  fs.mkdirSync(dataDirectory, { recursive: true });
  const command = backendCommand();
  const launchBackend = (extraArgs = []) => startBackend({
    ...command,
    args: [...command.args, ...extraArgs],
    env: { ...process.env, DEVHARBOR_DESKTOP: '1', DEVHARBOR_DATA_DIR: dataDirectory, DEVHARBOR_DESKTOP_TOKEN: token, DEVHARBOR_DESKTOP_PORT: '0', PYTHONUNBUFFERED: '1', PYTHONUTF8: '1' },
    onLog: (line) => fs.appendFileSync(logFile, line),
    onUnexpectedExit: () => { if (!quitting) { dialog.showErrorBox('后台服务已停止', `请重新打开 DevHarbor。日志位置：\n${logFile}`); app.quit(); } },
  });
  let usingLocalFallback = false;
  try {
    backend = await launchBackend();
  } catch (error) {
    if (error.code !== 'DATABASE_UNAVAILABLE' || quitting) throw error;
    backend = await launchBackend(['--local-database']);
    usingLocalFallback = true;
  }
  runtime = { apiBaseUrl: `http://127.0.0.1:${backend.port}`, token, dataDirectory };
  console.info('DevHarbor: local backend ready');
  const health = await fetch(`${runtime.apiBaseUrl}/health`, { headers: { 'X-DevHarbor-Token': token }, signal: AbortSignal.timeout(5000) });
  if (!health.ok) throw new Error('后台服务未通过启动检查。');
  console.info('DevHarbor: backend health checked');
  if (quitting) { await backend.stop(); return; }

  const root = path.resolve(__dirname, '../dist');
  const mime = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8', '.svg': 'image/svg+xml', '.png': 'image/png', '.jpg': 'image/jpeg', '.ico': 'image/x-icon', '.woff2': 'font/woff2', '.json': 'application/json' };
  protocol.handle('app', async (request) => {
    if (!['GET', 'HEAD'].includes(request.method)) return new Response(null, { status: 405 });
    const asset = await resolveAsset(root, request.url);
    if (!asset) return new Response('Not found', { status: 404 });
    try {
      return new Response(request.method === 'HEAD' ? null : await fsp.readFile(asset), { headers: {
        'Content-Type': mime[path.extname(asset)] || 'application/octet-stream',
        'Content-Security-Policy': `default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; font-src 'self' data:; connect-src 'self' ${runtime.apiBaseUrl}; object-src 'none'; base-uri 'self'; frame-src 'none'`,
        'X-Content-Type-Options': 'nosniff',
      } });
    } catch { return new Response('Not found', { status: 404 }); }
  });

  window = new BrowserWindow({ width: 1440, height: 940, minWidth: 760, minHeight: 600, backgroundColor: '#191919', title: 'DevHarbor', autoHideMenuBar: true, show: false,
    webPreferences: { preload: path.join(__dirname, 'preload.cjs'), contextIsolation: true, nodeIntegration: false, sandbox: true, webSecurity: true },
  });
  window.webContents.session.setPermissionRequestHandler((_contents, _permission, callback) => callback(false));
  window.webContents.session.setPermissionCheckHandler(() => false);
  window.webContents.setWindowOpenHandler(({ url }) => { openExternal(url); return { action: 'deny' }; });
  window.webContents.on('will-navigate', (event, url) => {
    if (!isTrustedPage(url, developmentUrl)) { event.preventDefault(); openExternal(url); }
  });
  window.webContents.on('will-attach-webview', (event) => event.preventDefault());
  ipcMain.handle('devharbor:runtime', (event) => {
    requireTrustedFrame(event);
    return runtime;
  });
  ipcMain.handle('devharbor:restart', (event) => {
    requireTrustedFrame(event);
    if (quitting || restarting) return;
    if (!developmentUrl) app.relaunch();
    restarting = true;
    setImmediate(() => app.quit());
  });
  window.once('ready-to-show', () => window.show());
  window.on('closed', () => { window = null; });
  await window.loadURL(developmentUrl || 'app://localhost/');
  console.info('DevHarbor: interface loaded');
  if (window && !window.isDestroyed()) {
    window.show();
    if (usingLocalFallback) {
      void dialog.showMessageBox(window, {
        type: 'warning',
        message: 'PostgreSQL 启动失败，已使用本地 SQLite 打开',
        detail: '你可以在「设置 → 数据库连接」检查连接，再重启应用。',
      });
    }
  }
}

if (!app.requestSingleInstanceLock()) app.quit();
else {
  app.on('second-instance', () => { if (window) { if (window.isMinimized()) window.restore(); window.focus(); } });
  app.on('window-all-closed', () => app.quit());
  app.on('before-quit', (event) => {
    quitting = true;
    if (backend && !shutdownComplete) {
      event.preventDefault();
      void backend.stop().finally(() => {
        shutdownComplete = true;
        if (developmentUrl && restarting) app.exit(DESKTOP_DEV_RESTART);
        else app.quit();
      });
    }
  });
  app.whenReady().then(run).catch(async (error) => {
    if (!quitting) dialog.showErrorBox('DevHarbor 启动失败', `${error.message}\n\n日志位置：${logFile}`);
    if (backend) await backend.stop();
    shutdownComplete = true;
    app.quit();
  });
}
