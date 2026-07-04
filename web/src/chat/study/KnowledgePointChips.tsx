// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

// STUDY module — renders the kq-kp knowledge points of one assistant message
// as chips. Clicking a chip drops the point into the spaced-repetition deck
// (front = concept name, back = gist), which is the "she remembers what you
// skipped" entry path of the learning loop. Chips whose concept is already in
// the deck render as added, so re-reading a session never duplicates cards.

import { useEffect, useState } from "react";
import { BookmarkCheck, BookmarkPlus, Lightbulb } from "lucide-react";
import { useI18n } from "../../lib/i18n";
import { cn } from "../../lib/cn";
import {
  FLASHCARD_EVENT,
  loadDeck,
  normalizeCard,
  saveDeck,
  upsertCards,
} from "./flashcardStore";
import { knowledgePointToCardInput, type KnowledgePoint } from "./knowledgePoints";

function deckFronts(): Set<string> {
  return new Set(loadDeck().cards.map((card) => card.front.trim().toLowerCase()));
}

export function KnowledgePointChips({ points }: { points: KnowledgePoint[] }) {
  const { t } = useI18n();
  const [inDeck, setInDeck] = useState<Set<string>>(deckFronts);

  useEffect(() => {
    const sync = () => setInDeck(deckFronts());
    window.addEventListener(FLASHCARD_EVENT, sync);
    window.addEventListener("storage", sync);
    return () => {
      window.removeEventListener(FLASHCARD_EVENT, sync);
      window.removeEventListener("storage", sync);
    };
  }, []);

  if (!points.length) return null;

  const addPoint = (point: KnowledgePoint) => {
    const card = normalizeCard(knowledgePointToCardInput(point));
    if (!card) return;
    saveDeck(upsertCards(loadDeck(), [card]));
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
        const added = inDeck.has(point.name.trim().toLowerCase());
        const tooltip = [
          point.gist,
          point.confidence === "inferred" ? t("chat.kpInferred") : "",
          added ? t("chat.kpAdded") : t("chat.kpAdd"),
        ]
          .filter(Boolean)
          .join("\n");
        return (
          <button
            key={point.name}
            type="button"
            disabled={added}
            onClick={() => addPoint(point)}
            title={tooltip}
            aria-label={`${point.name} — ${added ? t("chat.kpAdded") : t("chat.kpAdd")}`}
            className={cn(
              "inline-flex max-w-full items-center gap-1 rounded-full border px-2 py-0.5 text-[12px] leading-snug transition",
              added
                ? "cursor-default border-transparent bg-[var(--kq-hover-bg)] text-[var(--kq-color-muted)]"
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
