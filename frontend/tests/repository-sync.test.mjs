import assert from "node:assert/strict";
import test from "node:test";
import { getRepositorySyncError, isDemoRepository, refreshRepositoryData } from "../lib/repository-sync.ts";

const sample = {
  id: "demo", owner: "devharbor-demo", name: "devharbor-sample-api",
  full_name: "devharbor-demo/devharbor-sample-api", provider: "github",
  description: "Sample repository for the DevHarbor local demo"
};
const real = { ...sample, id: "real", full_name: "owner/project", description: "A real project" };

test("bundled demo reloads locally without making a remote sync request", async () => {
  let reloads = 0;
  await refreshRepositoryData(sample, {
    sync: async () => { assert.fail("A fictional demo repository must not contact GitHub"); },
    reload: async () => { reloads++; }
  });
  assert.equal(reloads, 1);
  assert.equal(isDemoRepository({ ...sample, description: "A real repository with the same name" }), false);
  assert.equal(isDemoRepository(undefined), false);
});

test("real repository refresh waits for remote sync before reading data", async () => {
  const events = [];
  await refreshRepositoryData(real, {
    sync: async () => { events.push("sync"); },
    reload: async () => { events.push("reload"); }
  });
  assert.deepEqual(events, ["sync", "reload"]);
});

test("rate limit failure neither reloads nor retries; callers can retain current lists", async () => {
  let requests = 0;
  const failure = new Error('GitHub issues sync failed: 403 {"message":"API rate limit exceeded for 192.0.2.1"}');
  await assert.rejects(refreshRepositoryData(real, {
    sync: async () => { requests++; throw failure; },
    reload: async () => { assert.fail("Do not replace displayed data after a failed sync"); }
  }), failure);
  assert.equal(requests, 1);
  const message = getRepositorySyncError(failure);
  assert.match(message, /GitHub 请求次数已达上限/);
  assert.doesNotMatch(message, /192\.0\.2\.1|\{"message"/);
});

test("network and other failures are not mislabeled as rate limits", () => {
  assert.match(getRepositorySyncError(new Error("Failed to fetch")), /无法连接后端服务/);
  assert.doesNotMatch(getRepositorySyncError(new Error("403 Forbidden")), /次数已达上限/);
  assert.match(getRepositorySyncError(new Error('{"detail":"secondary rate limit"}')), /请求次数已达上限/);
});

test("local read failures remain visible to the caller", async () => {
  await assert.rejects(refreshRepositoryData(sample, {
    sync: async () => { assert.fail("No remote sync for the demo"); },
    reload: async () => { throw new Error("Local API unavailable"); }
  }), /Local API unavailable/);
});
