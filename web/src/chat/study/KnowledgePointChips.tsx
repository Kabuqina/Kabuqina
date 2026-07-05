// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

// STUDY module — renders the kq-kp knowledge points of one assistant message
// as chips. Clicking a chip captures one trusted flashcard into learning.db,
// which is the "she remembers what you skipped" entry path of the learning
// loop. Chips whose concept is already captured render as added, so re-reading
// a session never duplicates cards.

import { useEffect, useState } from "react";
import { BookmarkCheck, BookmarkPlus, Lightbulb } from "lucide-react";
import { useI18n } from "../../lib/i18n";
import { cn } from "../../lib/cn";
import { readPersistedSession } from "../hooks/useChatState";
import { captureIndex } from "./captureIndex";
import { cmdStudyFlashcardCapture } from "./study-api";
import { knowledgePointToCardInput, type KnowledgePoint } from "./knowledgePoints";

type ChipState = "saving" | "failed";

export function KnowledgePointChips({ points }: { points: KnowledgePoint[] }) {
  const { t } = useI18n();
  const [, setIndexVersion] = useState(0);
  const [chipStates, setChipStates] = useState<Record<string, ChipState>>({});

  useEffect(() => {
    void captureIndex.initialize();
    return captureIndex.subscribe(() => setIndexVersion((v) => v + 1));
  }, []);

  if (!points.length) return null;

  const addPoint = async (point: KnowledgePoint) => {
    const card = knowledgePointToCardInput(point);
    const front = card.front.trim();
    const back = card.back.trim();
    if (!front || !back) return;
    setChipStates((current) => ({ ...current, [front]: "saving" }));
    try {
      const sessionId = readPersistedSession();
      await cmdStudyFlashcardCapture({
        front,
        back,
        hint: card.hint,
        tags: card.tags,
        source: {
          origin: "kq-kp",
          session_id: sessionId ?? undefined,
          confidence: point.confidence,
          gist: point.gist,
        },
      });
      captureIndex.markCaptured(front);
      setChipStates((current) => {
        const next = { ...current };
        delete next[front];
        return next;
      });
    } catch {
      setChipStates((current) => ({ ...current, [front]: "failed" }));
    }
  };

  return (
    <div className="mt-2.5 flex flex-wrap items-center gap-1.5 border-t border-[var(--kq-glass-border)] pt-2">
      <span
        className="inline-flex items-center gap-1 text-[11px] font-medium text-[var(--kq-color-muted)]"
        title={t("chat.kpLabelHint")}
      >
        <Lightbulb className="h-3.5 w-3.5" strokeWidth={2.25} aria-hidden />
        {t("chat.kpLabel")}
      </span>
      {points.map((point) => {
        const front = point.name.trim();
        const state = chipStates[front];
        const saving = state === "saving";
        const failed = state === "failed";
        const unavailable = captureIndex.status() === "unavailable";
        const added = !failed && captureIndex.has(front);
        const tooltip = [
          point.gist,
          point.confidence === "inferred" ? t("chat.kpInferred") : "",
          unavailable ? t("chat.kpUnavailable") : failed ? t("chat.kpAddFailed") : added ? t("chat.kpAdded") : t("chat.kpAdd"),
        ]
          .filter(Boolean)
          .join("\n");
        return (
          <button
            key={point.name}
            type="button"
            disabled={added || saving || unavailable}
            onClick={() => void addPoint(point)}
            title={tooltip}
            aria-label={`${point.name} — ${added ? t("chat.kpAdded") : t("chat.kpAdd")}`}
            className={cn(
              "inline-flex max-w-full items-center gap-1 rounded-full border px-2 py-0.5 text-[12px] leading-snug transition",
              added
                ? "cursor-default border-transparent bg-[var(--kq-hover-bg)] text-[var(--kq-color-muted)]"
                : unavailable
                  ? "cursor-not-allowed border-[var(--kq-glass-border)] text-[var(--kq-color-muted)] opacity-60"
                : "border-[var(--kq-glass-border)] text-[var(--kq-color-ink)] hover:bg-[var(--kq-hover-bg)] hover:text-[var(--kq-color-strong)] active:scale-[0.98]",
            )}
          >
            {added ? (
              <BookmarkCheck className="h-3 w-3 shrink-0 text-emerald-600 dark:text-emerald-400" strokeWidth={2.5} aria-hidden />
            ) : (
              <BookmarkPlus className="h-3 w-3 shrink-0" strokeWidth={2.25} aria-hidden />
            )}
            <span className="truncate">
              {point.name}
              {point.confidence === "inferred" ? " *" : ""}
            </span>
          </button>
        );
      })}
    </div>
  );
}
