import assert from "node:assert/strict";
import fs from "node:fs";
import ts from "typescript";

const source = fs.readFileSync(new URL("./knowledgeGraphLayout.ts", import.meta.url), "utf8");
const js = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.ES2022, target: ts.ScriptTarget.ES2022 },
}).outputText;
const layout = await import(`data:text/javascript;base64,${Buffer.from(js).toString("base64")}`);

const nodes = [
  { id: "b", module: "AI" },
  { id: "a", module: "AI" },
  { id: "c", module: "Programming" },
];
assert.deepEqual(layout.layoutKnowledgeNodes(nodes), layout.layoutKnowledgeNodes([...nodes].reverse()));
assert.notDeepEqual(layout.layoutKnowledgeNodes(nodes).a, layout.layoutKnowledgeNodes(nodes).b);
assert.equal(layout.clampGraphScale(0.01), 0.35);
assert.equal(layout.clampGraphScale(9), 2.8);

const anchor = { x: 320, y: 240 };
const initial = { x: 20, y: -10, scale: 1 };
const zoomed = layout.zoomGraphAt(initial, 1.6, anchor);
const worldBefore = {
  x: (anchor.x - initial.x) / initial.scale,
  y: (anchor.y - initial.y) / initial.scale,
};
const worldAfter = {
  x: (anchor.x - zoomed.x) / zoomed.scale,
  y: (anchor.y - zoomed.y) / zoomed.scale,
};
assert.deepEqual(worldAfter, worldBefore, "zoom keeps the pointer anchor fixed in world space");

const crowded = Array.from({ length: 80 }, (_, index) => ({ id: `node-${index}`, module: `module-${index % 12}` }));
for (const point of Object.values(layout.layoutKnowledgeNodes(crowded))) {
  assert.ok(point.x >= 55 && point.x <= layout.GRAPH_VIEWBOX_WIDTH - 190);
  assert.ok(point.y >= 45 && point.y <= layout.GRAPH_VIEWBOX_HEIGHT - 45);
}

console.log("knowledgeGraphLayout.test.mjs: ok");
