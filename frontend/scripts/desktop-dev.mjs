import { createServer } from 'vite';
import { spawn } from 'node:child_process';
import electron from 'electron';
import { DESKTOP_DEV_RESTART } from '../electron/runtime.cjs';

const server = await createServer();
await server.listen();
server.printUrls();
const environment = { ...process.env, DEVHARBOR_RENDERER_URL: 'http://127.0.0.1:5174' };
delete environment.ELECTRON_RUN_AS_NODE;
let desktop;
let stopping = false;

function startDesktop() {
  desktop = spawn(electron, ['.'], { env: environment, stdio: 'inherit', windowsHide: true });
  desktop.once('error', async (error) => {
    console.error(error.message);
    await server.close();
    process.exitCode = 1;
  });
  desktop.once('exit', async (code) => {
    if (!stopping && code === DESKTOP_DEV_RESTART) {
      startDesktop();
      return;
    }
    await server.close();
    process.exitCode = code ?? 1;
  });
}

startDesktop();
for (const signal of ['SIGINT', 'SIGTERM']) process.on(signal, () => {
  stopping = true;
  desktop.kill(signal);
});
