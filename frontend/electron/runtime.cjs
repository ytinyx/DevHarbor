const { spawn } = require('node:child_process');
const path = require('node:path');
const fs = require('node:fs/promises');
const DESKTOP_DEV_RESTART = 75;

function isTrustedPage(url, developmentUrl) {
  try {
    const parsed = new URL(url);
    if (parsed.protocol === 'app:' && parsed.hostname === 'localhost' && !parsed.port && !parsed.username && !parsed.password) return true;
    return Boolean(developmentUrl && parsed.origin === new URL(developmentUrl).origin);
  } catch { return false; }
}

async function resolveAsset(root, rawUrl) {
  const url = new URL(rawUrl);
  if (url.protocol !== 'app:' || url.hostname !== 'localhost' || url.port || url.username || url.password) return null;
  let pathname;
  try { pathname = decodeURIComponent(url.pathname); } catch { return null; }
  if (pathname.includes('\\') || pathname.includes('\0')) return null;
  const asset = path.resolve(root, `.${pathname}`);
  const relative = path.relative(root, asset);
  if (relative.startsWith('..') || path.isAbsolute(relative)) return null;
  try { if ((await fs.stat(asset)).isFile()) return asset; } catch { /* Client routes have no corresponding file. */ }
  if (path.extname(pathname)) return null;
  return path.join(root, 'index.html');
}

function startBackend({ command, args = [], cwd, env, onLog = () => {}, onUnexpectedExit = () => {}, timeoutMs = 90000 }) {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, { cwd, env, windowsHide: true, stdio: ['pipe', 'pipe', 'pipe'] });
    let settled = false;
    let stopping = false;
    let buffer = '';
    let stopPromise;
    const timer = setTimeout(() => fail(new Error('后台服务启动超时，请查看应用日志。')), timeoutMs);
    const fail = (error) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      void stop().then(() => reject(error));
    };
    const stop = () => {
      if (stopPromise) return stopPromise;
      stopping = true;
      stopPromise = new Promise((done) => {
        if (child.exitCode !== null || child.signalCode || !child.pid) { done(); return; }
        const forceTimer = setTimeout(() => {
          if (process.platform === 'win32') {
            const killer = spawn('taskkill', ['/PID', String(child.pid), '/T', '/F'], { windowsHide: true, stdio: 'ignore' });
            killer.on('error', () => { child.kill(); });
          } else child.kill('SIGKILL');
        }, 5000);
        child.once('exit', () => { clearTimeout(forceTimer); done(); });
        try { child.stdin.end('{"type":"shutdown"}\n'); } catch { child.kill(); }
      });
      return stopPromise;
    };
    child.stdin.on('error', () => {});
    child.stderr.on('data', (chunk) => onLog(chunk.toString()));
    child.stdout.on('data', (chunk) => {
      buffer += chunk.toString();
      if (buffer.length > 1024 * 1024) { fail(new Error('后台服务未返回有效启动信息。')); return; }
      let newline;
      while ((newline = buffer.indexOf('\n')) !== -1) {
        const line = buffer.slice(0, newline).trim();
        buffer = buffer.slice(newline + 1);
        let message;
        try { message = JSON.parse(line); } catch { if (line) onLog(`${line}\n`); continue; }
        if (settled || !message || typeof message !== 'object') continue;
        if (message.type === 'database_unavailable') {
          fail(Object.assign(new Error('PostgreSQL 未能启动，请检查数据库连接和权限。'), { code: 'DATABASE_UNAVAILABLE' }));
          return;
        }
        if (message.type !== 'ready') continue;
        if (!Number.isInteger(message.port) || message.port < 1 || message.port > 65535) { fail(new Error('后台服务返回了无效端口。')); return; }
        settled = true;
        clearTimeout(timer);
        resolve({ port: message.port, pid: child.pid, stop });
      }
    });
    child.on('error', () => fail(new Error('无法启动 Python 后台，请检查安装是否完整。')));
    child.once('exit', (code) => {
      if (!settled) fail(new Error(`后台服务启动失败（退出码 ${code ?? '未知'}），请查看应用日志。`));
      else if (!stopping) onUnexpectedExit(code);
    });
  });
}

module.exports = { DESKTOP_DEV_RESTART, isTrustedPage, resolveAsset, startBackend };
