// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

// STUDY M4: personalized learning path panel. Mirrors ProfilePanel's
// draft/active review flow, but renders learning_plan phases as a compact
// vertical timeline so the current stage is visible at a glance.

import { Check, Clock3, RefreshCw, Route, Send, X } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { cn } from "../../lib/cn";
import { WorkspaceSection } from "../workspaceSection";
import { STUDY_LEARNING_EVENT } from "./flashcardLearningStore";
import { LEARNING_PATH_PROMPT } from "./studyPrompts";
import { pickCurrentStudyArtifact } from "./studyArtifactState";
import {
  cmdStudyArtifactActivate,
  cmdStudyArtifactReject,
  cmdStudyDrafts,
  type LearningPlanPhase,
  type LearningPlanTask,
  type StudyArtifact,
} from "./study-api";

function normalizedStatus(phase: LearningPlanPhase, index: number): "pending" | "active" | "done" {
  const raw = String(phase.status || "").toLowerCase();
  if (raw === "done" || raw === "active" || raw === "pending") return raw;
  return index === 0 ? "active" : "pending";
}

function statusLabel(status: string): string {
  if (status === "done") return "已完成";
  if (status === "active") return "进行中";
  return "待开始";
}

function orderedTasks(tasks: LearningPlanTask[] | undefined): LearningPlanTask[] {
  if (!Array.isArray(tasks)) return [];
  return [...tasks].sort((a, b) => {
    const ao = typeof a.order === "number" ? a.order : Number.MAX_SAFE_INTEGER;
    const bo = typeof b.order === "number" ? b.order : Number.MAX_SAFE_INTEGER;
    return ao - bo;
  });
}

