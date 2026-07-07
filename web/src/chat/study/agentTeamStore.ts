// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

// In-memory reducer for the study-team (小娜编队) live visualization. The
// backend streams `agent_state` frames on the chat SSE; useSendMessage
// re-dispatches them as an AGENT_TEAM_EVENT CustomEvent (decoupled, like
// STUDY_LEARNING_EVENT). AgentTeamSection folds them with applyAgentStateEvent.
//
// State is ephemeral (per chat turn) — deliberately NOT persisted to
// localStorage; a new team_started run replaces the previous one.

export const AGENT_TEAM_EVENT = "kabuqina-agent-team";

export type AgentStatus =
  | "waiting"
  | "working"
  | "produced"
  | "passed"
  | "flagged"
  | "failed"
  | "skipped";

export type TeamArtifact = { artifact_id?: string; kind?: string; title?: string };

export type RoleView = {
  roleId: string;
  display: string;
  blurb: string;
  isGate: boolean;
  status: AgentStatus;
  currentTool: string | null;
  produced: TeamArtifact[];
  dropped: TeamArtifact[];
  summary: string;
  error: string | null;
};

export type TeamRun = {
  runId: string;
  sessionId: string;
  order: string[]; // role ids in DAG layer order
  layers: string[][];
  edges: [string, string][];
  roles: Record<string, RoleView>;
  done: boolean;
  draftsTotal: number;
  startedAt: number;
  ok: boolean | null;
};

// A minimal shape of the `agent_state` stream event (see chat-api.ts).
export type AgentStateEvent = {
  type?: string;
  phase?: string;
  run_id?: string;
  session_id?: string;
  role_id?: string;
  display?: string;
  blurb?: string;
  is_gate?: boolean;
  status?: string;
  current_tool?: string | null;
  produced?: TeamArtifact[];
  dropped?: TeamArtifact[];
  summary?: string | null;
  error?: string | null;
  dag?: {
    nodes?: { role_id: string; display?: string; blurb?: string; is_gate?: boolean }[];
    edges?: [string, string][];
    layers?: string[][];
  };
  report?: { ok?: boolean; drafts_total?: number } & Record<string, unknown>;
};

function coerceStatus(value: unknown): AgentStatus {
  const s = String(value || "");
  const allowed: AgentStatus[] = [
    "waiting", "working", "produced", "passed", "flagged", "failed", "skipped",
  ];
  return (allowed as string[]).includes(s) ? (s as AgentStatus) : "waiting";
}

function initRunFromDag(evt: AgentStateEvent): TeamRun {
  const nodes = evt.dag?.nodes ?? [];
  const layers = evt.dag?.layers ?? nodes.map((n) => [n.role_id]);
  const roles: Record<string, RoleView> = {};
  for (const n of nodes) {
    roles[n.role_id] = {
      roleId: n.role_id,
      display: n.display || n.role_id,
      blurb: n.blurb || "",
      isGate: Boolean(n.is_gate),
      status: "waiting",
      currentTool: null,
      produced: [],
      dropped: [],
      summary: "",
      error: null,
    };
  }
  const order = layers.flat().filter((id) => roles[id]);
  return {
    runId: evt.run_id || "",
    sessionId: evt.session_id || "",
    order,
    layers,
    edges: evt.dag?.edges ?? [],
    roles,
    done: false,
    draftsTotal: 0,
    startedAt: Date.now(),
    ok: null,
  };
}

/** Pure reducer: fold one agent_state event into the current run. */
export function applyAgentStateEvent(
  prev: TeamRun | null,
  evt: AgentStateEvent
): TeamRun | null {
  if (!evt || evt.type !== "agent_state") return prev;

  if (evt.phase === "team_started") {
    return initRunFromDag(evt);
  }

  // Ignore stray role/done frames from a different run than the active one.
  if (!prev) return prev;
  if (evt.run_id && prev.runId && evt.run_id !== prev.runId) return prev;

  if (evt.phase === "role" && evt.role_id) {
    const existing = prev.roles[evt.role_id];
    const base: RoleView =
      existing ?? {
        roleId: evt.role_id,
        display: evt.display || evt.role_id,
        blurb: "",
        isGate: Boolean(evt.is_gate),
        status: "waiting",
        currentTool: null,
        produced: [],
        dropped: [],
        summary: "",
        error: null,
      };
    const updated: RoleView = {
      ...base,
      display: evt.display || base.display,
      isGate: evt.is_gate ?? base.isGate,
      status: coerceStatus(evt.status),
      currentTool: evt.current_tool ?? null,
      produced: evt.produced && evt.produced.length ? evt.produced : base.produced,
      dropped: evt.dropped && evt.dropped.length ? evt.dropped : base.dropped,
      summary: (evt.summary ?? base.summary) || "",
      error: evt.error ?? base.error,
    };
    const roles = { ...prev.roles, [evt.role_id]: updated };
    const draftsTotal = Object.values(roles).reduce((n, r) => n + r.produced.length, 0);
    const order = prev.order.includes(evt.role_id)
      ? prev.order
      : [...prev.order, evt.role_id];
    return { ...prev, roles, order, draftsTotal };
  }

  if (evt.phase === "team_done") {
    return {
      ...prev,
      done: true,
      ok: typeof evt.report?.ok === "boolean" ? evt.report.ok : prev.ok,
      draftsTotal:
        typeof evt.report?.drafts_total === "number"
          ? evt.report.drafts_total
          : prev.draftsTotal,
    };
  }

  return prev;
}
