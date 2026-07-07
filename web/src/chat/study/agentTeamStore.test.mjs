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

const { applyAgentStateEvent, AGENT_TEAM_EVENT } = await importTs("./agentTeamStore.ts");

function teamStarted() {
  return {
    type: "agent_state",
    phase: "team_started",
    run_id: "run-1",
    session_id: "s1",
    dag: {
      nodes: [
        { role_id: "profiler", display: "小娜·画像", is_gate: false },
        { role_id: "lecturer", display: "小娜·讲解", is_gate: false },
        { role_id: "guardian", display: "小娜·把关", is_gate: true },
      ],
      edges: [["profiler", "lecturer"], ["lecturer", "guardian"], ["profiler", "guardian"]],
      layers: [["profiler"], ["lecturer"], ["guardian"]],
    },
  };
}

// 1. team_started builds the run with waiting roles in layer order.
{
  const run = applyAgentStateEvent(null, teamStarted());
  assert.equal(run.runId, "run-1");
  assert.deepEqual(run.order, ["profiler", "lecturer", "guardian"]);
  assert.equal(run.roles.profiler.status, "waiting");
  assert.equal(run.roles.guardian.isGate, true);
  assert.equal(run.done, false);
}

// 2. role frames update status + accumulate produced drafts.
{
  let run = applyAgentStateEvent(null, teamStarted());
  run = applyAgentStateEvent(run, {
    type: "agent_state", phase: "role", run_id: "run-1",
    role_id: "profiler", status: "working", current_tool: "learning_draft_create",
  });
  assert.equal(run.roles.profiler.status, "working");
  assert.equal(run.roles.profiler.currentTool, "learning_draft_create");

  run = applyAgentStateEvent(run, {
    type: "agent_state", phase: "role", run_id: "run-1",
    role_id: "profiler", status: "produced",
    produced: [{ artifact_id: "a1", kind: "student_state", title: "画像" }],
    summary: "6维画像已建",
  });
  assert.equal(run.roles.profiler.status, "produced");
  assert.equal(run.roles.profiler.produced.length, 1);
  assert.equal(run.draftsTotal, 1);
  assert.equal(run.roles.profiler.summary, "6维画像已建");
}

// 3. team_done marks completion and carries report totals.
{
  let run = applyAgentStateEvent(null, teamStarted());
  run = applyAgentStateEvent(run, {
    type: "agent_state", phase: "team_done", run_id: "run-1",
    report: { ok: true, drafts_total: 3 },
  });
  assert.equal(run.done, true);
  assert.equal(run.ok, true);
  assert.equal(run.draftsTotal, 3);
}

// 4. frames from a different run_id are ignored (don't corrupt active run).
{
  let run = applyAgentStateEvent(null, teamStarted());
  const before = run;
  run = applyAgentStateEvent(run, {
    type: "agent_state", phase: "role", run_id: "OTHER",
    role_id: "profiler", status: "failed",
  });
  assert.equal(run.roles.profiler.status, before.roles.profiler.status);
}

// 5. a new team_started replaces the previous run.
{
  let run = applyAgentStateEvent(null, teamStarted());
  const next = { ...teamStarted(), run_id: "run-2" };
  run = applyAgentStateEvent(run, next);
  assert.equal(run.runId, "run-2");
  assert.equal(run.draftsTotal, 0);
}

// 6. non agent_state events pass through untouched.
{
  const run = applyAgentStateEvent(null, teamStarted());
  const same = applyAgentStateEvent(run, { type: "delta", text: "hi" });
  assert.equal(same, run);
}

assert.equal(AGENT_TEAM_EVENT, "kabuqina-agent-team");

console.log("agentTeamStore.test.mjs: all assertions passed");
