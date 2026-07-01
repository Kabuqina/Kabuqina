// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

// STUDY module — self-test quiz panel.
//
// A thin view over quizStore: parsing, validation and grading all live in the
// store (unit-tested there). The agent writes a quiz via a bounded prompt; the
// student pastes it back, takes it here, and the client grades it locally. A
// graded result can be written back into the study context to close the loop.

import { Check, Eraser, FileQuestion, Import, ListChecks, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { useI18n } from "../../lib/i18n";
import { WorkspaceSection } from "../workspaceSection";
import {
  QUIZ_EVENT,
  type QuizResult,
  type QuizState,
  clearQuizState,
  emptyResponse,
  formatQuizResultForContext,
  gradeQuiz,
  loadQuizState,
  parseQuiz,
  saveQuizState,
} from "./quizStore";
import { QUIZ_GENERATION_PROMPT } from "./studyPrompts";
import {
  STUDY_CONTEXT_FIELD_LIMIT,
  formatStudyContextForPrompt,
  loadStudyContext,
  saveStudyContext,
} from "./studyStore";

type Mode = "idle" | "taking" | "result";

function initialMode(state: QuizState): Mode {
  if (state.submitted && state.quiz.questions.length) return "result";
  return "idle";
}

export function QuizPanel({
  onStartPrompt,
}: {
  onStartPrompt?: (prompt: string) => void;
}) {
  const { t } = useI18n();
  const [state, setState] = useState<QuizState>(loadQuizState);
  const [mode, setMode] = useState<Mode>(() => initialMode(loadQuizState()));
  const [index, setIndex] = useState(0);
  const [showImport, setShowImport] = useState(false);
  const [importText, setImportText] = useState("");
  const [importMsg, setImportMsg] = useState("");
  const [wroteBack, setWroteBack] = useState(false);

  useEffect(() => {
    const sync = () => setState(loadQuizState());
    window.addEventListener("storage", sync);
    window.addEventListener(QUIZ_EVENT, sync);
    return () => {
      window.removeEventListener("storage", sync);
      window.removeEventListener(QUIZ_EVENT, sync);
    };
  }, []);

  const persist = (next: QuizState) => setState(saveQuizState(next));

  const typeLabel = (type: string) =>
    type === "multiple"
      ? t("chat.quizTypeMultiple")
      : type === "short"
        ? t("chat.quizTypeShort")
        : t("chat.quizTypeSingle");

  const generate = () => {
    const contextPrompt = formatStudyContextForPrompt(loadStudyContext());
    onStartPrompt?.([contextPrompt, QUIZ_GENERATION_PROMPT].filter(Boolean).join("\n\n"));
  };

  const runImport = () => {
    const quiz = parseQuiz(importText);
    if (!quiz.questions.length) {
      setImportMsg(t("chat.quizImportEmpty"));
      return;
    }
    persist({ version: 1, quiz, responses: {}, submitted: false });
    setImportText("");
    setShowImport(false);
    setImportMsg(t("chat.quizLoaded", { count: quiz.questions.length }));
    setIndex(0);
  };

  const startQuiz = () => {
    if (!state.quiz.questions.length) return;
    persist({ ...state, responses: {}, submitted: false });
    setIndex(0);
    setWroteBack(false);
    setMode("taking");
  };

  const setResponse = (id: string, selected: number[], text: string) => {
    const responses = { ...state.responses, [id]: { selected, text } };
    persist({ ...state, responses });
  };

  const toggleChoice = (id: string, optionIndex: number, multiple: boolean) => {
    const prev = state.responses[id] ?? emptyResponse();
    let selected: number[];
    if (multiple) {
      selected = prev.selected.includes(optionIndex)
        ? prev.selected.filter((n) => n !== optionIndex)
        : [...prev.selected, optionIndex].sort((a, b) => a - b);
    } else {
      selected = [optionIndex];
    }
    setResponse(id, selected, "");
  };

  const submit = () => {
    persist({ ...state, submitted: true });
    setMode("result");
  };

  const result: QuizResult | null = useMemo(
    () => (mode === "result" ? gradeQuiz(state.quiz, state.responses) : null),
    [mode, state.quiz, state.responses],
  );

  const writeBack = () => {
    if (!result) return;
    const context = loadStudyContext();
    const summary = formatQuizResultForContext(state.quiz, result);
    const evaluationSummary = `${summary}${context.evaluationSummary ? `\n${context.evaluationSummary}` : ""}`.slice(
      0,
      STUDY_CONTEXT_FIELD_LIMIT,
    );
    let weakPoints = context.weakPoints;
    if (result.weakTags.length) {
      const merged = [result.weakTags.join("、"), context.weakPoints].filter(Boolean).join("；");
      weakPoints = merged.slice(0, STUDY_CONTEXT_FIELD_LIMIT);
    }
    saveStudyContext({ ...context, evaluationSummary, weakPoints });
    setWroteBack(true);
  };

  const retry = () => {
    persist({ ...state, responses: {}, submitted: false });
    setIndex(0);
    setWroteBack(false);
    setMode("taking");
  };

  const clearAll = () => {
    if (typeof window !== "undefined" && !window.confirm(t("chat.quizClearConfirm"))) return;
    setState(clearQuizState());
    setMode("idle");
    setIndex(0);
    setImportMsg("");
  };

  const questions = state.quiz.questions;
  const current = questions[index];

  return (
    <WorkspaceSection
      sectionId="workspace.quiz"
      title={t("chat.quizTitle")}
      dotColor="#2f9e8f"
    >
      {mode === "taking" && current ? (
        <div className="mt-3 grid gap-2">
          <div className="flex items-center justify-between text-[11.5px] text-[var(--kq-color-muted)]">
            <span>{t("chat.quizQuestionProgress", { current: index + 1, total: questions.length })}</span>
            <span className="rounded-full bg-[var(--kq-color-surface-2)] px-2 py-0.5">{typeLabel(current.type)}</span>
          </div>
          <div className="text-[13px] font-medium text-[var(--kq-color-ink)] whitespace-pre-wrap break-words">
            {current.prompt}
          </div>

          {current.type === "short" ? (
            <textarea
              value={state.responses[current.id]?.text ?? ""}
              onChange={(event) => setResponse(current.id, [], event.currentTarget.value)}
              placeholder={t("chat.quizShortPlaceholder")}
              rows={2}
              className="kq-workspace-select min-h-[38px] resize-none rounded-md px-2 py-1.5 text-[12.5px] leading-snug text-[var(--kq-color-ink)] transition"
            />
          ) : (
            <div className="grid gap-1.5">
              {current.options.map((option, optionIndex) => {
                const selected = state.responses[current.id]?.selected ?? [];
                const active = selected.includes(optionIndex);
                return (
                  <button
                    key={optionIndex}
                    type="button"
                    onClick={() => toggleChoice(current.id, optionIndex, current.type === "multiple")}
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
                onClick={submit}
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
            {result.weakTags.length ? (
              <div className="mt-1 text-[11.5px] text-[var(--kq-color-muted)]">
                {t("chat.quizWeakTags")}: {result.weakTags.join("、")}
              </div>
            ) : null}
          </div>

          <div className="grid gap-1.5">
            {questions.map((question, qi) => {
              const per = result.perQuestion.find((p) => p.id === question.id);
              const correct = per?.correct ?? false;
              const response = state.responses[question.id];
              const yours =
                question.type === "short"
                  ? response?.text?.trim() || t("chat.quizNoAnswer")
                  : (response?.selected ?? [])
                      .map((n) => String.fromCharCode(65 + n))
                      .join(", ") || t("chat.quizNoAnswer");
              const answer =
                question.type === "short"
                  ? question.accepted.join(" / ")
                  : question.answerIndices.map((n) => String.fromCharCode(65 + n)).join(", ");
              return (
                <div key={question.id} className="rounded-md border border-[var(--kq-color-border)] px-2.5 py-2 text-[12px]">
                  <div className="flex items-start gap-1.5">
                    {correct ? (
                      <Check className="mt-0.5 h-3.5 w-3.5 shrink-0" style={{ color: "#2f9e8f" }} aria-hidden />
                    ) : (
                      <X className="mt-0.5 h-3.5 w-3.5 shrink-0" style={{ color: "#c2410c" }} aria-hidden />
                    )}
                    <span className="font-medium text-[var(--kq-color-ink)] whitespace-pre-wrap break-words">
                      {qi + 1}. {question.prompt}
                    </span>
                  </div>
                  <div className="mt-1 pl-5 text-[var(--kq-color-muted)]">
                    {t("chat.quizYourAnswer")}: {yours}
                  </div>
                  {!correct ? (
                    <div className="pl-5 text-[var(--kq-color-muted)]">
                      {t("chat.quizCorrectAnswer")}: {answer}
                    </div>
                  ) : null}
                  {question.explanation ? (
                    <div className="pl-5 text-[11.5px] text-[var(--kq-color-muted)]">
                      {t("chat.quizExplanation")}: {question.explanation}
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

      {mode === "idle" ? (
        <div className="mt-3 grid grid-cols-1 gap-2">
          <button
            type="button"
            onClick={startQuiz}
            disabled={questions.length === 0}
            className="kq-quick-action justify-start rounded-[10px] px-2.5 py-2 text-left text-[13px] leading-snug transition disabled:opacity-60"
          >
            <ListChecks className="kq-color-icon-course mr-2 inline h-4 w-4" aria-hidden />
            {questions.length > 0
              ? `${t("chat.quizStart")}（${questions.length}）`
              : t("chat.quizStart")}
          </button>
          <button
            type="button"
            onClick={generate}
            className="kq-quick-action justify-start rounded-[10px] px-2.5 py-2 text-left text-[13px] leading-snug transition"
          >
            <FileQuestion className="kq-color-icon-course mr-2 inline h-4 w-4" aria-hidden />
            {t("chat.quizGenerate")}
          </button>
          <button
            type="button"
            onClick={() => {
              setShowImport((v) => !v);
              setImportMsg("");
            }}
            className="kq-quick-action justify-start rounded-[10px] px-2.5 py-2 text-left text-[13px] leading-snug transition"
          >
            <Import className="kq-color-icon-course mr-2 inline h-4 w-4" aria-hidden />
            {t("chat.quizImportToggle")}
          </button>

          {showImport ? (
            <div className="grid gap-1.5">
              <textarea
                value={importText}
                onChange={(event) => setImportText(event.currentTarget.value)}
                placeholder={t("chat.quizImportPlaceholder")}
                rows={4}
                className="kq-workspace-select min-h-[64px] resize-none rounded-md px-2 py-1.5 text-[12px] leading-snug text-[var(--kq-color-ink)] transition"
              />
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={runImport}
                  disabled={!importText.trim()}
                  className="kq-quick-action inline-flex flex-1 items-center justify-center gap-1.5 rounded-[10px] px-2.5 py-2 text-[12.5px] leading-snug transition disabled:opacity-60"
                >
                  <Import className="h-3.5 w-3.5" aria-hidden />
                  {t("chat.quizImport")}
                </button>
                <button
                  type="button"
                  onClick={clearAll}
                  disabled={questions.length === 0}
                  className="kq-soft-icon-btn inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-md transition disabled:opacity-60"
                  aria-label={t("chat.quizClear")}
                  title={t("chat.quizClear")}
                >
                  <Eraser className="h-3.5 w-3.5" aria-hidden />
                </button>
              </div>
              {importMsg ? (
                <div className="text-[11.5px] text-[var(--kq-color-muted)]">{importMsg}</div>
              ) : null}
            </div>
          ) : null}
        </div>
      ) : null}
    </WorkspaceSection>
  );
}
