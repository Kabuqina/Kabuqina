// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

// STUDY M6: learning-effect evaluation panel. Keeps evaluation artifacts
// reviewable like profile/path, then lets weak points flow back into the
// persistent study context for the next quiz or path adjustment.

import { Check, ClipboardCheck, RefreshCw, RotateCcw, X } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { cn } from "../../lib/cn";
import { WorkspaceSection } from "../workspaceSection";
import { STUDY_LEARNING_EVENT } from "./flashcardLearningStore";
import { LEARNING_EVALUATION_PROMPT, LEARNING_PATH_PROMPT } from "./studyPrompts";
import {
  STUDY_CONTEXT_FIELD_LIMIT,
  loadStudyContext,
  saveStudyContext,
} from "./studyStore";
import {
  cmdStudyArtifactActivate,
  cmdStudyArtifactReject,
  cmdStudyDrafts,
  type StudyArtifact,
} from "./study-api";

function pickCurrent(items: StudyArtifact[]): StudyArtifact | null {
  if (!Array.isArray(items) || items.length === 0) return null;
  const byRecent = [...items].sort((a, b) =>
    String(b.updated_at || "").localeCompare(String(a.updated_at || "")),
  );
  return byRecent.find((a) => a.status === "active") || byRecent[0];
}

function asText(value: unknown): string {
  if (typeof value === "string") return value.trim();
  if (value && typeof value === "object") {
    const obj = value as Record<string, unknown>;
    const parts = [
      obj.point || obj.title || obj.topic,
      obj.evidence ? `证据：${obj.evidence}` : "",
      obj.result ? `结果：${obj.result}` : "",
      obj.note || obj.summary || obj.reason,
    ].filter(Boolean);
    if (parts.length) return parts.map(String).join("；");
  }
  return value == null ? "" : String(value);
}

function stringList(values: unknown[] | undefined): string[] {
  if (!Array.isArray(values)) return [];
  return values.map(asText).filter(Boolean);
}

