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

function createStorage() {
  const data = new Map();
  return {
    getItem(key) {
      return data.has(key) ? data.get(key) : null;
    },
    setItem(key, value) {
      data.set(key, String(value));
    },
    removeItem(key) {
      data.delete(key);
    },
  };
}

const store = await importTs("./quizStore.ts");

// ---------------------------------------------------------------------------
// normalizeQuestion: validation
// ---------------------------------------------------------------------------

assert.equal(store.normalizeQuestion(null), null);
assert.equal(store.normalizeQuestion({ type: "single" }), null, "no prompt -> dropped");
assert.equal(
  store.normalizeQuestion({ type: "single", prompt: "q", options: ["only one"], answerIndices: [0] }),
  null,
  "single option is not a choice question",
);
assert.equal(
  store.normalizeQuestion({ type: "single", prompt: "q", options: ["a", "b"], answerIndices: [5] }),
  null,
  "answer index out of range -> dropped",
);
assert.equal(
  store.normalizeQuestion({ type: "short", prompt: "q" }),
  null,
  "short with no accepted answers -> dropped",
);

const single = store.normalizeQuestion({
  type: "single",
  prompt: "  2 + 2 = ?  ",
  options: ["3", "4", "5"],
  answerIndices: [1, 2],
  points: "3",
});
assert.equal(single.type, "single");
assert.equal(single.prompt, "2 + 2 = ?");
assert.deepEqual(single.answerIndices, [1], "single keeps only first correct index");
assert.equal(single.points, 3, "points coerced from string");

const multiple = store.normalizeQuestion({
  type: "multiple",
  prompt: "pick primes",
  options: ["2", "3", "4", "6"],
  answer: [0, 1, 1, 9],
});
assert.equal(multiple.type, "multiple");
assert.deepEqual(multiple.answerIndices, [0, 1], "dedup + out-of-range dropped");

// Type inference when omitted.
assert.equal(
  store.normalizeQuestion({ prompt: "q", accepted: ["yes"] }).type,
  "short",
  "no options -> short",
);
assert.equal(
  store.normalizeQuestion({ prompt: "q", options: ["a", "b"], answer: [0, 1] }).type,
  "multiple",
  "multiple correct -> multiple",
);
assert.equal(
  store.normalizeQuestion({ prompt: "q", options: ["a", "b"], answer: [0] }).type,
  "single",
);

// Points clamping.
assert.equal(store.normalizeQuestion({ prompt: "q", accepted: ["a"], points: -3 }).points, 1);
assert.equal(store.normalizeQuestion({ prompt: "q", accepted: ["a"], points: 9999 }).points, store.QUIZ_MAX_POINTS);

// Option / accepted count caps.
const manyOpts = store.normalizeQuestion({
  prompt: "q",
  options: Array.from({ length: 30 }, (_, i) => `o${i}`),
  answer: [0],
});
assert.equal(manyOpts.options.length, store.QUIZ_MAX_OPTIONS);

// ---------------------------------------------------------------------------
// normalizeQuiz / parseQuiz
// ---------------------------------------------------------------------------

assert.deepEqual(store.normalizeQuiz(null), store.emptyQuiz());
assert.deepEqual(store.normalizeQuiz("garbage"), store.emptyQuiz());
assert.deepEqual(store.parseQuiz(""), store.emptyQuiz());
assert.deepEqual(store.parseQuiz("not json"), store.emptyQuiz());
assert.deepEqual(store.parseQuiz("{bad json"), store.emptyQuiz());

const parsed = store.parseQuiz(
  'Here is your quiz:\n```json\n{"title":"ML basics","questions":[' +
    '{"type":"single","prompt":"Q1","options":["a","b"],"answer":[0],"tags":["ml"]},' +
    '{"type":"single","prompt":"bad","options":["a"],"answer":[0]},' +
    '{"type":"short","prompt":"Q2","accepted":["gradient descent"],"tags":["opt"]}' +
    ']}\n```',
);
assert.equal(parsed.title, "ML basics");
assert.equal(parsed.questions.length, 2, "invalid single-option question dropped");
assert.deepEqual(parsed.questions.map((q) => q.type), ["single", "short"]);

// Question cap.
const bulk = { questions: Array.from({ length: 200 }, (_, i) => ({ prompt: `q${i}`, accepted: ["a"] })) };
assert.equal(store.normalizeQuiz(bulk).questions.length, store.QUIZ_MAX_QUESTIONS);

// Duplicate ids regenerated.
const dupIds = store.normalizeQuiz({
  questions: [
    { id: "x", prompt: "a", accepted: ["1"] },
    { id: "x", prompt: "b", accepted: ["2"] },
  ],
});
assert.notEqual(dupIds.questions[0].id, dupIds.questions[1].id);

// ---------------------------------------------------------------------------
// normalizeShortAnswer
// ---------------------------------------------------------------------------

assert.equal(store.normalizeShortAnswer("  Gradient Descent!  "), "gradient descent");
// Trailing punctuation/symbols are stripped; this is symmetric (accepted and
// response are normalized the same way) so it never breaks matching.
assert.equal(store.normalizeShortAnswer("Backpropagation."), "backpropagation");
assert.equal(store.normalizeShortAnswer("多个   空格"), "多个 空格");

