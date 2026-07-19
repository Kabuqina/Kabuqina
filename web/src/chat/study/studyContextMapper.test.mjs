import assert from "node:assert/strict";
import fs from "node:fs";
import ts from "typescript";

async function importTs(path) {
  const source = fs.readFileSync(new URL(path, import.meta.url), "utf8");
  const js = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.ES2022, target: ts.ScriptTarget.ES2022 },
  }).outputText.replace('import { emptyStudyContext, normalizeStudyContext } from "./studyStore";', `
    const emptyStudyContext = () => ({ course:"", goal:"", profileSummary:"", weakPoints:"", preferences:"", progressNotes:"", assessmentEvidence:"", currentStage:"", generatedResources:"", tutoringNotes:"", evaluationSummary:"", nextAdjustment:"" });
    const normalizeStudyContext = (value) => Object.fromEntries(Object.entries(emptyStudyContext()).map(([key]) => [key, typeof value?.[key] === "string" ? value[key].trim().slice(0, 800) : ""]));
  `);
  return import(`data:text/javascript;base64,${Buffer.from(js).toString("base64")}`);
}

const mapper = await importTs("./studyContextMapper.ts");
const context = {
  course: "Algebra",
  goal: "Pass",
  profileSummary: "Likes examples",
  weakPoints: "prime numbers\nfactoring",
  preferences: "30 minutes daily",
  progressNotes: "Finished chapter 1",
  assessmentEvidence: "Quiz 1: 70%",
  currentStage: "Practice",
  generatedResources: "Factoring guide",
  tutoringNotes: "Review signs",
  evaluationSummary: "Application is weak",
  nextAdjustment: "Add mixed review",
};

const state = mapper.studyContextToStudentState(context);
const evaluation = mapper.studyContextToEvaluation(context);
assert.deepEqual(state.progress_notes, ["Finished chapter 1", "Factoring guide"]);
assert.equal("generated_resources" in state, false);
assert.equal("tutoring_notes" in state, false);
assert.deepEqual(evaluation.weak_points, ["prime numbers", "factoring"]);
assert.deepEqual(evaluation.observations, ["Application is weak", "Quiz 1: 70%", "Review signs"]);
const restored = mapper.backendPayloadsToStudyContext(state, evaluation);
assert.equal(restored.course, "Algebra");
assert.equal(restored.progressNotes, "Finished chapter 1\nFactoring guide");
assert.equal(restored.evaluationSummary, "Application is weak\nQuiz 1: 70%\nReview signs");
assert.equal(
  mapper.studyContextToEvaluation({
    ...context,
    weakPoints: "",
    assessmentEvidence: "",
    tutoringNotes: "",
    evaluationSummary: "",
    nextAdjustment: "",
  }),
  null,
);

console.log("studyContextMapper.test.mjs: ok");
