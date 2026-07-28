// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import type { CheckResult, DeskData } from "./types";

// Copy is taken verbatim from the frozen canonical prototype
// (docs/superpowers/prototypes/2026-07-23-v0.5.0-desk-canonical.html).

export const deskFixtureData: DeskData = {
  course: {
    name: "高等数学 · 极限",
    notebookLabel: "我的课程笔记本 · 最近保存 13:42",
  },
  steps: [
    {
      id: "ex3-step2",
      kicker: "练习 3 · 第 2 步",
      title: "解释为什么不能直接代入",
      standard: "区分“得到 0/0”与“得到极限值”，并指出下一步需要继续分析。",
      prompt: "计算 lim (x² − 1) / (x − 1)，x → 1。为什么不能把直接代入得到的 0/0 当作答案？",
      referenceSummary: "直接代入得到未定式时，先识别结构，再选择等价变形。",
      referenceHint: "x² − 1 = (x − 1)(x + 1)",
      initialDraft: "代入后分子和分母同时为 0，所以需要先变形。",
    },
    {
      id: "ex3-step3",
      kicker: "练习 3 · 第 3 步",
      title: "用等价变形求出极限",
      standard: "写出因式分解，说明约分只在 x≠1 时成立，并得到极限值。",
      prompt: "继续上一步：当 x≠1 时怎样化简 (x² − 1) / (x − 1)，并求出 x → 1 的极限？",
      referenceSummary: "直接代入得到未定式时，先识别结构，再选择等价变形。",
      referenceHint: "x² − 1 = (x − 1)(x + 1)",
      initialDraft: "",
    },
  ],
  overview: {
    kicker: "上次学习 · 今天 13:42",
    heading: "从“0/0 是什么”继续",
    body: "你已经写下直接代入的结果。下一步是把它解释成一句可以检查的话。",
    resume: [
      { icon: "circleCheck", text: "已识别分子、分母同时趋近 0" },
      { icon: "circleDot", text: "待说明：0/0 是未定式，不是极限值" },
    ],
  },
  bookstand: {
    title: "我的课程本",
    hint: "换课就是换一本本子。",
    books: [
      { id: "fixture-calculus", name: "高等数学", current: true },
      { id: "fixture-physics", name: "大学物理", current: false },
    ],
    scratch: { id: "fixture-scratch", name: "杂记本", current: false },
    newBookLabel: "开新本",
  },
  materials: {
    title: "参考资料",
    hint: "平放在这本高数笔记本旁。",
    items: [
      { id: "material-1", title: "教材 §2.3", kind: "resource_pack", status: "active" },
      { id: "material-2", title: "习题集 p.41", kind: "knowledge_base", status: "active" },
    ],
  },
  activities: [{
    id: "activity-1",
    type: "quiz.attempt",
    artifactId: "quiz-1",
    createdAt: "2026-07-24T13:42:00+08:00",
  }],
  dueCards: Array.from({ length: 6 }, (_, index) => ({
    item_id: `card-${index + 1}`,
    artifact_id: "cards-1",
    front: `极限卡片 ${index + 1}`,
    back: "先识别未定式，再选择等价变形。",
  })),
  dueCount: 6,
};

/** F0 feedback copy, verbatim from the frozen prototype. */
export const needsRevisionResult: CheckResult = {
  verdict: "needs_revision",
  goodLabel: "已经说明清楚",
  good: "代入后分子、分母都趋近 0。",
  gap: "说明 0/0 是未定式，不是极限值。",
  next: "把这句话补进你的解释，再检查一次。",
};

/** F1 feedback copy, verbatim from the frozen prototype. */
export const completedResult: CheckResult = {
  verdict: "completed",
  goodLabel: "这一点已经说明清楚",
  good: "你区分了“得到未定式”和“得到极限值”。",
  gap: "",
  next: "",
};