// ---------------------------------------------------------------------------
// gradeQuestion
// ---------------------------------------------------------------------------

const q1 = store.normalizeQuestion({ type: "single", prompt: "q", options: ["a", "b", "c"], answer: [1] });
assert.equal(store.gradeQuestion(q1, { selected: [1], text: "" }), true);
assert.equal(store.gradeQuestion(q1, { selected: [0], text: "" }), false);
assert.equal(store.gradeQuestion(q1, undefined), false, "no response -> incorrect");
assert.equal(store.gradeQuestion(q1, { selected: [1, 2], text: "" }), false, "extra selection wrong for single");
assert.equal(store.gradeQuestion(q1, { selected: [99], text: "" }), false, "out-of-range selection ignored");

const q2 = store.normalizeQuestion({ type: "multiple", prompt: "q", options: ["a", "b", "c", "d"], answer: [0, 2] });
assert.equal(store.gradeQuestion(q2, { selected: [2, 0], text: "" }), true, "order-independent set match");
assert.equal(store.gradeQuestion(q2, { selected: [0], text: "" }), false, "partial is not credited");
assert.equal(store.gradeQuestion(q2, { selected: [0, 2, 1], text: "" }), false, "superset is wrong");

const q3 = store.normalizeQuestion({ type: "short", prompt: "q", accepted: ["Gradient Descent", "SGD"] });
assert.equal(store.gradeQuestion(q3, { selected: [], text: " gradient descent " }), true);
assert.equal(store.gradeQuestion(q3, { selected: [], text: "sgd!" }), true);
assert.equal(store.gradeQuestion(q3, { selected: [], text: "adam" }), false);
assert.equal(store.gradeQuestion(q3, { selected: [], text: "   " }), false, "blank short answer -> incorrect");

// ---------------------------------------------------------------------------
// gradeQuiz: scoring, percent, weak tags
// ---------------------------------------------------------------------------

const quiz = store.normalizeQuiz({
  title: "T",
  questions: [
    { id: "a", type: "single", prompt: "q1", options: ["x", "y"], answer: [0], points: 2, tags: ["topic-a"] },
    { id: "b", type: "multiple", prompt: "q2", options: ["p", "q", "r"], answer: [0, 1], points: 3, tags: ["topic-b"] },
    { id: "c", type: "short", prompt: "q3", accepted: ["z"], points: 1, tags: ["topic-c"] },
  ],
});
const result = store.gradeQuiz(quiz, {
  a: { selected: [0], text: "" }, // correct (2)
  b: { selected: [0], text: "" }, // wrong -> weak topic-b
  c: { selected: [], text: "wrong" }, // wrong -> weak topic-c
});
assert.equal(result.total, 3);
assert.equal(result.correctCount, 1);
assert.equal(result.score, 2);
assert.equal(result.maxScore, 6);
assert.equal(result.percent, Math.round((2 / 6) * 100));
assert.deepEqual(result.weakTags.sort(), ["topic-b", "topic-c"]);
assert.equal(result.perQuestion.find((p) => p.id === "a").earned, 2);
assert.equal(result.perQuestion.find((p) => p.id === "b").earned, 0);

// Empty quiz: no divide-by-zero.
const emptyResult = store.gradeQuiz(store.emptyQuiz(), {});
assert.equal(emptyResult.percent, 0);
assert.equal(emptyResult.maxScore, 0);

// formatQuizResultForContext is plain text with the score.
const summary = store.formatQuizResultForContext(quiz, result);
assert.match(summary, /2\/6/);
assert.match(summary, /topic-b/);

// ---------------------------------------------------------------------------
// Persistence + corrupt-storage resilience
// ---------------------------------------------------------------------------

globalThis.window = { localStorage: createStorage(), dispatchEvent() {} };
globalThis.Event = class {
  constructor(type) {
    this.type = type;
  }
};

const state = {
  version: 1,
  quiz,
  responses: {
    a: { selected: [0], text: "" },
    b: { selected: [0, 99], text: "" }, // 99 out of range -> dropped on normalize
    ghost: { selected: [0], text: "" }, // unknown id -> dropped
  },
  submitted: true,
};
const saved = store.saveQuizState(state);
assert.deepEqual(saved.responses.b.selected, [0], "out-of-range selection stripped on save");
assert.equal(saved.responses.ghost, undefined, "response for unknown question dropped");
assert.equal(saved.submitted, true);

const loaded = store.loadQuizState();
assert.equal(loaded.quiz.questions.length, 3);
assert.equal(loaded.submitted, true);

assert.deepEqual(store.clearQuizState(), store.emptyQuizState());
assert.deepEqual(store.loadQuizState(), store.emptyQuizState());

window.localStorage.setItem(store.QUIZ_STORAGE_KEY, "{bad json");
assert.deepEqual(store.loadQuizState(), store.emptyQuizState());

console.log("quizStore.test.mjs: ok");
