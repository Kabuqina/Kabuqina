// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useEffect, useRef, useState } from "react";
import {
  AlertCircle,
  Check,
  ChevronDown,
  ChevronUp,
  FileText,
  Folder,
  Globe,
  LoaderCircle,
  Search,
  Terminal,
  Wrench,
} from "lucide-react";
import { cn } from "../lib/cn";
import { useI18n } from "../lib/i18n";
import type { AgentProgressState, AgentStep } from "./hooks/useAgentProgress";

const TOOL_ICON_MAP: Record<string, typeof Wrench> = {
  read_file: FileText,
  write_file: FileText,
  patch: FileText,
  search_files: Search,
  web_search: Search,
  web_extract: Globe,
  browser_navigate: Globe,
  browser_click: Globe,
  browser_type: Globe,
  terminal: Terminal,
  execute_code: Terminal,
  list_directory: Folder,
};

const LONG_TASK_META: Record<string, { label: string; phase: string; estimateSeconds: number }> = {
  pptx_write: { label: "PPT 生成", phase: "正在排版并写入文件", estimateSeconds: 75 },
  manim_render: { label: "视频渲染", phase: "正在渲染讲解动画", estimateSeconds: 120 },
  video_render: { label: "视频渲染", phase: "正在生成短视频", estimateSeconds: 120 },
  render_video: { label: "视频渲染", phase: "正在生成短视频", estimateSeconds: 120 },
  xfyun_tts: { label: "语音合成", phase: "正在合成讲解音频", estimateSeconds: 45 },
};

function iconForTool(tool: string) {
  return TOOL_ICON_MAP[tool] ?? Wrench;
}

function formatDuration(seconds: number | null): string {
  if (seconds == null || !Number.isFinite(seconds)) return "";
  if (seconds < 1) return `${Math.max(1, Math.round(seconds * 1000))}ms`;
  if (seconds < 10) return `${seconds.toFixed(1)}s`;
  return `${Math.round(seconds)}s`;
}

/** One-line status label for a compact/collapsed progress header. */
export function describeProgress(progress: AgentProgressState): string {
  const { status, current_tool, error } = progress;
  if (error) return error;
  if (status === "tool" && current_tool) {
    const longTask = LONG_TASK_META[current_tool];
    return longTask ? `${longTask.label} · ${longTask.phase}…` : `running ${current_tool.replace(/_/g, " ")}…`;
  }
  if (status === "thinking") return "thinking…";
  if (status === "starting") return "starting…";
  if (status === "done") return "done";
  if (status === "interrupted") return "interrupted";
  return "computing…";
}

function runningLongTask(progress: AgentProgressState): AgentStep | null {
  const current = [...progress.steps].reverse().find((step) => step.running && LONG_TASK_META[step.tool]);
  if (current) return current;
  if (progress.current_tool && LONG_TASK_META[progress.current_tool]) {
    return progress.steps.find((step) => step.running && step.tool === progress.current_tool) || null;
  }
  return null;
}

function LongTaskProgress({ step }: { step: AgentStep }) {
  const meta = LONG_TASK_META[step.tool];
  const [now, setNow] = useState(() => Date.now() / 1000);

  useEffect(() => {
    if (!step.running) return;
    const timer = window.setInterval(() => setNow(Date.now() / 1000), 1000);
    return () => window.clearInterval(timer);
  }, [step.running]);

  if (!meta) return null;
  const elapsed = Math.max(0, now - step.startedAt);
  const percent = step.running
    ? Math.max(8, Math.min(92, Math.round((elapsed / meta.estimateSeconds) * 86) + 8))
    : 100;
  return (
    <div className="mb-2 rounded-lg border border-[var(--kq-glass-border)] bg-[var(--kq-glass-bg-subtle,rgba(255,255,255,0.35))] px-2.5 py-2">
      <div className="flex items-center justify-between gap-2 text-[12px] leading-snug">
        <span className="min-w-0 truncate font-medium text-[var(--kq-color-ink)]">
          {meta.label}
        </span>
        <span className="shrink-0 font-mono text-[11px] tabular-nums text-[var(--kq-color-muted)]">
          {step.running ? `${percent}%` : "100%"}
        </span>
      </div>
      <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-[var(--kq-hover-bg-strong)]">
        <div
          className="h-full rounded-full bg-[var(--kq-color-primary)] transition-[width]"
          style={{ width: `${percent}%` }}
        />
      </div>
      <p className="mt-1 truncate text-[11px] text-[var(--kq-color-muted)]" title={step.preview || meta.phase}>
        {meta.phase} · {formatDuration(elapsed)}
      </p>
    </div>
  );
}

