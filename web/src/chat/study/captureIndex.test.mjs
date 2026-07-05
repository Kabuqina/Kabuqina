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
  const compiled = ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.ES2022,
      target: ts.ScriptTarget.ES2022,
      verbatimModuleSyntax: true,
    },
  }).outputText;
  const tempPath = path.join(
    os.tmpdir(),
    `kabuqina-capture-index-${path.basename(relativePath, ".ts")}-${process.pid}-${Date.now()}.mjs`,
  );
  fs.writeFileSync(tempPath, compiled, "utf8");
  try {
    return await import(pathToFileURL(tempPath).href);
  } finally {
    fs.rmSync(tempPath, { force: true });
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
