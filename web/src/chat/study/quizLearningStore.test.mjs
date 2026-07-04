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

const store = await importTs("./quizLearningStore.ts");

const legacyQuiz = {
  version: 1,
  title: "Legacy quiz",
  questions: [
    {
      id: "q1",
      type: "single",
      prompt: " 2+2? ",
      options: ["3", "4"],
      answerIndices: [1],
      explanation: "addition",
      tags: ["math"],
      points: 2,
    },
    {
      id: "q2",
      type: "multiple",
      prompt: "Pick primes",
      options: ["2", "3", "4"],
      answerIndices: [0, 1],
      tags: ["prime"],
      points: 3,
    },
    {
      id: "q3",
      type: "short",
      prompt: "Optimizer abbreviated GD?",
      accepted: ["gradient descent", "GD"],
      tags: ["opt"],
      points: 4,
    },
  ],
};

assert.deepEqual(store.legacyQuizToMigrationQuiz(legacyQuiz), {
  title: "Legacy quiz",
  questions: [
    {
      type: "choice",
      prompt: "2+2?",
      options: ["3", "4"],
      answer: 1,
      explanation: "addition",
      tags: ["math"],
      points: 2,
    },
    {
      type: "choice",
      prompt: "Pick primes",
      options: ["2", "3", "4"],
      answer: [0, 1],
      tags: ["prime"],
      points: 3,
    },
    {
      type: "short_answer",
      prompt: "Optimizer abbreviated GD?",
      accepted: ["gradient descent", "GD"],
      tags: ["opt"],
      points: 4,
    },
  ],
});

assert.deepEqual(
  store.legacyQuizToMigrationQuiz({ title: "bad", questions: [{ prompt: "", accepted: ["x"] }] }),
  { title: "bad", questions: [] },
);

const backendQuestions = [
  {
    item_id: "item-1",
    artifact_id: "quiz-1",
    type: "choice",
    prompt: "Q",
    options: ["A", "B"],
    multiple: false,
    explanation: "E",
    tags: ["t"],
    points: 2,
  },
  {
    item_id: "item-2",
    artifact_id: "quiz-1",
    type: "true_false",
    prompt: "T/F",
    options: [],
    points: 1,
  },
];

assert.deepEqual(store.backendQuestionsToQuizRows(backendQuestions), [
  {
    itemId: "item-1",
    artifactId: "quiz-1",
    type: "choice",
    prompt: "Q",
    options: ["A", "B"],
    multiple: false,
    explanation: "E",
    tags: ["t"],
    points: 2,
  },
  {
    itemId: "item-2",
    artifactId: "quiz-1",
    type: "true_false",
    prompt: "T/F",
    options: [],
    multiple: false,
    explanation: "",
    tags: [],
    points: 1,
  },
]);

assert.deepEqual(
  store.responsesToSubmitPayload({
    "item-1": { selected: [1, 99], text: "ignored", value: true },
    "item-2": { selected: [], text: "", value: false },
  }),
  {
    "item-1": { selected: [1, 99], text: "ignored", value: true },
    "item-2": { selected: [], text: "", value: false },
  },
);

assert.equal(
  store.formatQuizAttemptSummary({ score: 7, maxScore: 10, percent: 70, correctCount: 3, total: 4 }, "zh"),
  "完成测验：7/10（70%，答对 3/4）。",
);
assert.equal(
  store.formatQuizAttemptSummary({ score: 2, maxScore: 4, percent: 50, correctCount: 1, total: 2 }, "en"),
  "Quiz complete: 2/4 (50%, 1/2 correct).",
);

console.log("quizLearningStore.test.mjs: ok");