function StepRow({ step }: { step: AgentStep }) {
  const Icon = iconForTool(step.tool);
  const display = step.preview && step.preview.trim() ? step.preview : "";
  const toolLabel = step.tool.replace(/_/g, " ");
  return (
    <div
      className={cn(
        "flex items-center gap-2 py-0.5 font-mono text-[12.5px] leading-snug",
        step.isError ? "text-rose-600 dark:text-rose-400" : "text-[var(--kq-color-muted)]"
      )}
    >
      <span
        className={cn(
          "inline-flex h-4 w-4 shrink-0 items-center justify-center rounded-sm",
          step.running
            ? "text-sky-500 dark:text-sky-400"
            : step.isError
              ? "text-rose-500 dark:text-rose-400"
              : "text-emerald-500 dark:text-emerald-400"
        )}
        aria-hidden
      >
        {step.running ? (
          <LoaderCircle className="h-3.5 w-3.5 animate-spin" strokeWidth={2.5} />
        ) : step.isError ? (
          <AlertCircle className="h-3.5 w-3.5" strokeWidth={2.5} />
        ) : (
          <Check className="h-3.5 w-3.5" strokeWidth={3} />
        )}
      </span>
      <Icon className="h-3.5 w-3.5 shrink-0 text-[var(--kq-color-muted)]" aria-hidden />
      <span className="shrink-0 font-semibold text-[var(--kq-color-ink)]">{toolLabel}</span>
      {display && (
        <span className="min-w-0 flex-1 truncate text-[var(--kq-color-muted)]" title={display}>
          {display}
        </span>
      )}
      <span className="ml-auto shrink-0 tabular-nums text-[var(--kq-color-muted)]">
        {step.running ? "…" : formatDuration(step.duration)}
      </span>
    </div>
  );
}

const MOOD_FRAMES = ["(◕‿◕)", "(¬‿¬)", "(¬_¬)", "(•‿•)"];

function StatusRow({ progress }: { progress: AgentProgressState }) {
  const { status, current_tool, iteration, max_iterations, error } = progress;
  const frame = MOOD_FRAMES[Math.floor(Date.now() / 700) % MOOD_FRAMES.length];

  let label = "computing…";
  if (error) {
    label = error;
  } else if (status === "tool" && current_tool) {
    label = `running ${current_tool.replace(/_/g, " ")}…`;
  } else if (status === "thinking") {
    label = "thinking…";
  } else if (status === "starting") {
    label = "starting…";
  } else if (status === "done") {
    label = "done";
  } else if (status === "interrupted") {
    label = "interrupted";
  }

  return (
    <div className="mt-1.5 flex items-center gap-2 border-t border-[var(--kq-glass-border)] pt-1.5 font-mono text-[12.5px] text-[var(--kq-color-muted)]">
      <span aria-hidden className="select-none text-amber-500/90 dark:text-amber-400/90">
        {frame}
      </span>
      <span className="italic">{label}</span>
      {iteration > 0 && max_iterations > 0 && (
        <span className="ml-auto shrink-0 tabular-nums text-[var(--kq-color-muted)]">
          {iteration}/{max_iterations}
        </span>
      )}
    </div>
  );
}