export function EvaluationPanel({ onStartPrompt }: { onStartPrompt?: (prompt: string) => void }) {
  const [evaluation, setEvaluation] = useState<StudyArtifact | null>(null);
  const [status, setStatus] = useState("");

  const refresh = useCallback(async () => {
    try {
      const res = await cmdStudyDrafts("evaluation");
      setEvaluation(pickCurrent(res.drafts || []));
    } catch (error) {
      setStatus("后端暂不可用");
      console.debug("evaluation refresh failed:", error);
    }
  }, []);

  useEffect(() => {
    void refresh();
    const onLearning = () => void refresh().catch(() => undefined);
    window.addEventListener(STUDY_LEARNING_EVENT, onLearning);
    return () => window.removeEventListener(STUDY_LEARNING_EVENT, onLearning);
  }, [refresh]);

  const observations = useMemo(
    () => stringList(evaluation?.payload?.observations),
    [evaluation],
  );
  const weakPoints = useMemo(
    () => (Array.isArray(evaluation?.payload?.weak_points) ? evaluation.payload.weak_points.filter(Boolean) : []),
    [evaluation],
  );
  const suggestions = useMemo(
    () => (Array.isArray(evaluation?.payload?.suggestions) ? evaluation.payload.suggestions.filter(Boolean) : []),
    [evaluation],
  );

  const act = async (fn: (id: string) => Promise<unknown>) => {
    if (!evaluation) return;
    try {
      await fn(evaluation.artifact_id);
      await refresh();
    } catch (error) {
      setStatus("操作失败");
      console.debug("evaluation action failed:", error);
    }
  };

  const applyToContext = () => {
    if (!evaluation) return;
    const context = loadStudyContext();
    const stamp = new Date().toISOString().slice(0, 10);
    const summaryParts = [
      observations.length ? `观察：${observations.slice(0, 3).join("；")}` : "",
      weakPoints.length ? `薄弱点：${weakPoints.join("、")}` : "",
      suggestions.length ? `建议：${suggestions.slice(0, 3).join("；")}` : "",
    ].filter(Boolean);
    const evaluationSummary = [`【${stamp}】${summaryParts.join("；")}`, context.evaluationSummary]
      .filter(Boolean)
      .join("\n")
      .slice(0, STUDY_CONTEXT_FIELD_LIMIT);
    const nextAdjustment = suggestions.length
      ? [`基于最近评估，优先处理：${suggestions.slice(0, 2).join("；")}`, context.nextAdjustment]
          .filter(Boolean)
          .join("\n")
          .slice(0, STUDY_CONTEXT_FIELD_LIMIT)
      : context.nextAdjustment;
    const weak = weakPoints.length
      ? [weakPoints.join("、"), context.weakPoints].filter(Boolean).join("；")
      : context.weakPoints;
    const result = saveStudyContext({
      ...context,
      evaluationSummary,
      weakPoints: weak.slice(0, STUDY_CONTEXT_FIELD_LIMIT),
      nextAdjustment,
    });
    setStatus(result.succeeded ? "已写回学习档案，可据此重规划路径" : "写回失败");
  };

  const replanFromEvaluation = () => {
    const prompt = [
      "请基于最近一次学习效果评估，更新我的学习路径。",
      weakPoints.length ? `薄弱点：${weakPoints.join("、")}` : "",
      suggestions.length ? `建议：${suggestions.join("；")}` : "",
      "请只调整未完成阶段，保留已完成阶段，并说明重排依据。",
      LEARNING_PATH_PROMPT,
    ].filter(Boolean).join("\n\n");
    onStartPrompt?.(prompt);
  };

  const hasPayload = observations.length || weakPoints.length || suggestions.length;

  return (
    <WorkspaceSection sectionId="workspace.evaluation" title="学习评估闭环" dotColor="#c2410c">
      <div className="mt-2 flex items-center gap-2">
        <button
          type="button"
          onClick={() => onStartPrompt?.(LEARNING_EVALUATION_PROMPT)}
          className="kq-quick-action inline-flex flex-1 items-center justify-center gap-1.5 rounded-[10px] px-2.5 py-2 text-[12.5px] leading-snug transition"
        >
          <ClipboardCheck className="h-3.5 w-3.5" aria-hidden />
          {evaluation ? "更新学习评估" : "开始学习评估"}
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

      {evaluation && hasPayload ? (
        <div className="mt-3">
          <div className="flex items-center justify-between gap-2">
            <span className="truncate text-[12.5px] font-medium text-[var(--kq-color-ink)]" title={evaluation.title}>
              {evaluation.title}
            </span>
            <span
              className={cn(
                "shrink-0 rounded-full px-1.5 py-px text-[10px]",
                evaluation.status === "active"
                  ? "bg-emerald-500/15 text-emerald-600"
                  : "bg-[var(--kq-glass-hover,rgba(0,0,0,0.04))] text-[var(--kq-color-muted)]",
              )}
            >
              {evaluation.status === "active" ? "已激活" : "待审核"}
            </span>
          </div>

          {observations.length ? (
            <PanelList title="观察证据" items={observations} tone="ink" />
          ) : null}
          {weakPoints.length ? (
            <div className="mt-2">
              <div className="text-[12px] font-medium text-[var(--kq-color-ink)]">薄弱点</div>
              <div className="mt-1 flex flex-wrap gap-1">
                {weakPoints.map((point) => (
                  <span
                    key={point}
                    className="rounded-full bg-orange-500/10 px-2 py-0.5 text-[11px] text-orange-700 dark:text-orange-300"
                  >
                    {point}
                  </span>
                ))}
              </div>
            </div>
          ) : null}
          {suggestions.length ? (
            <PanelList title="下一步建议" items={suggestions} tone="muted" />
          ) : null}

          {evaluation.status !== "active" ? (
            <div className="mt-2 flex items-center gap-2">
              <button
                type="button"
                onClick={() => void act(cmdStudyArtifactActivate)}
                className="kq-quick-action inline-flex flex-1 items-center justify-center gap-1.5 rounded-[10px] px-2.5 py-1.5 text-[12px] leading-snug transition"
              >
                <Check className="h-3.5 w-3.5" aria-hidden />
                激活为当前评估
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
            <div className="mt-2 grid grid-cols-1 gap-1.5">
              <button
                type="button"
                onClick={applyToContext}
                className="kq-quick-action inline-flex items-center justify-center gap-1.5 rounded-[10px] px-2.5 py-1.5 text-[12px] leading-snug transition"
              >
                <Check className="h-3.5 w-3.5" aria-hidden />
                应用到画像/路径
              </button>
              <button
                type="button"
                onClick={replanFromEvaluation}
                className="kq-quick-action inline-flex items-center justify-center gap-1.5 rounded-[10px] px-2.5 py-1.5 text-[12px] leading-snug transition"
              >
                <RotateCcw className="h-3.5 w-3.5" aria-hidden />
                按评估重规划
              </button>
            </div>
          )}
        </div>
      ) : (
        <p className="mt-3 text-[12px] leading-relaxed text-[var(--kq-color-muted)]">
          还没有学习评估。点上面「开始学习评估」，小娜会一题一题收集证据，生成可审核的观察、薄弱点和下一步建议。
        </p>
      )}

      {status ? <div className="mt-2 text-[11.5px] text-[var(--kq-color-muted)]">{status}</div> : null}
    </WorkspaceSection>
  );
}

function PanelList({
  items,
  title,
  tone,
}: {
  items: string[];
  title: string;
  tone: "ink" | "muted";
}) {
  return (
    <div className="mt-2">
      <div className="text-[12px] font-medium text-[var(--kq-color-ink)]">{title}</div>
      <ul className="mt-1 space-y-1">
        {items.map((item, index) => (
          <li
            key={`${index}-${item}`}
            className={cn(
              "break-words rounded-md border border-[var(--kq-glass-border)] px-2 py-1 text-[11.5px] leading-snug",
              tone === "ink" ? "text-[var(--kq-color-ink)]" : "text-[var(--kq-color-muted)]",
            )}
          >
            {item}
          </li>
        ))}
      </ul>
    </div>
  );
}
