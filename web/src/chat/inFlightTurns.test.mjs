/* global process */
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
      jsx: ts.JsxEmit.ReactJSX,
      verbatimModuleSyntax: true,
    },
  }).outputText;
  const tempPath = path.join(
    os.tmpdir(),
    `kabuqina-inflight-${path.basename(relativePath, ".ts")}-${process.pid}-${Date.now()}.mjs`,
  );
  fs.writeFileSync(tempPath, compiled, "utf8");
  try {
    return await import(pathToFileURL(tempPath).href);
  } finally {
    fs.rmSync(tempPath, { force: true });
  }
}

const { latestAssistantText, mergeInFlightMessages } = await importTs("./inFlightTurnUtils.ts");

const turn = {
  sessionId: "s1",
  requestId: "r1",
  startedAt: 1,
  userMsg: { id: "u-local", role: "user", text: "精确识别PDF", timestamp: 1 },
  pendingAssistant: { id: "pending-assistant", role: "assistant", text: "…", timestamp: 1 },
  streamedText: "",
  status: "running",
  progress: null,
};

assert.deepEqual(
  mergeInFlightMessages([], turn).messages.map((m) => [m.role, m.text]),
  [
    ["user", "精确识别PDF"],
    ["assistant", "…"],
  ],
  "empty DB transcript should still show the in-flight user turn and pending assistant",
);

assert.deepEqual(
  mergeInFlightMessages([{ id: "m0", role: "user", text: "精确识别PDF" }], turn).messages.map((m) => [
    m.role,
    m.text,
  ]),
  [
    ["user", "精确识别PDF"],
    ["assistant", "…"],
  ],
  "DB user row should not be duplicated when adding the pending assistant",
);

assert.deepEqual(
  mergeInFlightMessages(
    [{ id: "m0", role: "user", text: "精确识别PDF" }],
    { ...turn, userMsg: { ...turn.userMsg, attachments: [{ name: "paper.pdf", mime: "application/pdf" }] } },
  ).messages.map((m) => [m.role, m.text]),
  [
    ["user", "精确识别PDF"],
    ["assistant", "…"],
  ],
  "DB user rows without attachment metadata should still match the in-flight attachment turn",
);

const finalized = mergeInFlightMessages(
  [
    { id: "m0", role: "user", text: "精确识别PDF" },
    { id: "m1", role: "assistant", text: "识别完成" },
  ],
  turn,
);
assert.equal(finalized.clearTurn, true);
assert.deepEqual(
  finalized.messages.map((m) => [m.role, m.text]),
  [
    ["user", "精确识别PDF"],
    ["assistant", "识别完成"],
  ],
  "DB final assistant row should replace the in-flight overlay",
);

assert.deepEqual(
  mergeInFlightMessages([], { ...turn, status: "failed" }).messages.map((m) => [m.role, m.text]),
  [["user", "精确识别PDF"]],
  "failed in-flight turns preserve the user message without a stale pending assistant",
);

assert.equal(
  latestAssistantText([
    { role: "user", content: "hi" },
    { role: "assistant", content: [{ type: "text", text: "done" }] },
  ]),
  "done",
);