const AUTO_COLLAPSE_THRESHOLD = 10;

export function AgentProgress({
  progress,
  embedded = false,
}: {
  progress: AgentProgressState | null;
  embedded?: boolean;
}) {
  const { t } = useI18n();
  const [collapsed, setCollapsed] = useState(false);
  const autoCollapsedRef = useRef(false);

  useEffect(() => {
    if (!progress) return;
    const stepCount = progress.steps.length;
    if (stepCount === 0) {
      autoCollapsedRef.current = false;
    }
    if (stepCount > AUTO_COLLAPSE_THRESHOLD && !autoCollapsedRef.current && !collapsed) {
      autoCollapsedRef.current = true;
      setCollapsed(true);
    }
  }, [progress, collapsed]);

  if (!progress || (!progress.running && progress.steps.length === 0)) {
    return null;
  }

  // Embedded: no outer bubble/self-collapse — the host (ChatMessage 过程 区)
  // owns the fold. Just render the step list + live status row.
  if (embedded) {
    const longTask = runningLongTask(progress);
    return (
      <div className="space-y-0.5" role="status" aria-label="agent progress">
        {longTask ? <LongTaskProgress step={longTask} /> : null}
        {progress.steps.map((s) => (
          <StepRow key={s.seq} step={s} />
        ))}
        {progress.running && <StatusRow progress={progress} />}
      </div>
    );
  }

  const currentTool = progress.current_tool?.replace(/_/g, " ");
  if (collapsed) {
    return (
      <button
        type="button"
        className={cn(
          "inline-flex max-w-full items-center gap-2 rounded-2xl rounded-tl-sm border border-[var(--kq-glass-border)] bg-[var(--kq-glass-bg)] px-3 py-2 text-left shadow-sm transition",
          "hover:bg-[var(--kq-hover-bg-strong)]"
        )}
        onClick={() => setCollapsed(false)}
        aria-label={t("chat.expand")}
      >
        <span aria-hidden className="text-base">
          ✨
        </span>
        <span className="min-w-0 truncate text-sm font-medium text-[var(--kq-color-ink)]">
          {t("chat.streamingWorking")}
          {currentTool ? ` · ${currentTool}` : ""}
        </span>
        {progress.steps.length > 0 && (
          <span className="shrink-0 rounded-full bg-[var(--kq-hover-bg)] px-1.5 py-0.5 font-mono text-[11px] text-[var(--kq-color-muted)]">
            {progress.steps.length}
          </span>
        )}
        <ChevronDown className="h-4 w-4 shrink-0 text-[var(--kq-color-muted)]" strokeWidth={2.25} />
      </button>
    );
  }

  return (
    <div
      className={cn(
        "relative w-fit max-w-full rounded-2xl rounded-tl-sm border border-[var(--kq-glass-border)] bg-[var(--kq-glass-bg)] px-3 py-2 shadow-sm backdrop-blur-[14px]"
      )}
      role="status"
      aria-label="Agent progress"
    >
      <button
        type="button"
        className="absolute -right-1.5 -top-1.5 inline-flex h-6 w-6 items-center justify-center rounded-md bg-[var(--kq-color-surface)] text-[var(--kq-color-muted)] shadow-sm ring-1 ring-[var(--kq-glass-border)] transition hover:bg-[var(--kq-hover-bg)] hover:text-[var(--kq-color-strong)]"
        onClick={() => setCollapsed(true)}
        aria-label={t("chat.collapse")}
        title={t("chat.collapse")}
      >
        <ChevronUp className="h-3.5 w-3.5" strokeWidth={2.5} />
      </button>
      <div className="space-y-0.5">
        {runningLongTask(progress) ? <LongTaskProgress step={runningLongTask(progress)!} /> : null}
        {progress.steps.map((s) => (
          <StepRow key={s.seq} step={s} />
        ))}
      </div>
      {progress.running && <StatusRow progress={progress} />}
    </div>
  );
}
