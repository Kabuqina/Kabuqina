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
assert.match(graphPage, /onLostPointerCapture=\{clearCapturedGesture\}/, "lost pointer capture clears drag feedback safely");
assert.match(graphPage, /<g pointerEvents="none"/, "edges never block canvas panning");
assert.match(graphPage, /collectGraphNeighborhood/, "hover, focus, and drag emphasize the direct graph neighborhood");
assert.match(graphPage, /draggingNodeId[\s\S]*settlingNodeId/, "node drag has distinct lifted and release states");
assert.match(graphPage, /motion-reduce:transition-none/, "graph transitions respect reduced-motion preferences");
assert.match(graphPage, /motion-reduce:animate-none/, "drag emphasis does not pulse when reduced motion is requested");
assert.match(graphPage, /cmdStudyKnowledgeGraph/, "graph loads owner-scoped backend projection");
assert.match(graphPage, /\/study\/knowledge\/\$\{encodeURIComponent\(node\.artifact_id\)\}/, "node opens its document route");
assert.match(conceptPage, /<ChatMarkdown text=\{articleBody\} variant="article"/, "concept document uses the full article reader");
assert.match(conceptPage, /concept\.source_section[\s\S]*concept\.source_locator/, "concept detail preserves its document location");
assert.match(conceptPage, /concept\.review_prompt/, "atomic concepts provide a focused review question");
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
