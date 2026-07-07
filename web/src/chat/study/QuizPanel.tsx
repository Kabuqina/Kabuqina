// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

// STUDY M3 quizzes: course-space selection, draft activation, deterministic
// backend grading, and real attempt activity writes through the desktop API.

import {
  Check,
  FileQuestion,
  Layers,
  ListChecks,
  Plus,
  RefreshCw,
  X,
  type LucideIcon,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { useI18n } from "../../lib/i18n";
import { WorkspaceSection } from "../workspaceSection";
import { STUDY_LEARNING_EVENT } from "./flashcardLearningStore";
import {
  backendQuestionsToQuizRows,
  formatQuizAttemptSummary,
  legacyQuizToMigrationQuiz,
  responsesToSubmitPayload,
  type QuizQuestionRow,
  type QuizResponseDraft,
} from "./quizLearningStore";
import { loadQuizState } from "./quizStore";
import { QUIZ_GENERATION_PROMPT } from "./studyPrompts";
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
  cmdStudyMigrateQuizzes,
  cmdStudyQuizQuestions,
  cmdStudyQuizSubmit,
  cmdStudyQuizzes,
  cmdStudySpaceCreate,
  cmdStudySpaceSelect,
  cmdStudySpaces,
  type StudyArtifact,
  type StudyQuizPerQuestion,
  type StudyQuizResult,
  type StudySpace,
} from "./study-api";

type Mode = "idle" | "taking" | "result";

function answerLetters(value: unknown): string {
  const values = Array.isArray(value) ? value : [value];
  return values
    .filter((item): item is number => Number.isInteger(item))
    .map((n) => String.fromCharCode(65 + n))
    .join(", ");
}

