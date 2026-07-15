/* global Event, EventTarget, process, setTimeout */
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { pathToFileURL } from "node:url";
import ts from "typescript";

async function importTs(relativePath) {
  const sourcePath = new URL(relativePath, import.meta.url);
  const source = fs.readFileSync(sourcePath, "utf8");
  const eventSourcePath = new URL("../../study/learningEvent.ts", import.meta.url);
  const eventCompiled = ts.transpileModule(fs.readFileSync(eventSourcePath, "utf8"), {
    compilerOptions: {
      module: ts.ModuleKind.ES2022,
      target: ts.ScriptTarget.ES2022,
      verbatimModuleSyntax: true,
    },
  }).outputText;
  const suffix = `${process.pid}-${Date.now()}`;
  const eventTempPath = path.join(os.tmpdir(), `kabuqina-learning-event-${suffix}.mjs`);
  fs.writeFileSync(eventTempPath, eventCompiled, "utf8");
  const eventTempUrl = pathToFileURL(eventTempPath).href;
  const compiled = ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.ES2022,
      target: ts.ScriptTarget.ES2022,
      verbatimModuleSyntax: true,
    },
  }).outputText.replaceAll("../../study/learningEvent", eventTempUrl);
  const tempPath = path.join(
    os.tmpdir(),
    `kabuqina-capture-index-${path.basename(relativePath, ".ts")}-${suffix}.mjs`,
  );
  fs.writeFileSync(tempPath, compiled, "utf8");
  try {
    return await import(pathToFileURL(tempPath).href);
  } finally {
    fs.rmSync(tempPath, { force: true });
    fs.rmSync(eventTempPath, { force: true });
  }
}

const { STUDY_LEARNING_EVENT, createCaptureIndex } = await importTs("./captureIndex.ts");

{
  let fetches = 0;
  const target = new EventTarget();
  const index = createCaptureIndex({
    target,
    fetcher: async () => {
      fetches += 1;
      return { cards: [{ front: " Bayes " }, { front: "Gradient" }] };
    },
  });

  assert.equal(index.status(), "idle");
  await index.initialize();
  assert.equal(fetches, 1);
  assert.equal(index.status(), "ready");
  assert.equal(index.has("bayes"), true);
  assert.equal(index.has(" gradient "), true);
  await index.initialize();
  assert.equal(fetches, 1, "initialize should be cached after success");
}

{
  const target = new EventTarget();
  const index = createCaptureIndex({
    target,
    fetcher: async () => ({ cards: [] }),
  });

  await index.initialize();
  const seen = [];
  const unsubscribe = index.subscribe(() => seen.push(index.has("Bayes")));
  assert.equal(index.has("Bayes"), false);
  index.markCaptured("Bayes");
  assert.equal(index.has("bayes"), true);
  assert.deepEqual(seen, [true]);
  unsubscribe();
  index.markCaptured("Other");
  assert.deepEqual(seen, [true]);
}

{
  let cards = [{ front: "A" }];
  const target = new EventTarget();
  const index = createCaptureIndex({
    target,
    fetcher: async () => ({ cards }),
  });

  await index.initialize();
  assert.equal(index.has("A"), true);
  cards = [{ front: "B" }];
  target.dispatchEvent(new Event(STUDY_LEARNING_EVENT));
  await new Promise((resolve) => setTimeout(resolve, 0));
  assert.equal(index.has("A"), false);
  assert.equal(index.has("B"), true);
}

{
  const target = new EventTarget();
  const index = createCaptureIndex({
    target,
    fetcher: async () => {
      throw new Error("offline");
    },
  });

  await index.initialize();
  assert.equal(index.status(), "unavailable");
  assert.equal(index.has("Bayes"), false);
}

{
  let fail = true;
  let fetches = 0;
  let now = 1_000;
  const index = createCaptureIndex({
    target: new EventTarget(),
    retryBackoffMs: 15_000,
    now: () => now,
    fetcher: async () => {
      fetches += 1;
      if (fail) throw new Error("offline");
      return { cards: [{ front: "Bayes" }] };
    },
  });

  await index.initialize();
  assert.equal(index.status(), "unavailable");
  now += 14_999;
  await index.initialize();
  assert.equal(fetches, 1, "initialize should back off after a failure");

  fail = false;
  const firstRefresh = index.forceRefresh();
  const secondRefresh = index.forceRefresh();
  assert.equal(firstRefresh, secondRefresh, "forceRefresh should reuse the pending request");
  await firstRefresh;
  assert.equal(index.status(), "ready");
  assert.equal(index.has("bayes"), true);
}

{
  let fail = true;
  let fetches = 0;
  let now = 20_000;
  const index = createCaptureIndex({
    target: new EventTarget(),
    retryBackoffMs: 15_000,
    now: () => now,
    fetcher: async () => {
      fetches += 1;
      if (fail) throw new Error("offline");
      return { cards: [{ front: "Gradient" }] };
    },
  });

  await index.initialize();
  fail = false;
  now += 15_000;
  await index.initialize();
  assert.equal(fetches, 2, "initialize should retry once the backoff elapsed");
  assert.equal(index.status(), "ready");
  assert.equal(index.has("Gradient"), true);
}

{
  let fetches = 0;
  let resolveFetch;
  const target = new EventTarget();
  const index = createCaptureIndex({
    target,
    fetcher: () => {
      fetches += 1;
      return new Promise((resolve) => {
        resolveFetch = resolve;
      });
    },
  });

  const initialized = index.initialize();
  const duplicateInitialize = index.initialize();
  const forced = index.forceRefresh();
  target.dispatchEvent(new Event(STUDY_LEARNING_EVENT));
  assert.equal(initialized, duplicateInitialize);
  assert.equal(initialized, forced);
  assert.equal(fetches, 1, "all refresh entry points should share one request");
  resolveFetch({ cards: [{ front: "Shared" }] });
  await initialized;
  assert.equal(index.has("shared"), true);
}
