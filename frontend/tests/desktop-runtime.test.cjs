const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const os = require('node:os');
const path = require('node:path');
const { isTrustedPage, resolveAsset, startBackend } = require('../electron/runtime.cjs');

test('desktop bridge is restricted to the local app or the explicit development origin', () => {
  assert.equal(isTrustedPage('app://localhost/settings/agents'), true);
  assert.equal(isTrustedPage('app://attacker/settings'), false);
  assert.equal(isTrustedPage('https://example.com'), false);
  assert.equal(isTrustedPage('http://127.0.0.1:5174/settings', 'http://127.0.0.1:5174'), true);
  assert.equal(isTrustedPage('http://127.0.0.1:8000/settings', 'http://127.0.0.1:5174'), false);
});

test('local protocol supports direct page reloads while rejecting traversal and missing assets', async () => {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), 'devharbor-assets-'));
  try {
    await fs.writeFile(path.join(root, 'index.html'), 'app');
    assert.equal(await resolveAsset(root, 'app://localhost/settings/agents'), path.join(root, 'index.html'));
    assert.equal(await resolveAsset(root, 'app://localhost/knowledge/123'), path.join(root, 'index.html'));
    assert.equal(await resolveAsset(root, 'app://localhost/assets/missing.js'), null);
    assert.equal(await resolveAsset(root, 'app://localhost/%2e%2e%2fprivate.txt'), null);
    assert.equal(await resolveAsset(root, 'app://localhost/%5c..%5cprivate.txt'), null);
    assert.equal(await resolveAsset(root, 'app://remote/index.html'), null);
  } finally {
    assert.equal(path.dirname(path.resolve(root)), path.resolve(os.tmpdir()));
    assert.ok(path.basename(root).startsWith('devharbor-assets-'));
    await fs.rm(root, { recursive: true, force: true });
  }
});

test('owned backend waits for readiness, accepts one shutdown, and exits without an orphan', async () => {
  const code = 'process.stdin.resume(); process.stdin.on("data", b => { if (JSON.parse(b).type === "shutdown") process.exit(0); }); console.log(JSON.stringify({type:"ready",port:12345}));';
  const backend = await startBackend({ command: process.execPath, args: ['-e', code], timeoutMs: 5000 });
  assert.equal(backend.port, 12345);
  await Promise.all([backend.stop(), backend.stop()]);
  assert.throws(() => process.kill(backend.pid, 0));
});

test('startup failure and invalid readiness reject instead of leaving a hanging splash', async () => {
  await assert.rejects(startBackend({ command: process.execPath, args: ['-e', 'process.exit(2)'], timeoutMs: 5000 }), /启动失败/);
  await assert.rejects(startBackend({ command: process.execPath, args: ['-e', 'console.log(JSON.stringify({type:"ready",port:0}))'], timeoutMs: 5000 }), /无效端口/);
});

test('database startup failure is reported after the original backend stops', async () => {
  const code = [
    'process.stdin.resume()',
    'process.stdin.on("data", () => process.exit(0))',
    'console.log(JSON.stringify({type:"database_unavailable"}))',
  ].join(';');
  await assert.rejects(
    startBackend({ command: process.execPath, args: ['-e', code], timeoutMs: 5000 }),
    { code: 'DATABASE_UNAVAILABLE' },
  );
});
