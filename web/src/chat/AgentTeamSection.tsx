// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

// 编队协同面板 — live visualization of 小娜's backstage multi-agent team.
// Subscribes to AGENT_TEAM_EVENT (re-dispatched from the chat SSE by
// useSendMessage) and folds frames with the pure applyAgentStateEvent reducer.
// This is the student-/judge-facing proof that a multi-agent DAG really ran.

import { useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  BookOpen,
  CheckCircle2,
  Circle,
  ListChecks,
  Loader2,
  ShieldCheck,
  Sparkles,
  UserSearch,
  type LucideIcon,
} from "lucide-react";
import { cn } from "../lib/cn";
import {
  AGENT_TEAM_EVENT,
  applyAgentStateEvent,
  type AgentStatus,
  type RoleView,
  type TeamRun,
} from "./study/agentTeamStore";

const ROLE_ICON: Record<string, LucideIcon> = {
  profiler: UserSearch,
  lecturer: BookOpen,
  quizmaster: ListChecks,
  guardian: ShieldCheck,
};

const STATUS_TEXT: Record<AgentStatus, string> = {
  waiting: "等待中",
  working: "工作中",
  produced: "已产出",
  passed: "已把关",
  flagged: "待复核",
  failed: "失败",
  skipped: "跳过",
};

function StatusIcon({ status }: { status: AgentStatus }) {
  const base = "h-4 w-4 shrink-0";
  switch (status) {
    case "working":
      return <Loader2 className={cn(base, "animate-spin text-[var(--kq-color-accent,#4466cc)]")} aria-hidden />;
    case "produced":
      return <CheckCircle2 className={cn(base, "text-emerald-500")} aria-hidden />;
    case "passed":
      return <ShieldCheck className={cn(base, "text-emerald-500")} aria-hidden />;
    case "flagged":
      return <AlertTriangle className={cn(base, "text-amber-500")} aria-hidden />;
    case "failed":
      return <AlertTriangle className={cn(base, "text-red-500")} aria-hidden />;
    default:
      return <Circle className={cn(base, "text-[var(--kq-color-muted,#98a2b3)]")} aria-hidden />;
  }
}

function RoleCard({ role, index, total }: { role: RoleView; index: number; total: number }) {
  const RoleGlyph = ROLE_ICON[role.roleId] ?? Sparkles;
  const active = role.status === "working";
  return (
    <li className="relative pl-6">
      {/* pipeline connector */}
      {index < total - 1 ? (
        <span
          className="absolute left-[9px] top-6 h-[calc(100%-4px)] w-px bg-[var(--kq-glass-border,#e5e7eb)]"
          aria-hidden
        />
      ) : null}
      <span className="absolute left-0 top-1.5"><StatusIcon status={role.status} /></span>
      <div
        className={cn(
          "kq-workspace-body rounded-lg border px-2.5 py-2 transition",
          active
            ? "border-[var(--kq-color-accent,#4466cc)] bg-[var(--kq-glass-hover,rgba(68,102,204,0.06))]"
            : "border-[var(--kq-glass-border,#e5e7eb)]",
        )}
      >
        <div className="flex items-center gap-1.5">
          <RoleGlyph className="h-3.5 w-3.5 shrink-0 text-[var(--kq-color-muted,#98a2b3)]" aria-hidden />
          <span className="text-[13px] font-medium">{role.display}</span>
          {role.isGate ? (
            <span className="rounded-full bg-[var(--kq-glass-hover,rgba(0,0,0,0.04))] px-1.5 py-px text-[10px] text-[var(--kq-color-muted,#98a2b3)]">
              门禁
            </span>
          ) : null}
          <span className="ml-auto text-[11px] text-[var(--kq-color-muted,#98a2b3)]">
            {STATUS_TEXT[role.status]}
          </span>
        </div>
        {role.blurb ? (
          <p className="mt-0.5 text-[11px] leading-snug text-[var(--kq-color-muted,#98a2b3)]">{role.blurb}</p>
        ) : null}
        {active && role.currentTool ? (
          <p className="mt-1 truncate text-[11px] text-[var(--kq-color-accent,#4466cc)]" title={role.currentTool}>
            调用 {role.currentTool}
          </p>
        ) : null}
        {role.produced.length > 0 ? (
          <div className="mt-1.5 flex flex-wrap gap-1">
            {role.produced.map((a, i) => (
              <span
                key={a.artifact_id ?? `${role.roleId}-${i}`}
                className="kq-material-chip max-w-full truncate text-[11px]"
                title={`${a.kind ?? ""} · ${a.title ?? ""}`}
              >
                {a.title || a.kind || "草稿"}
              </span>
            ))}
          </div>
        ) : null}
        {role.error ? (
          <p className="mt-1 text-[11px] text-red-500" title={role.error}>
            {role.error}
          </p>
        ) : null}
      </div>
    </li>
  );
}

export function AgentTeamSection() {
  const [run, setRun] = useState<TeamRun | null>(null);

  useEffect(() => {
    const onEvt = (e: Event) => {
      const detail = (e as CustomEvent).detail;
      if (!detail) return;
      setRun((prev) => applyAgentStateEvent(prev, detail));
    };
    window.addEventListener(AGENT_TEAM_EVENT, onEvt as EventListener);
    return () => window.removeEventListener(AGENT_TEAM_EVENT, onEvt as EventListener);
  }, []);

  const roles = useMemo(
    () => (run ? run.order.map((id) => run.roles[id]).filter(Boolean) : []),
    [run],
  );

  const running = run != null && !run.done;

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <Sparkles className="h-4 w-4 text-[var(--kq-color-accent,#4466cc)]" aria-hidden />
        <span className="text-[13px] font-semibold">小娜的学习编队</span>
        {run ? (
          <span
            className={cn(
              "ml-auto inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px]",
              running
                ? "kq-workspace-active"
                : "bg-[var(--kq-glass-hover,rgba(0,0,0,0.04))] text-[var(--kq-color-muted,#98a2b3)]",
            )}
          >
            {running ? <Loader2 className="h-3 w-3 animate-spin" aria-hidden /> : null}
            {running ? "协同中" : run.ok === false ? "已完成（有告警）" : "已完成"}
          </span>
        ) : null}
      </div>

      {!run ? (
        <p className="kq-workspace-body text-[12px] leading-relaxed text-[var(--kq-color-muted,#98a2b3)]">
          让小娜召集编队即可在这里实时看到多个角色智能体（画像师 / 讲解官 / 出题官 / 守门人）协同工作的过程。
          <br />
          试试对小娜说：“用你的学习编队，把某一章做成复习资料和练习。”
        </p>
      ) : (
        <>
          <ul className="space-y-2">
            {roles.map((role, i) => (
              <RoleCard key={role.roleId} role={role} index={i} total={roles.length} />
            ))}
          </ul>
          <p className="text-[11px] text-[var(--kq-color-muted,#98a2b3)]">
            共 {run.draftsTotal} 份草稿已进入草稿箱，请在 STUDY 审核后自行激活。
          </p>
        </>
      )}
    </div>
  );
}
