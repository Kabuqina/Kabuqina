// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

// STUDY M2 flashcards: course-space selection, draft activation, and real
// practice activity writes through the desktop learning API.

import {
  Check,
  Layers,
  Plus,
  RefreshCw,
  Sparkles,
  X,
  type LucideIcon,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { useI18n } from "../../lib/i18n";
import { WorkspaceSection } from "../workspaceSection";
import {
  STUDY_LEARNING_EVENT,
  backendCardsToQueue,
  formatReviewSummary,
  legacyDeckToMigrationDeck,
  type ReviewQueueCard,
} from "./flashcardLearningStore";
import { loadDeck } from "./flashcardStore";
import { FLASHCARD_GENERATION_PROMPT } from "./studyPrompts";
import {
  STUDY_CONTEXT_FIELD_LIMIT,
  formatStudyContextForPrompt,
  loadStudyContext,
  saveStudyContext,
} from "./studyStore";
import {
  cmdStudyArtifactActivate,
  cmdStudyArtifactReject,
  cmdStudyDrafts,
  cmdStudyFlashcardReview,
  cmdStudyFlashcards,
  cmdStudyMigrateFlashcards,
  cmdStudySpaceCreate,
  cmdStudySpaceSelect,
  cmdStudySpaces,
  type StudyArtifactSummary,
  type StudyFlashcard,
  type StudySpace,
} from "./study-api";

type Mode = "idle" | "review" | "done";
type ReviewGrade = "again" | "hard" | "good" | "easy";

const GRADES: Array<{ grade: ReviewGrade; labelKey: string; tone: string }> = [
  { grade: "again", labelKey: "chat.flashcardGradeAgain", tone: "#c2410c" },
  { grade: "hard", labelKey: "chat.flashcardGradeHard", tone: "#a16207" },
  { grade: "good", labelKey: "chat.flashcardGradeGood", tone: "#2f9e8f" },
  { grade: "easy", labelKey: "chat.flashcardGradeEasy", tone: "#2563eb" },
];

function isDue(card: StudyFlashcard): boolean {
  const due = Date.parse(card.dueAt || "");
  return !Number.isFinite(due) || due <= Date.now();
}

export function FlashcardPanel({
  onStartPrompt,
}: {
  onStartPrompt?: (prompt: string) => void;
}) {
  const { t, locale } = useI18n();
  const [spaces, setSpaces] = useState<StudySpace[]>([]);
  const [currentSpaceId, setCurrentSpaceId] = useState<string>("");
  const [newSpaceTitle, setNewSpaceTitle] = useState("");
  const [drafts, setDrafts] = useState<StudyArtifactSummary[]>([]);
  const [cards, setCards] = useState<StudyFlashcard[]>([]);
  const [mode, setMode] = useState<Mode>("idle");
  const [queue, setQueue] = useState<ReviewQueueCard[]>([]);
  const [index, setIndex] = useState(0);
  const [revealed, setRevealed] = useState(false);
  const [status, setStatus] = useState("");
  const [reviewedCount, setReviewedCount] = useState(0);
  const [dueRemaining, setDueRemaining] = useState(0);
  const [wroteBack, setWroteBack] = useState(false);
  const migratedRef = useRef(false);

  const refresh = useCallback(async () => {
    const [spaceRes, draftRes, cardRes] = await Promise.all([
      cmdStudySpaces(),
      cmdStudyDrafts("flashcard_deck"),
      cmdStudyFlashcards(false),
    ]);
    setSpaces(spaceRes.spaces || []);
    setCurrentSpaceId(spaceRes.currentSpaceId || "");
    setDrafts(draftRes.items || []);
    setCards(cardRes.cards || []);
  }, []);

  useEffect(() => {
    let alive = true;
    const run = async () => {
      try {
        await refresh();
        if (!migratedRef.current) {
          migratedRef.current = true;
          const migrationDeck = legacyDeckToMigrationDeck(loadDeck());
          if (migrationDeck.cards.length > 0) {
            const res = await cmdStudyMigrateFlashcards(migrationDeck);
            if (alive && res.migrated) {
              setStatus(t("chat.flashcardMigrated", { count: res.cards }));
              await refresh();
            }
          }
        }
      } catch (error) {
        if (alive) setStatus(t("chat.flashcardBackendUnavailable"));
        console.debug("study flashcards refresh failed:", error);
      }
    };
    void run();
    const onLearning = () => {
      void refresh().catch((error) => console.debug("study learning refresh failed:", error));
    };
    window.addEventListener(STUDY_LEARNING_EVENT, onLearning);
    return () => {
      alive = false;
      window.removeEventListener(STUDY_LEARNING_EVENT, onLearning);
    };
  }, [refresh, t]);

  const stats = useMemo(() => {
    const due = cards.filter(isDue).length;
    const mature = cards.filter((card) => Number(card.intervalDays || 0) >= 21).length;
    return { total: cards.length, due, mature };
  }, [cards]);

  const current = queue[index];

  const createSpace = async () => {
    const title = newSpaceTitle.trim();
    if (!title) return;
    try {
      const res = await cmdStudySpaceCreate(title);
      setNewSpaceTitle("");
      setCurrentSpaceId(res.currentSpaceId || res.space_id || "");
      await refresh();
    } catch (error) {
      setStatus(t("chat.flashcardBackendUnavailable"));
      console.debug("study create space failed:", error);
    }
  };

  const selectSpace = async (spaceId: string) => {
    try {
      await cmdStudySpaceSelect(spaceId);
      setCurrentSpaceId(spaceId);
      setMode("idle");
      await refresh();
    } catch (error) {
      setStatus(t("chat.flashcardBackendUnavailable"));
      console.debug("study select space failed:", error);
    }
  };

  const activateDraft = async (artifactId: string) => {
    try {
      await cmdStudyArtifactActivate(artifactId);
      await refresh();
    } catch (error) {
      setStatus(t("chat.flashcardBackendUnavailable"));
      console.debug("study activate flashcards failed:", error);
    }
  };

  const rejectDraft = async (artifactId: string) => {
    try {
      await cmdStudyArtifactReject(artifactId);
      await refresh();
    } catch (error) {
      setStatus(t("chat.flashcardBackendUnavailable"));
      console.debug("study reject flashcards failed:", error);
    }
  };

  const generate = () => {
    const contextPrompt = formatStudyContextForPrompt(loadStudyContext());
    onStartPrompt?.([contextPrompt, FLASHCARD_GENERATION_PROMPT].filter(Boolean).join("\n\n"));
  };

  const startReview = async () => {
    try {
      const due = await cmdStudyFlashcards(true);
      const nextQueue = backendCardsToQueue(due.cards || []);
      if (!nextQueue.length) return;
      setQueue(nextQueue);
      setIndex(0);
      setRevealed(false);
      setReviewedCount(0);
      setDueRemaining(0);
      setWroteBack(false);
      setMode("review");
    } catch (error) {
      setStatus(t("chat.flashcardBackendUnavailable"));
      console.debug("study start review failed:", error);
    }
  };

  const grade = async (value: ReviewGrade) => {
    if (!current) return;
    try {
      await cmdStudyFlashcardReview(current.itemId, value);
      const reviewed = reviewedCount + 1;
      setReviewedCount(reviewed);
      if (index + 1 >= queue.length) {
        const due = await cmdStudyFlashcards(true);
        setDueRemaining((due.cards || []).length);
        await refresh();
        setMode("done");
      } else {
        setIndex(index + 1);
        setRevealed(false);
      }
    } catch (error) {
      setStatus(t("chat.flashcardBackendUnavailable"));
      console.debug("study flashcard review failed:", error);
    }
  };

  const writeBack = () => {
    const context = loadStudyContext();
    const stamp = new Date().toISOString().slice(0, 10);
    const line = `【${stamp}】${formatReviewSummary(
      { reviewed: reviewedCount, dueRemaining },
      locale === "en" ? "en" : "zh",
    )}`;
    const progressNotes = `${line}${context.progressNotes ? `\n${context.progressNotes}` : ""}`.slice(
      0,
      STUDY_CONTEXT_FIELD_LIMIT,
    );
    const result = saveStudyContext({ ...context, progressNotes });
    setWroteBack(result.succeeded);
  };

  return (
    <WorkspaceSection sectionId="workspace.flashcards" title={t("chat.flashcardTitle")} dotColor="#2f9e8f">
      <div className="mt-2 grid grid-cols-1 gap-2">
        <div className="flex items-center gap-2">
          <select
            value={currentSpaceId}
            onChange={(event) => void selectSpace(event.currentTarget.value)}
            className="kq-workspace-select min-w-0 flex-1 rounded-md px-2 py-1.5 text-[12px] text-[var(--kq-color-ink)]"
          >
            <option value="">{t("chat.flashcardNoSpace")}</option>
            {spaces.map((space) => (
              <option key={space.space_id} value={space.space_id}>
                {space.title}
              </option>
            ))}
          </select>
          <button
            type="button"
            onClick={() => void refresh()}
            className="kq-soft-icon-btn inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-md transition"
            aria-label={t("chat.flashcardRefresh")}
            title={t("chat.flashcardRefresh")}
          >
            <RefreshCw className="h-3.5 w-3.5" aria-hidden />
          </button>
        </div>
        <div className="flex items-center gap-2">
          <input
            value={newSpaceTitle}
            onChange={(event) => setNewSpaceTitle(event.currentTarget.value)}
            placeholder={t("chat.flashcardNewSpacePlaceholder")}
            className="kq-workspace-select min-w-0 flex-1 rounded-md px-2 py-1.5 text-[12px] text-[var(--kq-color-ink)]"
          />
          <button
            type="button"
            onClick={() => void createSpace()}
            disabled={!newSpaceTitle.trim()}
            className="kq-soft-icon-btn inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-md transition disabled:opacity-60"
            aria-label={t("chat.flashcardCreateSpace")}
            title={t("chat.flashcardCreateSpace")}
          >
            <Plus className="h-3.5 w-3.5" aria-hidden />
          </button>
        </div>
      </div>

      <div className="mt-3 flex items-center gap-3 text-[12px] text-[var(--kq-color-muted)]">
        <StatChip icon={Layers} label={t("chat.flashcardStatsTotal")} value={stats.total} />
        <StatChip icon={Sparkles} label={t("chat.flashcardStatsDue")} value={stats.due} />
        <StatChip icon={Check} label={t("chat.flashcardStatsMature")} value={stats.mature} />
      </div>

      {drafts.length ? (
        <div className="mt-3 grid grid-cols-1 gap-1.5">
          <div className="text-[12px] font-medium text-[var(--kq-color-ink)]">
            {t("chat.flashcardDrafts")}
          </div>
          {drafts.map((draft) => (
            <div key={draft.artifact_id} className="kq-workspace-card flex items-center gap-2 rounded-md px-2 py-2">
              <div className="min-w-0 flex-1">
                <div className="truncate text-[12.5px] font-medium text-[var(--kq-color-ink)]">
                  {draft.title}
                </div>
                <div className="text-[11px] text-[var(--kq-color-muted)]">
                  {draft.review?.status || draft.status}
                </div>
              </div>
              <button
                type="button"
                onClick={() => void activateDraft(draft.artifact_id)}
                className="kq-soft-icon-btn inline-flex h-8 w-8 items-center justify-center rounded-md transition"
                aria-label={t("chat.flashcardActivate")}
                title={t("chat.flashcardActivate")}
              >
                <Check className="h-3.5 w-3.5" aria-hidden />
              </button>
              <button
                type="button"
                onClick={() => void rejectDraft(draft.artifact_id)}
                className="kq-soft-icon-btn inline-flex h-8 w-8 items-center justify-center rounded-md transition"
                aria-label={t("chat.flashcardReject")}
                title={t("chat.flashcardReject")}
              >
                <X className="h-3.5 w-3.5" aria-hidden />
              </button>
            </div>
          ))}
        </div>
      ) : null}

      {mode === "review" && current ? (
        <div className="mt-3 grid grid-cols-1 gap-2">
          <div className="kq-workspace-card rounded-md px-3 py-3">
            <div className="whitespace-pre-wrap break-words text-[13px] font-medium text-[var(--kq-color-ink)]">
              {current.front}
            </div>
            {revealed ? (
              <div className="mt-2 whitespace-pre-wrap break-words border-t border-[var(--kq-color-border)] pt-2 text-[12.5px] leading-snug text-[var(--kq-color-ink)]">
                {current.back}
                {current.hint ? (
                  <div className="mt-1 text-[11.5px] text-[var(--kq-color-muted)]">
                    {t("chat.flashcardHint")}: {current.hint}
                  </div>
                ) : null}
              </div>
            ) : null}
          </div>
          <div className="text-right text-[11px] text-[var(--kq-color-muted)]">
            {t("chat.flashcardRemaining", { count: queue.length - index })}
          </div>
          {revealed ? (
            <div className="grid grid-cols-4 gap-1.5">
              {GRADES.map((g) => (
                <button
                  key={g.grade}
                  type="button"
                  onClick={() => void grade(g.grade)}
                  className="kq-quick-action rounded-[10px] px-1 py-2 text-[12px] leading-snug transition"
                  style={{ color: g.tone }}
                >
                  {t(g.labelKey)}
                </button>
              ))}
            </div>
          ) : (
            <button
              type="button"
              onClick={() => setRevealed(true)}
              className="kq-quick-action rounded-[10px] px-2.5 py-2 text-[12.5px] leading-snug transition"
            >
              {t("chat.flashcardShowAnswer")}
            </button>
          )}
        </div>
      ) : null}

      {mode === "done" ? (
        <div className="mt-3 grid grid-cols-1 gap-2">
          <div className="rounded-md bg-[var(--kq-color-surface-2)] px-3 py-2 text-[12.5px] text-[var(--kq-color-ink)]">
            {t("chat.flashcardReviewDone")}
          </div>
          <button
            type="button"
            onClick={writeBack}
            disabled={wroteBack}
            className="kq-quick-action inline-flex items-center justify-center gap-1.5 rounded-[10px] px-2.5 py-2 text-[12.5px] leading-snug transition disabled:opacity-60"
          >
            <Check className="h-3.5 w-3.5" aria-hidden />
            {wroteBack ? t("chat.flashcardWroteBack") : t("chat.flashcardWriteBack")}
          </button>
        </div>
      ) : null}

      {mode === "idle" ? (
        <div className="mt-3 grid grid-cols-1 gap-2">
          <button
            type="button"
            onClick={() => void startReview()}
            disabled={stats.due === 0}
            className="kq-quick-action justify-start rounded-[10px] px-2.5 py-2 text-left text-[13px] leading-snug transition disabled:opacity-60"
          >
            <Sparkles className="kq-color-icon-course mr-2 inline h-4 w-4" aria-hidden />
            {stats.due > 0 ? t("chat.flashcardStartReview") : t("chat.flashcardNoDue")}
          </button>
          <button
            type="button"
            onClick={generate}
            className="kq-quick-action justify-start rounded-[10px] px-2.5 py-2 text-left text-[13px] leading-snug transition"
          >
            <Sparkles className="kq-color-icon-course mr-2 inline h-4 w-4" aria-hidden />
            {t("chat.flashcardGenerate")}
          </button>
        </div>
      ) : null}

      {status ? <div className="mt-2 text-[11.5px] text-[var(--kq-color-muted)]">{status}</div> : null}
    </WorkspaceSection>
  );
}

function StatChip({
  icon: Icon,
  label,
  value,
}: {
  icon: LucideIcon;
  label: string;
  value: number;
}) {
  return (
    <span className="inline-flex items-center gap-1">
      <Icon className="h-3.5 w-3.5" aria-hidden />
      <span className="font-medium text-[var(--kq-color-ink)]">{value}</span>
      {label}
    </span>
  );
}
