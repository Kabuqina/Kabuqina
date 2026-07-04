import assert from "node:assert/strict";
import fs from "node:fs";
import ts from "typescript";

async function importTs(path) {
  const source = fs.readFileSync(new URL(path, import.meta.url), "utf8");
  const js = ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.ES2022,
      target: ts.ScriptTarget.ES2022,
      jsx: ts.JsxEmit.ReactJSX,
    },
  }).outputText;
  const url = `data:text/javascript;base64,${Buffer.from(js).toString("base64")}`;
  return import(url);
}

const store = await importTs("./flashcardLearningStore.ts");

const legacy = {
  version: 1,
  cards: [
    {
      id: "old-1",
      front: " q ",
      back: " a ",
      hint: " h ",
      tags: ["math"],
      ease: 2.5,
      intervalDays: 12,
    },
  ],
};

assert.deepEqual(store.legacyDeckToMigrationDeck(legacy), {
  cards: [{ front: "q", back: "a", hint: "h", tags: ["math"] }],
});
assert.deepEqual(store.legacyDeckToMigrationDeck({ cards: [{ front: "", back: "x" }] }), {
  cards: [],
});

const backend = [
  {
    item_id: "item-1",
    artifact_id: "deck-1",
    front: "Q",
    back: "A",
    hint: "H",
    tags: ["t"],
    dueAt: "2026-01-01T00:00:00+00:00",
    repetitions: 0,
    intervalDays: 0,
  },
];
assert.deepEqual(store.backendCardsToQueue(backend), [
  {
    itemId: "item-1",
    artifactId: "deck-1",
    front: "Q",
    back: "A",
    hint: "H",
    tags: ["t"],
  },
]);

assert.equal(
  store.formatReviewSummary({ reviewed: 3, dueRemaining: 1 }, "zh"),
  "完成记忆卡片复习 3 张（待复习剩余 1）。",
);
assert.equal(
  store.formatReviewSummary({ reviewed: 2, dueRemaining: 0 }, "en"),
  "Reviewed 2 flashcard(s); 0 still due.",
);

console.log("flashcardLearningStore.test.mjs: ok");
