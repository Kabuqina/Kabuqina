import assert from "node:assert/strict";
import fs from "node:fs";

const graphPage = fs.readFileSync(new URL("./KnowledgeGraphPage.tsx", import.meta.url), "utf8");
const conceptPage = fs.readFileSync(new URL("./KnowledgeConceptPage.tsx", import.meta.url), "utf8");
const panel = fs.readFileSync(new URL("../chat/study/KnowledgeBasePanel.tsx", import.meta.url), "utf8");
const main = fs.readFileSync(new URL("../main.tsx", import.meta.url), "utf8");
const sidebar = fs.readFileSync(new URL("../chat/ChatSidebar.tsx", import.meta.url), "utf8");
const chatPage = fs.readFileSync(new URL("../chat/ChatPage.tsx", import.meta.url), "utf8");
const studySection = fs.readFileSync(new URL("../chat/study/StudySection.tsx", import.meta.url), "utf8");
const studyApi = fs.readFileSync(new URL("../chat/study/study-api.ts", import.meta.url), "utf8");

assert.match(graphPage, /onWheel=/, "graph supports wheel zoom");
assert.match(graphPage, /onPointerMove=\{moveGesture\}/, "graph supports canvas and node dragging");
assert.match(graphPage, /getScreenCTM/, "pointer coordinates account for SVG letterboxing");
assert.match(graphPage, /onPointerCancel=\{cancelGesture\}/, "cancelled gestures never open a node");
assert.match(graphPage, /<g pointerEvents="none"/, "edges never block canvas panning");
assert.match(graphPage, /cmdStudyKnowledgeGraph/, "graph loads owner-scoped backend projection");
assert.match(graphPage, /\/study\/knowledge\/\$\{encodeURIComponent\(node\.artifact_id\)\}/, "node opens its document route");
assert.match(conceptPage, /<ChatMarkdown text=\{articleBody\} variant="article"/, "concept document uses the full article reader");
assert.match(panel, /cmdStudyArtifactActivate/, "knowledge drafts require explicit activation");
assert.match(panel, /\/study\/knowledge-graph/, "knowledge panel links to the graph");
assert.match(main, /path="\/study\/knowledge-graph"/);
assert.match(main, /path="\/study\/knowledge\/:artifactId\/:conceptIndex"/);
assert.match(sidebar, /onOpenKnowledgeGraph/);
assert.match(chatPage, /onOpenKnowledgeGraph=\{\(\) => nav\("\/study\/knowledge-graph"\)\}/);
assert.match(studySection, /<KnowledgeBasePanel onStartPrompt=\{onStartPrompt\} \/>/);
assert.match(studyApi, /invoke\("cmd_study_knowledge_graph"\)/);
assert.match(studyApi, /invoke\("cmd_study_knowledge_concept"/);

console.log("knowledgeGraphUx.test.mjs: ok");