export function QuizPanel({
  onStartPrompt,
}: {
  onStartPrompt?: (prompt: string) => void;
}) {
  const { t, locale } = useI18n();
  const [spaces, setSpaces] = useState<StudySpace[]>([]);
  const [currentSpaceId, setCurrentSpaceId] = useState("");
  const [newSpaceTitle, setNewSpaceTitle] = useState("");
  const [drafts, setDrafts] = useState<StudyArtifact[]>([]);
  const [quizzes, setQuizzes] = useState<StudyArtifact[]>([]);
  const [selectedQuizId, setSelectedQuizId] = useState("");
  const [questions, setQuestions] = useState<QuizQuestionRow[]>([]);
  const [responses, setResponses] = useState<Record<string, QuizResponseDraft>>({});
  const [mode, setMode] = useState<Mode>("idle");
  const [index, setIndex] = useState(0);
  const [result, setResult] = useState<StudyQuizResult | null>(null);
  const [status, setStatus] = useState("");
  const [wroteBack, setWroteBack] = useState(false);
  const migratedRef = useRef(false);

  const refresh = useCallback(async () => {
    const [spaceRes, draftRes, quizRes] = await Promise.all([
      cmdStudySpaces(),
      cmdStudyDrafts("quiz"),
      cmdStudyQuizzes(),
    ]);
    const active = quizRes.quizzes || [];
    setSpaces(spaceRes.spaces || []);
    setCurrentSpaceId(spaceRes.currentSpaceId || "");
    setDrafts(draftRes.drafts || []);
    setQuizzes(active);
    setSelectedQuizId((prev) =>
      prev && active.some((quiz) => quiz.artifact_id === prev)
        ? prev
        : active[0]?.artifact_id || "",
    );
  }, []);

  useEffect(() => {
    let alive = true;
    const run = async () => {
      try {
        await refresh();
        if (!migratedRef.current) {
          migratedRef.current = true;
          const migrationQuiz = legacyQuizToMigrationQuiz(loadQuizState().quiz);
          if (migrationQuiz.questions.length > 0) {
            const res = await cmdStudyMigrateQuizzes(migrationQuiz);
            if (alive && res.migrated) {
              setStatus(t("chat.quizMigrated", { count: res.questions }));
              await refresh();
            }
          }
        }
      } catch (error) {
        if (alive) setStatus(t("chat.quizBackendUnavailable"));
        console.debug("study quiz refresh failed:", error);
      }
    };
    void run();
    const onLearning = () => {
      void refresh().catch((error) => console.debug("study quiz learning refresh failed:", error));
    };
    window.addEventListener(STUDY_LEARNING_EVENT, onLearning);
    return () => {
      alive = false;
      window.removeEventListener(STUDY_LEARNING_EVENT, onLearning);
    };
  }, [refresh, t]);

  const stats = useMemo(
    () => ({ active: quizzes.length, drafts: drafts.length, questions: questions.length }),
    [drafts.length, questions.length, quizzes.length],
  );

  const current = questions[index];

  const createSpace = async () => {
    const title = newSpaceTitle.trim();
    if (!title) return;
    try {
      const res = await cmdStudySpaceCreate(title);
      setNewSpaceTitle("");
      setCurrentSpaceId(res.currentSpaceId || res.space_id || "");
      await refresh();
    } catch (error) {
      setStatus(t("chat.quizBackendUnavailable"));
      console.debug("study create quiz space failed:", error);
    }
  };

  const selectSpace = async (spaceId: string) => {
    try {
      await cmdStudySpaceSelect(spaceId);
      setCurrentSpaceId(spaceId);
      setMode("idle");
      setQuestions([]);
      setResult(null);
      await refresh();
    } catch (error) {
      setStatus(t("chat.quizBackendUnavailable"));
      console.debug("study select quiz space failed:", error);
    }
  };

  const activateDraft = async (artifactId: string) => {
    try {
      await cmdStudyArtifactActivate(artifactId);
      await refresh();
    } catch (error) {
      setStatus(t("chat.quizBackendUnavailable"));
      console.debug("study activate quiz failed:", error);
    }
  };

  const rejectDraft = async (artifactId: string) => {
    try {
      await cmdStudyArtifactReject(artifactId);
      await refresh();
    } catch (error) {
      setStatus(t("chat.quizBackendUnavailable"));
      console.debug("study reject quiz failed:", error);
    }
  };

  const generate = () => {
    const contextPrompt = formatStudyContextForPrompt(loadStudyContext());
    onStartPrompt?.([contextPrompt, QUIZ_GENERATION_PROMPT].filter(Boolean).join("\n\n"));
  };

  const startQuiz = async () => {
    if (!selectedQuizId) return;
    try {
      const res = await cmdStudyQuizQuestions(selectedQuizId);
      const rows = backendQuestionsToQuizRows(res.questions || []);
      if (!rows.length) {
        setStatus(t("chat.quizNoQuestions"));
        return;
      }
      setQuestions(rows);
      setResponses({});
      setResult(null);
      setWroteBack(false);
      setIndex(0);
      setMode("taking");
    } catch (error) {
      setStatus(t("chat.quizBackendUnavailable"));
      console.debug("study start quiz failed:", error);
    }
  };

  const setResponse = (itemId: string, patch: QuizResponseDraft) => {
    setResponses((prev) => ({
      ...prev,
      [itemId]: { selected: [], text: "", value: null, ...(prev[itemId] || {}), ...patch },
    }));
  };

  const toggleChoice = (question: QuizQuestionRow, optionIndex: number) => {
    const prev = responses[question.itemId]?.selected || [];
    const selected = question.multiple
      ? prev.includes(optionIndex)
        ? prev.filter((n) => n !== optionIndex)
        : [...prev, optionIndex].sort((a, b) => a - b)
      : [optionIndex];
    setResponse(question.itemId, { selected, text: "", value: null });
  };

  const submit = async () => {
    if (!selectedQuizId) return;
    try {
      const graded = await cmdStudyQuizSubmit(
        selectedQuizId,
        responsesToSubmitPayload(responses),
      );
      setResult(graded);
      setMode("result");
      await refresh();
    } catch (error) {
      setStatus(t("chat.quizBackendUnavailable"));
      console.debug("study quiz submit failed:", error);
    }
  };

  const retry = () => {
    setResponses({});
    setResult(null);
    setIndex(0);
    setWroteBack(false);
    setMode("taking");
  };

  const writeBack = () => {
    if (!result) return;
    const context = loadStudyContext();
    const stamp = new Date().toISOString().slice(0, 10);
    const summary = `【${stamp}】${formatQuizAttemptSummary(
      result,
      locale === "en" ? "en" : "zh",
    )}`;
    const evaluationSummary = `${summary}${context.evaluationSummary ? `\n${context.evaluationSummary}` : ""}`.slice(
      0,
      STUDY_CONTEXT_FIELD_LIMIT,
    );
    const weak = result.weakTags?.length
      ? [result.weakTags.join("、"), context.weakPoints].filter(Boolean).join("；")
      : context.weakPoints;
    const saveResult = saveStudyContext({
      ...context,
      evaluationSummary,
      weakPoints: weak.slice(0, STUDY_CONTEXT_FIELD_LIMIT),
    });
    setWroteBack(saveResult.succeeded);
  };

  const typeLabel = (question: QuizQuestionRow) => {
    if (question.type === "true_false") return t("chat.quizTypeTrueFalse");
    if (question.type === "short_answer") return t("chat.quizTypeShort");
    return question.multiple ? t("chat.quizTypeMultiple") : t("chat.quizTypeSingle");
  };

  const userAnswer = (question: QuizQuestionRow) => {
    const response = responses[question.itemId];
    if (question.type === "short_answer") return response?.text?.trim() || t("chat.quizNoAnswer");
    if (question.type === "true_false") {
      return typeof response?.value === "boolean"
        ? response.value
          ? t("chat.quizTrue")
          : t("chat.quizFalse")
        : t("chat.quizNoAnswer");
    }
    return (response?.selected || []).map((n) => String.fromCharCode(65 + n)).join(", ") || t("chat.quizNoAnswer");
  };

  const correctAnswer = (per: StudyQuizPerQuestion) => {
    if (per.type === "true_false") {
      return per.answer === true ? t("chat.quizTrue") : t("chat.quizFalse");
    }
    if (per.type === "short_answer") {
      const parts = [
        typeof per.answer === "string" ? per.answer : "",
        ...(per.accepted || []),
      ].filter(Boolean);
      return parts.join(" / ") || t("chat.quizNoAnswer");
    }
    return answerLetters(per.answer) || t("chat.quizNoAnswer");
  };

  return (
    <WorkspaceSection sectionId="workspace.quiz" title={t("chat.quizTitle")} dotColor="#2f9e8f">
      <div className="mt-2 grid gap-2">
        <div className="flex items-center gap-2">
          <select
            value={currentSpaceId}
            onChange={(event) => void selectSpace(event.currentTarget.value)}
            className="kq-workspace-select min-w-0 flex-1 rounded-md px-2 py-1.5 text-[12px] text-[var(--kq-color-ink)]"
          >
            <option value="">{t("chat.quizNoSpace")}</option>
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
            aria-label={t("chat.quizRefresh")}
            title={t("chat.quizRefresh")}
          >
            <RefreshCw className="h-3.5 w-3.5" aria-hidden />
          </button>
        </div>
        <div className="flex items-center gap-2">
          <input
            value={newSpaceTitle}
            onChange={(event) => setNewSpaceTitle(event.currentTarget.value)}
            placeholder={t("chat.quizNewSpacePlaceholder")}
            className="kq-workspace-select min-w-0 flex-1 rounded-md px-2 py-1.5 text-[12px] text-[var(--kq-color-ink)]"
          />
          <button
            type="button"
            onClick={() => void createSpace()}
            disabled={!newSpaceTitle.trim()}
            className="kq-soft-icon-btn inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-md transition disabled:opacity-60"
            aria-label={t("chat.quizCreateSpace")}
            title={t("chat.quizCreateSpace")}
          >
            <Plus className="h-3.5 w-3.5" aria-hidden />
          </button>
        </div>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-[12px] text-[var(--kq-color-muted)]">
        <StatChip icon={Layers} label={t("chat.quizActive")} value={stats.active} />
        <StatChip icon={FileQuestion} label={t("chat.quizDrafts")} value={stats.drafts} />
        <StatChip icon={ListChecks} label={t("chat.quizQuestions")} value={stats.questions} />
      </div>

      {drafts.length ? (
        <div className="mt-3 grid gap-1.5">
          <div className="text-[12px] font-medium text-[var(--kq-color-ink)]">{t("chat.quizDrafts")}</div>
          {drafts.map((draft) => (
            <div key={draft.artifact_id} className="kq-workspace-card flex items-center gap-2 rounded-md px-2 py-2">
              <div className="min-w-0 flex-1">
                <div className="truncate text-[12.5px] font-medium text-[var(--kq-color-ink)]">{draft.title}</div>
                <div className="text-[11px] text-[var(--kq-color-muted)]">{draft.review?.status || draft.status}</div>
              </div>
              <button
                type="button"
                onClick={() => void activateDraft(draft.artifact_id)}
                className="kq-soft-icon-btn inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-md transition"
                aria-label={t("chat.quizActivate")}
                title={t("chat.quizActivate")}
              >
                <Check className="h-3.5 w-3.5" aria-hidden />
              </button>
              <button
                type="button"
                onClick={() => void rejectDraft(draft.artifact_id)}
                className="kq-soft-icon-btn inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-md transition"
                aria-label={t("chat.quizReject")}
                title={t("chat.quizReject")}
              >
                <X className="h-3.5 w-3.5" aria-hidden />
              </button>
            </div>
          ))}
        </div>
      ) : null}

      {mode === "idle" ? (
        <div className="mt-3 grid gap-2">
          <select
            value={selectedQuizId}
            onChange={(event) => setSelectedQuizId(event.currentTarget.value)}
            className="kq-workspace-select min-w-0 rounded-md px-2 py-1.5 text-[12px] text-[var(--kq-color-ink)]"
          >
            <option value="">{t("chat.quizNoQuiz")}</option>
            {quizzes.map((quiz) => (
              <option key={quiz.artifact_id} value={quiz.artifact_id}>
                {quiz.title}
              </option>
            ))}
          </select>
          <button
            type="button"
            onClick={() => void startQuiz()}
            disabled={!selectedQuizId}
            className="kq-quick-action justify-start rounded-[10px] px-2.5 py-2 text-left text-[13px] leading-snug transition disabled:opacity-60"
          >
            <ListChecks className="kq-color-icon-course mr-2 inline h-4 w-4" aria-hidden />
            {t("chat.quizStart")}
          </button>
          <button
            type="button"
            onClick={generate}
            className="kq-quick-action justify-start rounded-[10px] px-2.5 py-2 text-left text-[13px] leading-snug transition"
          >
            <FileQuestion className="kq-color-icon-course mr-2 inline h-4 w-4" aria-hidden />
            {t("chat.quizGenerate")}
          </button>
        </div>
      ) : null}

      {mode === "taking" && current ? (
        <div className="mt-3 grid gap-2">
          <div className="flex items-center justify-between text-[11.5px] text-[var(--kq-color-muted)]">
            <span>{t("chat.quizQuestionProgress", { current: index + 1, total: questions.length })}</span>
            <span className="rounded-full bg-[var(--kq-color-surface-2)] px-2 py-0.5">{typeLabel(current)}</span>
          </div>
          <div className="whitespace-pre-wrap break-words text-[13px] font-medium text-[var(--kq-color-ink)]">
            {current.prompt}
          </div>

          {current.type === "short_answer" ? (
            <textarea
              value={responses[current.itemId]?.text || ""}
              onChange={(event) => setResponse(current.itemId, { text: event.currentTarget.value, selected: [], value: null })}
              placeholder={t("chat.quizShortPlaceholder")}
              rows={2}
              className="kq-workspace-select min-h-[38px] resize-none rounded-md px-2 py-1.5 text-[12.5px] leading-snug text-[var(--kq-color-ink)] transition"
            />
          ) : current.type === "true_false" ? (
            <div className="grid grid-cols-2 gap-1.5">
              {[true, false].map((value) => {
                const active = responses[current.itemId]?.value === value;
                return (
                  <button
                    key={String(value)}
                    type="button"
                    onClick={() => setResponse(current.itemId, { value, selected: [], text: "" })}
                    className="kq-quick-action rounded-[10px] px-2.5 py-2 text-[12.5px] leading-snug transition"
                    style={active ? { borderColor: "#2f9e8f", color: "#2f9e8f" } : undefined}
                    aria-pressed={active}
                  >
                    {value ? t("chat.quizTrue") : t("chat.quizFalse")}
                  </button>
                );
              })}
            </div>
          ) : (
            <div className="grid gap-1.5">
              {current.options.map((option, optionIndex) => {
                const selected = responses[current.itemId]?.selected || [];
                const active = selected.includes(optionIndex);
                return (
                  <button
                    key={optionIndex}
                    type="button"
                    onClick={() => toggleChoice(current, optionIndex)}
                    className="kq-quick-action justify-start rounded-[10px] px-2.5 py-2 text-left text-[12.5px] leading-snug transition"
                    style={active ? { borderColor: "#2f9e8f", color: "#2f9e8f" } : undefined}
                    aria-pressed={active}
                  >
                    <span className="mr-2 inline-block font-medium">{String.fromCharCode(65 + optionIndex)}.</span>
                    {option}
                  </button>
                );
              })}
            </div>
          )}

          <div className="mt-1 flex items-center gap-2">
            <button
              type="button"
              onClick={() => setIndex((i) => Math.max(0, i - 1))}
              disabled={index === 0}
              className="kq-quick-action rounded-[10px] px-2.5 py-2 text-[12.5px] leading-snug transition disabled:opacity-50"
            >
              {t("chat.quizPrev")}
            </button>
            {index + 1 < questions.length ? (
              <button
                type="button"
                onClick={() => setIndex((i) => Math.min(questions.length - 1, i + 1))}
                className="kq-quick-action flex-1 rounded-[10px] px-2.5 py-2 text-[12.5px] leading-snug transition"
              >
                {t("chat.quizNext")}
              </button>
            ) : (
              <button
                type="button"
                onClick={() => void submit()}
                className="kq-quick-action flex-1 rounded-[10px] px-2.5 py-2 text-[12.5px] font-medium leading-snug transition"
                style={{ color: "#2f9e8f" }}
              >
                {t("chat.quizSubmit")}
              </button>
            )}
          </div>
        </div>
      ) : null}

      {mode === "result" && result ? (
        <div className="mt-3 grid gap-2">
          <div className="rounded-md bg-[var(--kq-color-surface-2)] px-3 py-2 text-[12.5px] text-[var(--kq-color-ink)]">
            <div className="font-medium">
              {t("chat.quizScore", { score: result.score, max: result.maxScore, percent: result.percent })}
            </div>
            <div className="text-[11.5px] text-[var(--kq-color-muted)]">
              {t("chat.quizCorrectCount", { correct: result.correctCount, total: result.total })}
            </div>
            {result.weakTags?.length ? (
              <div className="mt-1 text-[11.5px] text-[var(--kq-color-muted)]">
                {t("chat.quizWeakTags")}: {result.weakTags.join("、")}
              </div>
            ) : null}
          </div>

          <div className="grid gap-1.5">
            {questions.map((question, qi) => {
              const per = result.perQuestion.find((p) => p.item_id === question.itemId);
              const correct = per?.correct ?? false;
              return (
                <div key={question.itemId} className="rounded-md border border-[var(--kq-color-border)] px-2.5 py-2 text-[12px]">
                  <div className="flex items-start gap-1.5">
                    {correct ? (
                      <Check className="mt-0.5 h-3.5 w-3.5 shrink-0" style={{ color: "#2f9e8f" }} aria-hidden />
                    ) : (
                      <X className="mt-0.5 h-3.5 w-3.5 shrink-0" style={{ color: "#c2410c" }} aria-hidden />
                    )}
                    <span className="whitespace-pre-wrap break-words font-medium text-[var(--kq-color-ink)]">
                      {qi + 1}. {question.prompt}
                    </span>
                  </div>
                  <div className="mt-1 pl-5 text-[var(--kq-color-muted)]">
                    {t("chat.quizYourAnswer")}: {userAnswer(question)}
                  </div>
                  {!correct && per ? (
                    <div className="pl-5 text-[var(--kq-color-muted)]">
                      {t("chat.quizCorrectAnswer")}: {correctAnswer(per)}
                    </div>
                  ) : null}
                  {per?.explanation ? (
                    <div className="pl-5 text-[11.5px] text-[var(--kq-color-muted)]">
                      {t("chat.quizExplanation")}: {per.explanation}
                    </div>
                  ) : null}
                </div>
              );
            })}
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={writeBack}
              disabled={wroteBack}
              className="kq-quick-action inline-flex flex-1 items-center justify-center gap-1.5 rounded-[10px] px-2.5 py-2 text-[12.5px] leading-snug transition disabled:opacity-60"
            >
              <Check className="h-3.5 w-3.5" aria-hidden />
              {wroteBack ? t("chat.quizWroteBack") : t("chat.quizWriteBack")}
            </button>
            <button
              type="button"
              onClick={retry}
              className="kq-quick-action rounded-[10px] px-2.5 py-2 text-[12.5px] leading-snug transition"
            >
              {t("chat.quizRetry")}
            </button>
          </div>
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
    <span className="inline-flex items-center gap-1 whitespace-nowrap">
      <Icon className="h-3.5 w-3.5" aria-hidden />
      <span className="font-medium text-[var(--kq-color-ink)]">{value}</span>
      {label}
    </span>
  );
}