export function LearningPathPanel({ onStartPrompt }: { onStartPrompt?: (prompt: string) => void }) {
  const [plan, setPlan] = useState<StudyArtifact | null>(null);
  const [status, setStatus] = useState("");

  const refresh = useCallback(async () => {
    try {
      const res = await cmdStudyDrafts("learning_plan");
      setPlan(pickCurrentStudyArtifact(res.drafts || []));
    } catch (error) {
      setStatus("后端暂不可用");
      console.debug("learning_plan refresh failed:", error);
    }
  }, []);

  useEffect(() => {
    void refresh();
    const onLearning = () => void refresh().catch(() => undefined);
    window.addEventListener(STUDY_LEARNING_EVENT, onLearning);
    return () => window.removeEventListener(STUDY_LEARNING_EVENT, onLearning);
  }, [refresh]);

  const phases = useMemo(
    () => (Array.isArray(plan?.payload?.phases) ? plan.payload.phases : []),
    [plan],
  );

  const activeIndex = useMemo(() => {
    const explicit = phases.findIndex((phase) => normalizedStatus(phase, 0) === "active");
    if (explicit >= 0) return explicit;
    const firstPending = phases.findIndex((phase, index) => normalizedStatus(phase, index) !== "done");
    return firstPending >= 0 ? firstPending : Math.max(0, phases.length - 1);
  }, [phases]);

  const act = async (fn: (id: string) => Promise<unknown>) => {
    if (!plan) return;
    try {
      await fn(plan.artifact_id);
      await refresh();
    } catch (error) {
      setStatus("操作失败");
      console.debug("learning_plan action failed:", error);
    }
  };

  const goals = Array.isArray(plan?.payload?.goals) ? plan.payload.goals.filter(Boolean) : [];

  return (
    <WorkspaceSection sectionId="workspace.learningPath" title="学习路径" dotColor="#2f9e8f">
      <div className="mt-2 flex items-center gap-2">
        <button
          type="button"
          onClick={() => onStartPrompt?.(LEARNING_PATH_PROMPT)}
          className="kq-quick-action inline-flex flex-1 items-center justify-center gap-1.5 rounded-[10px] px-2.5 py-2 text-[12.5px] leading-snug transition"
        >
          <Route className="h-3.5 w-3.5" aria-hidden />
          {plan ? "更新学习路径" : "构建学习路径"}
        </button>
        <button
          type="button"
          onClick={() => void refresh()}
          className="kq-soft-icon-btn inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-md transition"
          aria-label="刷新"
          title="刷新"
        >
          <RefreshCw className="h-3.5 w-3.5" aria-hidden />
        </button>
      </div>

      {plan && phases.length ? (
        <div className="mt-3">
          <div className="flex items-center justify-between gap-2">
            <span className="truncate text-[12.5px] font-medium text-[var(--kq-color-ink)]" title={plan.title}>
              {plan.title}
            </span>
            <span
              className={cn(
                "shrink-0 rounded-full px-1.5 py-px text-[10px]",
                plan.status === "active"
                  ? "bg-emerald-500/15 text-emerald-600"
                  : "bg-[var(--kq-glass-hover,rgba(0,0,0,0.04))] text-[var(--kq-color-muted)]",
              )}
            >
              {plan.status === "active" ? "已激活" : "待审核"}
            </span>
          </div>

          {goals.length ? (
            <div className="mt-1 text-[11.5px] leading-snug text-[var(--kq-color-muted)]">
              目标：{goals.join("；")}
            </div>
          ) : null}

          <div className="mt-3 grid grid-cols-1 gap-0">
            {phases.map((phase, index) => {
              const phaseStatus = normalizedStatus(phase, index);
              const isActive = index === activeIndex || phaseStatus === "active";
              const tasks = orderedTasks(phase.tasks);
              return (
                <div key={`${index}-${phase.title || "phase"}`} className="grid grid-cols-[18px_minmax(0,1fr)] gap-2">
                  <div className="flex flex-col items-center">
                    <span
                      className={cn(
                        "mt-0.5 inline-flex h-4 w-4 items-center justify-center rounded-full border",
                        phaseStatus === "done"
                          ? "border-emerald-500 bg-emerald-500 text-white"
                          : isActive
                            ? "border-[#2f9e8f] bg-[#2f9e8f] text-white"
                            : "border-[var(--kq-glass-border)] bg-[var(--kq-color-surface)] text-[var(--kq-color-muted)]",
                      )}
                    >
                      {phaseStatus === "done" ? (
                        <Check className="h-2.5 w-2.5" aria-hidden />
                      ) : (
                        <Clock3 className="h-2.5 w-2.5" aria-hidden />
                      )}
                    </span>
                    {index + 1 < phases.length ? (
                      <span className="min-h-8 w-px flex-1 bg-[var(--kq-glass-border)]" aria-hidden />
                    ) : null}
                  </div>
                  <div
                    className={cn(
                      "mb-2 min-w-0 rounded-md border px-2.5 py-2",
                      isActive
                        ? "border-[#2f9e8f]/40 bg-[#2f9e8f]/[0.06]"
                        : "border-[var(--kq-glass-border)] bg-[var(--kq-glass-bg-subtle,rgba(255,255,255,0.35))]",
                    )}
                  >
                    <div className="flex items-center gap-1.5">
                      <span className="min-w-0 flex-1 break-words text-[12.5px] font-medium text-[var(--kq-color-ink)]">
                        {phase.title || `阶段 ${index + 1}`}
                      </span>
                      <span className="shrink-0 rounded-full bg-[var(--kq-glass-hover,rgba(0,0,0,0.04))] px-1.5 py-px text-[10px] text-[var(--kq-color-muted)]">
                        {statusLabel(phaseStatus)}
                      </span>
                    </div>
                    {phase.focus ? (
                      <div className="mt-1 break-words text-[11px] text-[#2f9e8f]">聚焦：{phase.focus}</div>
                    ) : null}
                    {tasks.length ? (
                      <ol className="mt-1.5 space-y-1">
                        {tasks.map((task, taskIndex) => (
                          <li key={`${taskIndex}-${task.title || "task"}`} className="min-w-0 text-[11.5px] leading-snug">
                            <span className="text-[var(--kq-color-ink)]">
                              {task.title || `任务 ${taskIndex + 1}`}
                            </span>
                            {task.done_when ? (
                              <div className="break-words text-[var(--kq-color-muted)]">
                                完成标准：{task.done_when}
                              </div>
                            ) : null}
                          </li>
                        ))}
                      </ol>
                    ) : (
                      <p className="mt-1 text-[11.5px] text-[var(--kq-color-muted)]">暂无任务明细</p>
                    )}
                  </div>
                </div>
              );
            })}
          </div>

          {plan.status !== "active" ? (
            <div className="mt-1 flex items-center gap-2">
              <button
                type="button"
                onClick={() => void act(cmdStudyArtifactActivate)}
                className="kq-quick-action inline-flex flex-1 items-center justify-center gap-1.5 rounded-[10px] px-2.5 py-1.5 text-[12px] leading-snug transition"
              >
                <Check className="h-3.5 w-3.5" aria-hidden />
                激活为当前路径
              </button>
              <button
                type="button"
                onClick={() => void act(cmdStudyArtifactReject)}
                className="kq-soft-icon-btn inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-md transition"
                aria-label="驳回"
                title="驳回"
              >
                <X className="h-3.5 w-3.5" aria-hidden />
              </button>
            </div>
          ) : (
            <button
              type="button"
              onClick={() => onStartPrompt?.("请把当前学习路径的当前阶段任务和推荐资源，整理成今天的学习提醒内容。")}
              className="kq-quick-action mt-1 inline-flex w-full items-center justify-center gap-1.5 rounded-[10px] px-2.5 py-1.5 text-[12px] leading-snug transition"
            >
              <Send className="h-3.5 w-3.5" aria-hidden />
              推送到今日提醒
            </button>
          )}
        </div>
      ) : (
        <p className="mt-3 text-[12px] leading-relaxed text-[var(--kq-color-muted)]">
          还没有学习路径。点上面「构建学习路径」，小娜会结合画像、评估结果和课程材料，先确认目标与时间，再生成可审核激活的阶段计划。
        </p>
      )}

      {status ? <div className="mt-2 text-[11.5px] text-[var(--kq-color-muted)]">{status}</div> : null}
    </WorkspaceSection>
  );
}
