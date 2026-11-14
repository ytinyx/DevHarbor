import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import Module from "node:module";
import path from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";
import ts from "typescript";

const filename = fileURLToPath(new URL("../lib/model-providers.ts", import.meta.url));
const compiled = ts.transpileModule(readFileSync(filename, "utf8"), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2021 },
});

function setup(t, api) {
  const loaded = new Module(filename);
  loaded.paths = Module._nodeModulePaths(path.dirname(filename));
  loaded.require = (specifier) => {
    assert.equal(specifier, "@/lib/api");
    return api;
  };
  loaded._compile(compiled.outputText, filename);
  const originalWindow = globalThis.window;
  globalThis.window = new EventTarget();
  t.after(() => {
    if (originalWindow === undefined) delete globalThis.window;
    else globalThis.window = originalWindow;
  });
  let changed = 0;
  window.addEventListener(loaded.exports.MODEL_PROVIDERS_CHANGED_EVENT, () => changed++);
  return { ...loaded.exports, changes: () => changed };
}

test("selecting a model notifies other controls only after the saved selection succeeds", async (t) => {
  let resolveSelection;
  const selection = new Promise((resolve) => { resolveSelection = resolve; });
  const calls = [];
  const client = setup(t, { apiPost: (endpoint, input) => { calls.push({ endpoint, input }); return selection; } });
  const pending = client.activateModelProvider("provider-1", "model-b");
  assert.deepEqual(calls, [{ endpoint: "/api/settings/model-providers/activate", input: { provider_id: "provider-1", model: "model-b" } }]);
  assert.equal(client.changes(), 0);
  const active = { provider_id: "provider-1", model: "model-b" };
  resolveSelection(active);
  assert.deepEqual(await pending, active);
  assert.equal(client.changes(), 1);
});

test("failed model switches do not announce a changed active model", async (t) => {
  const client = setup(t, { apiPost: async () => { throw new Error("保存失败"); } });
  await assert.rejects(client.activateModelProvider("provider-1", "model-b"), /保存失败/);
  assert.equal(client.changes(), 0);
});

test("switching back to environment configuration resets the saved selection", async (t) => {
  const client = setup(t, { apiPost: async (endpoint, input) => {
    assert.equal(endpoint, "/api/settings/model-providers/reset-active");
    assert.deepEqual(input, {});
    return { provider_id: null, model: null };
  } });
  assert.deepEqual(await client.resetActiveModel(), { provider_id: null, model: null });
  assert.equal(client.changes(), 1);
});

test("reading the catalog never announces a model mutation", async (t) => {
  const settings = { providers: [], active: { provider_id: null, model: null }, environment: { configured: false, model: null, base_url: null } };
  const client = setup(t, { apiGet: async () => settings });
  assert.deepEqual(await client.loadModelProviders(), settings);
  assert.equal(client.changes(), 0);
});
