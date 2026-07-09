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

const {
  hasVisibleAssistantStreamText,
  latestAssistantText,
  mergeInFlightMessages,
} = await importTs("./inFlightTurnUtils.ts");
const { shouldDisplayAgentProgress } = await importTs("./hooks/useAgentProgress.ts");

assert.equal(
  typeof hasVisibleAssistantStreamText,
  "function",
  "The chat render layer needs a shared helper for hiding placeholder-only assistant stream text.",
);

if (typeof hasVisibleAssistantStreamText === "function") {
  assert.equal(hasVisibleAssistantStreamText("…"), false);
  assert.equal(hasVisibleAssistantStreamText("..."), false);
  assert.equal(hasVisibleAssistantStreamText("  .…  "), false);
  assert.equal(hasVisibleAssistantStreamText("正在整理结果…"), true);
}

assert.equal(
  typeof shouldDisplayAgentProgress,
  "function",
  "Agent progress should expose the display policy for tool-only working bubbles.",
);

if (typeof shouldDisplayAgentProgress === "function") {
  const baseProgress = {
    running: true,
    status: "starting",
    iteration: 0,
    max_iterations: 0,
    current_tool: null,
    error: null,
    steps: [],
    nextSeq: 0,
  };
  assert.equal(
    shouldDisplayAgentProgress(baseProgress),
    false,
    "Starting without a tool should leave the ordinary waiting bubble visible.",
  );
  assert.equal(
    shouldDisplayAgentProgress({ ...baseProgress, status: "thinking" }),
    false,
    "Thinking without a tool should not show the tool progress bubble.",
  );
  assert.equal(
    shouldDisplayAgentProgress({ ...baseProgress, status: "tool", current_tool: "read_file" }),
    true,
    "A current tool should show the tool progress bubble.",
  );
  assert.equal(
    shouldDisplayAgentProgress({
      ...baseProgress,
      status: "thinking",
      steps: [
        {
          seq: 1,
          tool: "read_file",
          preview: "paper.pdf",
          running: false,
          duration: 0.2,
          isError: false,
          startedAt: 1,
        },
      ],
      nextSeq: 1,
    }),
    true,
    "Completed tool steps should keep the tool progress bubble visible for the turn.",
  );
  assert.equal(
    shouldDisplayAgentProgress({
      ...baseProgress,
      running: false,
      status: "done",
      steps: [
        {
          seq: 1,
          tool: "read_file",
          preview: null,
          running: false,
          duration: 0.2,
          isError: false,
          startedAt: 1,
        },
      ],
    }),
    false,
    "Finished progress should not keep an extra working bubble in the transcript.",
  );
}

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
