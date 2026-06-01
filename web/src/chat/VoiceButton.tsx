// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { Loader2, Mic } from "lucide-react";
import { cn } from "../lib/cn";
import { useI18n } from "../lib/i18n";
import type { RecorderState } from "./hooks/useVoiceRecorder";

interface VoiceButtonProps {
  state: RecorderState;
  durationMs: number;
  disabled?: boolean;
  onPress: () => void;
}

function formatDuration(ms: number): string {
  const s = Math.floor(ms / 1000);
  const m = Math.floor(s / 60);
  return `${m}:${String(s % 60).padStart(2, "0")}`;
}

export function VoiceButton({ state, durationMs, disabled, onPress }: VoiceButtonProps) {
  const { t } = useI18n();

  const label =
    state === "idle"
      ? t("chat.voiceRecord")
      : state === "recording"
      ? t("chat.voiceRecording")
      : state === "downloading-model"
      ? t("chat.voiceModelDownloading")
      : t("chat.voiceProcessing");

  return (
    <button
      type="button"
      disabled={disabled || state === "processing" || state === "downloading-model"}
      onClick={onPress}
      className={cn(
        "group relative flex h-9 items-center justify-center rounded-lg transition",
        "text-zinc-500 hover:bg-zinc-100 active:scale-[0.98]",
        "dark:text-zinc-400 dark:hover:bg-zinc-700/80",
        "disabled:cursor-not-allowed disabled:opacity-40",
        state === "idle" && "w-9",
        state !== "idle" && "gap-1 px-2",
        state === "recording" && "text-red-500 dark:text-red-400"
      )}
      aria-label={label}
    >
      {state === "processing" || state === "downloading-model" ? (
        <Loader2 className="h-5 w-5 animate-spin" />
      ) : (
        <Mic className={cn("h-5 w-5", state === "recording" && "animate-pulse")} />
      )}
      {state === "recording" && (
        <span className="text-[11px] tabular-nums leading-none">
          {formatDuration(durationMs)}
        </span>
      )}
      {(state === "processing" || state === "downloading-model") && (
        <span className="text-[11px] leading-none text-zinc-400 dark:text-zinc-500">
          {label}
        </span>
      )}
      {state === "idle" && (
        <span className="pointer-events-none absolute -bottom-9 left-1/2 z-20 -translate-x-1/2 whitespace-nowrap rounded-lg bg-white/80 px-3 py-1.5 text-xs font-medium text-zinc-600 opacity-0 shadow-md ring-1 ring-zinc-200/60 backdrop-blur-sm transition-opacity group-hover:opacity-100 dark:bg-zinc-900/70 dark:text-zinc-300 dark:ring-zinc-700/60">
          {t("chat.voiceRecordHint")}
        </span>
      )}
    </button>
  );
}
