// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useState } from "react";
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

function iconForTool(tool: string) {
  return TOOL_ICON_MAP[tool] ?? Wrench;
}

function formatDuration(seconds: number | null): string {
  if (seconds == null || !Number.isFinite(seconds)) return "";
  if (seconds < 1) return `${Math.max(1, Math.round(seconds * 1000))}ms`;
  if (seconds < 10) return `${seconds.toFixed(1)}s`;
  return `${Math.round(seconds)}s`;
}

function StepRow({ step }: { step: AgentStep }) {
  const Icon = iconForTool(step.tool);
  const display = step.preview && step.preview.trim() ? step.preview : "";
  const toolLabel = step.tool.replace(/_/g, " ");
  return (
    <div
      className={cn(
        "flex items-center gap-2 py-0.5 font-mono text-[12.5px] leading-snug",
        step.isError ? "text-rose-600 dark:text-rose-400" : "text-zinc-600 dark:text-zinc-400"
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
      <Icon className="h-3.5 w-3.5 shrink-0 text-zinc-400 dark:text-zinc-500" aria-hidden />
      <span className="shrink-0 font-semibold text-zinc-700 dark:text-zinc-300">{toolLabel}</span>
      {display && (
        <span className="min-w-0 flex-1 truncate text-zinc-500 dark:text-zinc-500" title={display}>
          {display}
        </span>
      )}
      <span className="ml-auto shrink-0 tabular-nums text-zinc-400 dark:text-zinc-500">
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
    <div className="mt-1.5 flex items-center gap-2 border-t border-zinc-200/70 pt-1.5 font-mono text-[12.5px] text-zinc-500 dark:border-zinc-700/60 dark:text-zinc-500">
      <span aria-hidden className="select-none text-amber-500/90 dark:text-amber-400/90">
        {frame}
      </span>
      <span className="italic">{label}</span>
      {iteration > 0 && max_iterations > 0 && (
        <span className="ml-auto shrink-0 tabular-nums text-zinc-400 dark:text-zinc-500">
          {iteration}/{max_iterations}
        </span>
      )}
    </div>
  );
}

export function AgentProgress({ progress }: { progress: AgentProgressState | null }) {
  const { t } = useI18n();
  const [collapsed, setCollapsed] = useState(false);

  if (!progress || (!progress.running && progress.steps.length === 0)) {
    return null;
  }

  const currentTool = progress.current_tool?.replace(/_/g, " ");
  if (collapsed) {
    return (
      <button
        type="button"
        className={cn(
          "inline-flex max-w-full items-center gap-2 rounded-2xl rounded-tl-sm border border-zinc-200/80 bg-white/85 px-3 py-2 text-left shadow-sm transition",
          "hover:border-violet-200 hover:bg-white dark:border-zinc-700/70 dark:bg-zinc-900/70 dark:hover:border-zinc-600"
        )}
        onClick={() => setCollapsed(false)}
        aria-label={t("chat.expand")}
      >
        <span aria-hidden className="text-base">
          ✨
        </span>
        <span className="min-w-0 truncate text-sm font-medium text-zinc-600 dark:text-zinc-300">
          {t("chat.streamingWorking")}
          {currentTool ? ` · ${currentTool}` : ""}
        </span>
        {progress.steps.length > 0 && (
          <span className="shrink-0 rounded-full bg-zinc-100 px-1.5 py-0.5 font-mono text-[11px] text-zinc-500 dark:bg-zinc-800 dark:text-zinc-400">
            {progress.steps.length}
          </span>
        )}
        <ChevronDown className="h-4 w-4 shrink-0 text-zinc-400" strokeWidth={2.25} />
      </button>
    );
  }

  return (
    <div
      className={cn(
        "relative w-fit max-w-full rounded-2xl rounded-tl-sm border border-zinc-200/80 bg-white/85 px-3 py-2 shadow-sm",
        "dark:border-zinc-700/70 dark:bg-zinc-900/70"
      )}
      role="status"
      aria-label="Agent progress"
    >
      <button
        type="button"
        className="absolute -right-1.5 -top-1.5 inline-flex h-6 w-6 items-center justify-center rounded-md bg-white/90 text-zinc-400 shadow-sm ring-1 ring-zinc-200/80 transition hover:bg-zinc-50 hover:text-zinc-700 dark:bg-zinc-900/90 dark:ring-zinc-700 dark:hover:bg-zinc-800 dark:hover:text-zinc-200"
        onClick={() => setCollapsed(true)}
        aria-label={t("chat.collapse")}
        title={t("chat.collapse")}
      >
        <ChevronUp className="h-3.5 w-3.5" strokeWidth={2.5} />
      </button>
      <div className="space-y-0.5">
        {progress.steps.map((s) => (
          <StepRow key={s.seq} step={s} />
        ))}
      </div>
      {progress.running && <StatusRow progress={progress} />}
    </div>
  );
}
