import assert from "node:assert/strict";
import fs from "node:fs";
import ts from "typescript";

async function importTs(path) {
  const source = fs.readFileSync(new URL(path, import.meta.url), "utf8");
  const js = ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.ES2022,
      target: ts.ScriptTarget.ES2022,
    },
  }).outputText;
  const url = `data:text/javascript;base64,${Buffer.from(js).toString("base64")}`;
  return import(url);
}

function createStorage(initial) {
  const data = new Map(Object.entries(initial));
  return {
    removeItem(key) {
      data.delete(key);
    },
    has(key) {
      return data.has(key);
    },
    get(key) {
      return data.get(key);
    },
  };
}

const cleanup = await importTs("./cacheCleanup.ts");

assert.deepEqual(cleanup.VOLATILE_LOCAL_STORAGE_KEYS, [
  "kabuqina.study.context.v1",
  "kabuqina.study.flashcards.v1",
  "kabuqina.study.quiz.v1",
  "hermesdesk.shell.chat.lastSessionId",
]);
assert.deepEqual(cleanup.VOLATILE_SESSION_STORAGE_KEYS, ["hermesdesk.onboarding-draft"]);

const protectedLocalValues = {
  "hermesdesk.locale": "en",
  "hermesdesk.ui.fontSize": "large",
  "hermesdesk.ui.themeMode": "dark",
  "hermesdesk.ui.customCompanionImage": "data:image/png;base64,keep",
  "hermesdesk.allow_chat_without_api": "1",
  "kabuqina.workbench.layout": "keep-layout",
  "future.user.preference": "keep-unknown-preference",
};
const localStorage = createStorage({
  ...protectedLocalValues,
  "kabuqina.study.context.v1": "remove-context",
  "kabuqina.study.flashcards.v1": "remove-cards",
  "kabuqina.study.quiz.v1": "remove-quiz",
  "hermesdesk.shell.chat.lastSessionId": "remove-session-selection",
});
const sessionStorage = createStorage({
  "hermesdesk.onboarding-draft": "remove-draft",
  "future.session.preference": "keep-session-preference",
});
const cacheNames = new Set(["shell-pages", "generated-resources"]);
const result = await cleanup.clearVolatileBrowserCache({
  localStorage,
  sessionStorage,
  caches: {
    async keys() {
      return [...cacheNames];
    },
    async delete(name) {
      return cacheNames.delete(name);
    },
  },
});

assert.deepEqual(result, { removedCacheBuckets: 2, errors: [] });
for (const key of cleanup.VOLATILE_LOCAL_STORAGE_KEYS) {
  assert.equal(localStorage.has(key), false, `${key} should be removed`);
}
assert.equal(sessionStorage.has("hermesdesk.onboarding-draft"), false);
assert.equal(sessionStorage.get("future.session.preference"), "keep-session-preference");
assert.equal(cacheNames.size, 0);
for (const [key, value] of Object.entries(protectedLocalValues)) {
  assert.equal(localStorage.get(key), value, `${key} should be preserved`);
}

let cacheDeleteAttempted = false;
const failureResult = await cleanup.clearVolatileBrowserCache({
  get localStorage() {
    throw new Error("storage disabled");
  },
  sessionStorage: createStorage({ "hermesdesk.onboarding-draft": "remove" }),
  caches: {
    async keys() {
      return ["still-clear-cache"];
    },
    async delete() {
      cacheDeleteAttempted = true;
      return true;
    },
  },
});
assert.equal(cacheDeleteAttempted, true, "one storage failure must not stop other cache cleanup");
assert.equal(failureResult.removedCacheBuckets, 1);
assert.match(failureResult.errors.join("\n"), /localStorage: storage disabled/);

console.log("cacheCleanup.test.mjs: ok");
