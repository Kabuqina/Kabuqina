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

const store = await importTs("./studyStore.ts");

assert.equal(store.STUDY_CONTEXT_STORAGE_KEY, "kabuqina.study.context.v1");
assert.equal(store.STUDY_CONTEXT_FIELD_LIMIT, 800);

assert.deepEqual(store.emptyStudyContext(), {
  course: "",
  goal: "",
  profileSummary: "",
  weakPoints: "",
  preferences: "",
  progressNotes: "",
  assessmentEvidence: "",
});

assert.deepEqual(store.normalizeStudyContext(null), store.emptyStudyContext());
assert.deepEqual(
  store.normalizeStudyContext({
    course: "  机器学习基础  ",
    goal: 123,
    profileSummary: "Python 基础",
    weakPoints: "F1 混淆",
    preferences: "每天 1 小时",
    progressNotes: "完成逻辑回归",
    assessmentEvidence: "基础题 8/10",
  }),
  {
    course: "机器学习基础",
    goal: "",
    profileSummary: "Python 基础",
    weakPoints: "F1 混淆",
    preferences: "每天 1 小时",
    progressNotes: "完成逻辑回归",
    assessmentEvidence: "基础题 8/10",
  },
);

const longText = "x".repeat(900);
assert.equal(store.normalizeStudyContext({ course: longText }).course.length, 800);
assert.equal(store.hasStudyContext(store.emptyStudyContext()), false);
assert.equal(store.hasStudyContext({ ...store.emptyStudyContext(), goal: "掌握监督学习" }), true);

const formatted = store.formatStudyContextForPrompt({
  course: "机器学习基础",
  goal: "掌握监督学习",
  profileSummary: "",
  weakPoints: "模型评估指标",
  preferences: "",
  progressNotes: "已完成 20 道练习",
  assessmentEvidence: "进阶题 5/8",
});
assert.match(formatted, /已保存的学习上下文/);
assert.match(formatted, /课程\/专业方向：机器学习基础/);
assert.match(formatted, /学习目标：掌握监督学习/);
assert.match(formatted, /知识短板\/易错点：模型评估指标/);
assert.match(formatted, /学习进度\/行为记录：已完成 20 道练习/);
assert.match(formatted, /练习结果\/资源反馈：进阶题 5\/8/);
assert.doesNotMatch(formatted, /学习画像摘要：/);

globalThis.window = {
  localStorage: createStorage(),
  dispatchEvent() {},
};
globalThis.Event = class {
  constructor(type) {
    this.type = type;
  }
};

const saved = store.saveStudyContext({
  course: "  人工智能导论  ",
  goal: "完成课程项目",
  profileSummary: "",
  weakPoints: "",
  preferences: "图示优先",
  progressNotes: "完成第一章",
  assessmentEvidence: "小测 7/10",
});
assert.equal(saved.course, "人工智能导论");
assert.deepEqual(store.loadStudyContext(), saved);
assert.deepEqual(store.clearStudyContext(), store.emptyStudyContext());
assert.deepEqual(store.loadStudyContext(), store.emptyStudyContext());

window.localStorage.setItem(store.STUDY_CONTEXT_STORAGE_KEY, "{bad json");
assert.deepEqual(store.loadStudyContext(), store.emptyStudyContext());

console.log("studyStore.test.mjs: ok");
