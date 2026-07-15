// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { lazy, Suspense, useCallback, useEffect, useRef, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { useI18n } from "../../lib/i18n";
import type { StudyFlashcard, StudyQuizQuestion, StudyQuizResult } from "../../chat/study/study-api";
import { STUDY_LEARNING_EVENT } from "../learningEvent";
import { RequestCoordinator, type Loadable } from "../loadable";
import type { StudyPracticeHome } from "../repository";
import { useStudyRepository } from "../repositoryContext";

const CodePracticeSurface = lazy(async () => ({ default: (await import("./CodePracticeSurface")).CodePracticeSurface }));
const DerivationPracticeSurface = lazy(async () => ({ default: (await import("./DerivationPracticeSurface")).DerivationPracticeSurface }));

type Mode = "home" | "cards" | "quiz" | "result";
type Grade = "again" | "hard" | "good" | "easy";
type Responses = Record<string, Record<string, unknown>>;

const GRADES: Array<{ grade: Grade; key: "practiceAgain" | "practiceHard" | "practiceGood" | "practiceEasy" }> = [
  { grade: "again", key: "practiceAgain" },
  { grade: "hard", key: "practiceHard" },
  { grade: "good", key: "practiceGood" },
  { grade: "easy", key: "practiceEasy" },
];

export function PracticePage({ spaceId, onDirtyChange, onNavigateAway }: { spaceId: string; onDirtyChange?: (dirty: boolean) => void; onNavigateAway?: (to: string) => void }) {
  const { t } = useI18n();
  const repository = useStudyRepository();
  const heading = useRef<HTMLHeadingElement>(null);
  const requests = useRef(new RequestCoordinator());
  const mutations = useRef(new RequestCoordinator());
  const sourceRequests = useRef(new RequestCoordinator());
  const location = useLocation();
  const [snapshot, setSnapshot] = useState<Loadable<StudyPracticeHome>>({ status: "idle" });
  const [mode, setMode] = useState<Mode>("home");
  const [queue, setQueue] = useState<StudyFlashcard[]>([]);
  const [cardIndex, setCardIndex] = useState(0);
  const [revealed, setRevealed] = useState(false);
  const [quizId, setQuizId] = useState("");
  const [questions, setQuestions] = useState<StudyQuizQuestion[]>([]);
  const [questionIndex, setQuestionIndex] = useState(0);
  const [responses, setResponses] = useState<Responses>({});
  const [result, setResult] = useState<StudyQuizResult | null>(null);
  const [pending, setPending] = useState(false);
  const [actionError, setActionError] = useState("");
  const [generationNotice, setGenerationNotice] = useState<"draft" | "fallback" | null>(null);
  const dirty = mode === "quiz" && result === null && Object.keys(responses).length > 0;
  const sourceActivityId = new URLSearchParams(location.search).get("source") === "wrongbook"
    ? new URLSearchParams(location.search).get("activityId")
    : null;

  const data = snapshot.status === "ready"
    ? snapshot.data
    : snapshot.status === "loading" || snapshot.status === "error"
      ? snapshot.previous
      : undefined;

  const load = useCallback(() => {
    const request = requests.current.begin();
    setSnapshot((current) => ({
      status: "loading",
      ...(current.status === "ready" ? { previous: current.data } : {}),
      ...(current.status === "error" && current.previous ? { previous: current.previous } : {}),
    }));
    void repository.loadPracticeHome(spaceId, request.signal).then(
      (next) => {
        if (requests.current.isCurrent(request.generation)) setSnapshot({ status: "ready", data: next });
      },
      (error) => {
        if (!requests.current.isCurrent(request.generation)) return;
        setSnapshot((current) => ({
          status: "error", error,
          ...(current.status === "loading" && current.previous ? { previous: current.previous } : {}),
        }));
      },
    );
  }, [repository, spaceId]);

  useEffect(() => {
    const requestCoordinator = requests.current;
    const mutationCoordinator = mutations.current;
    const sourceCoordinator = sourceRequests.current;
    heading.current?.focus();
    load();
    const refresh = () => load();
    window.addEventListener(STUDY_LEARNING_EVENT, refresh);
    return () => {
      window.removeEventListener(STUDY_LEARNING_EVENT, refresh);
      requestCoordinator.cancel();
      mutationCoordinator.cancel();
      sourceCoordinator.cancel();
    };
  }, [load]);

  useEffect(() => { onDirtyChange?.(dirty); }, [dirty, onDirtyChange]);
  useEffect(() => () => { onDirtyChange?.(false); }, [onDirtyChange]);
  useEffect(() => {
    if (!dirty) return;
    const beforeUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", beforeUnload);
    return () => window.removeEventListener("beforeunload", beforeUnload);
  }, [dirty]);

  useEffect(() => {
    if (!sourceActivityId) return;
    const request = sourceRequests.current.begin();
    setPending(true);
    setActionError("");
    void repository.resolvePracticeSource(spaceId, sourceActivityId, request.signal).then(
      (source) => repository.loadQuizQuestions(spaceId, source.artifact_id, request.signal).then((next) => ({ source, next })),
    ).then(
      ({ source, next }) => {
        if (!sourceRequests.current.isCurrent(request.generation)) return;
        const firstFailedIndex = next.findIndex((question) => source.item_ids.includes(question.item_id));
        setPending(false);
        if (firstFailedIndex < 0) {
          setMode("home");
          setActionError(t("study.practiceSourceUnavailable"));
          return;
        }
        setQuizId(source.artifact_id);
        setQuestions(next);
        setQuestionIndex(firstFailedIndex);
        setResponses({});
        setResult(null);
        setMode("quiz");
      },
      () => {
        if (!sourceRequests.current.isCurrent(request.generation)) return;
        setPending(false);
        setMode("home");
        setActionError(t("study.practiceSourceUnavailable"));
      },
    );
  }, [repository, sourceActivityId, spaceId, t]);

  useEffect(() => {
    if (mode === "home") {
      heading.current?.focus();
      return;
    }
    const frame = window.requestAnimationFrame(() => document.getElementById("study-practice-surface")?.focus());
    return () => window.cancelAnimationFrame(frame);
  }, [cardIndex, mode, questionIndex]);

  const openCards = () => {
    if (!data?.dueCards.length) return;
    setQueue(data.dueCards);
    setCardIndex(0);
    setRevealed(false);
    setActionError("");
    setGenerationNotice(null);
    setMode("cards");
  };

  const review = (grade: Grade) => {
    const card = queue[cardIndex];
    if (!card || pending) return;
    const request = mutations.current.begin();
    setPending(true);
    setActionError("");
    void repository.reviewFlashcard(spaceId, card.item_id, grade, request.signal).then(
      () => {
        if (!mutations.current.isCurrent(request.generation)) return;
        setPending(false);
        if (cardIndex + 1 >= queue.length) {
          setMode("home");
          window.dispatchEvent(new Event(STUDY_LEARNING_EVENT));
        } else {
          setCardIndex((index) => index + 1);
          setRevealed(false);
        }
      },
      () => {
        if (!mutations.current.isCurrent(request.generation)) return;
        setPending(false);
        setActionError(t("study.practiceActionFailed"));
      },
    );
  };

  const openQuiz = (artifactId: string) => {
    const request = mutations.current.begin();
    setPending(true);
    setActionError("");
    void repository.loadQuizQuestions(spaceId, artifactId, request.signal).then(
      (next) => {
        if (!mutations.current.isCurrent(request.generation)) return;
        setPending(false);
        setQuizId(artifactId);
        setQuestions(next);
        setQuestionIndex(0);
        setResponses({});
        setResult(null);
        setGenerationNotice(null);
        setMode("quiz");
      },
      () => {
        if (!mutations.current.isCurrent(request.generation)) return;
        setPending(false);
        setActionError(t("study.practiceActionFailed"));
      },
    );
  };

  const updateResponse = (itemId: string, response: Record<string, unknown>) => {
    setResponses((current) => ({ ...current, [itemId]: response }));
  };

  const submit = () => {
    if (!quizId || pending) return;
    const request = mutations.current.begin();
    setPending(true);
    setActionError("");
    void repository.submitQuiz(spaceId, quizId, responses, request.signal).then(
      (next) => {
        if (!mutations.current.isCurrent(request.generation)) return;
        setPending(false);
        setResult(next);
        setMode("result");
        window.dispatchEvent(new Event(STUDY_LEARNING_EVENT));
      },
      () => {
        if (!mutations.current.isCurrent(request.generation)) return;
        setPending(false);
        setActionError(t("study.practiceActionFailed"));
      },
    );
  };

  const reviewDraft = (artifactId: string, status: "active" | "rejected", kind: string) => {
    if (pending) return;
    const request = mutations.current.begin();
    setPending(true);
    setActionError("");
    void repository.setArtifactStatus(spaceId, artifactId, status, request.signal).then(
      () => {
        if (!mutations.current.isCurrent(request.generation)) return;
        setPending(false);
        window.dispatchEvent(new Event(STUDY_LEARNING_EVENT));
        if (status === "active" && kind === "quiz") openQuiz(artifactId);
      },
      () => {
        if (!mutations.current.isCurrent(request.generation)) return;
        setPending(false);
        setActionError(t("study.practiceActionFailed"));
      },
    );
  };

  const generatePractice = (itemId: string, kind: "transcribe" | "variant") => {
    if (!quizId || pending) return;
    const request = mutations.current.begin();
    setPending(true);
    setActionError("");
    setGenerationNotice(null);
    void repository.generatePracticeDraft(spaceId, quizId, itemId, kind, request.signal).then(
      (next) => {
        if (!mutations.current.isCurrent(request.generation)) return;
        setPending(false);
        if (!Object.keys(responses).length) setMode("home");
        setGenerationNotice(next.generated ? "draft" : "fallback");
        window.dispatchEvent(new Event(STUDY_LEARNING_EVENT));
      },
      () => {
        if (!mutations.current.isCurrent(request.generation)) return;
        setPending(false);
        setActionError(t("study.practiceActionFailed"));
      },
    );
  };

  const currentCard = queue[cardIndex];
  const currentQuestion = questions[questionIndex];

  return (
    <section className="kq-study-content-page" aria-labelledby="study-page-title">
      <header className="kq-study-page-heading">
        <p className="kq-study-placeholder-kicker">{t("study.lifecycle")}</p>
        <h1 id="study-page-title" ref={heading} tabIndex={-1}>{t("study.pagePractice")}</h1>
        <p>{t("study.practiceLead")}</p>
      </header>

      {snapshot.status === "loading" && !data ? <p role="status">{t("study.pageLoading")}</p> : null}
      {snapshot.status === "error" && !data ? <PageError retry={load} /> : null}
      {snapshot.status === "error" && data ? <div className="kq-study-page-alert" role="alert"><span>{t("study.pageStale")}</span><button type="button" onClick={load}>{t("study.retry")}</button></div> : null}
      {mode === "home" && actionError ? <p role="alert" className="kq-study-page-error">{actionError}</p> : null}
      {generationNotice ? <div className="kq-study-page-alert" role="status"><span>{t(generationNotice === "draft" ? "study.practiceDraftCreated" : "study.practiceGenerationFallback")}</span>{generationNotice === "fallback" ? <Link to="/chat" onClick={(event) => { if (onNavigateAway) { event.preventDefault(); onNavigateAway("/chat"); } }}>{t("study.backToChat")}</Link> : null}</div> : null}

      {mode === "home" && data ? (
        <div className="kq-study-practice-home">
          <article className="kq-study-practice-card">
            <p>{t("study.practiceCardsKicker")}</p>
            <h2>{t("study.practiceCardsTitle")}</h2>
            {data.unavailable?.includes("cards") ? <SectionUnavailable retry={load} /> : <><strong>{t("study.practiceDueCount", { count: data.dueCards.length })}</strong><span>{t("study.practiceCardsTotal", { count: data.cards.length })}</span></>}
            <button type="button" className="kq-study-primary-link" disabled={data.unavailable?.includes("cards") || !data.dueCards.length} onClick={openCards}>{t("study.practiceStartCards")}</button>
          </article>
          <article className="kq-study-practice-card">
            <p>{t("study.practiceQuizKicker")}</p>
            <h2>{t("study.practiceQuizTitle")}</h2>
            {data.unavailable?.includes("quizzes") ? <SectionUnavailable retry={load} /> : data.quizzes.length ? <div className="kq-study-inline-actions">{data.quizzes.map((quiz) => <button key={quiz.artifact_id} type="button" disabled={pending} onClick={() => openQuiz(quiz.artifact_id)}>{quiz.title}</button>)}</div> : <p>{t("study.practiceQuizEmpty")}</p>}
          </article>
          {data.drafts.length || data.unavailable?.includes("drafts") ? <article className="kq-study-practice-card"><p>{t("study.drafts")}</p>{data.unavailable?.includes("drafts") ? <SectionUnavailable retry={load} /> : data.drafts.map((draft) => <div key={draft.artifact_id} className="kq-study-draft-row"><div><strong>{draft.title}</strong><span>{draft.kind} · {draft.review?.status || draft.status}</span></div><div className="kq-study-inline-actions"><button type="button" disabled={pending} onClick={() => reviewDraft(draft.artifact_id, "active", draft.kind)}>{t("study.flyleafInk")}</button><button type="button" disabled={pending} onClick={() => reviewDraft(draft.artifact_id, "rejected", draft.kind)}>{t("study.flyleafErase")}</button></div></div>)}</article> : null}
        </div>
      ) : null}

      {mode === "cards" && currentCard ? <Flashcard card={currentCard} index={cardIndex} total={queue.length} revealed={revealed} pending={pending} error={actionError} onReveal={() => setRevealed(true)} onGrade={review} onExit={() => setMode("home")} /> : null}
      {mode === "quiz" && currentQuestion ? <QuizQuestion question={currentQuestion} index={questionIndex} total={questions.length} response={responses[currentQuestion.item_id] ?? {}} pending={pending} error={actionError} onResponse={updateResponse} onPrevious={() => setQuestionIndex((index) => Math.max(0, index - 1))} onNext={() => setQuestionIndex((index) => Math.min(questions.length - 1, index + 1))} onSubmit={submit} onGenerate={generatePractice} /> : null}
      {mode === "result" && result ? <QuizResult result={result} onRetry={() => { setQuestionIndex(0); setResponses({}); setResult(null); setMode("quiz"); }} onHome={() => setMode("home")} /> : null}
    </section>
  );
}

function PageError({ retry }: { retry: () => void }) { const { t } = useI18n(); return <div className="kq-study-page-alert" role="alert"><p>{t("study.pageLoadFailed")}</p><button type="button" onClick={retry}>{t("study.retry")}</button><Link to="/chat">{t("study.backToChat")}</Link></div>; }

function SectionUnavailable({ retry }: { retry: () => void }) { const { t } = useI18n(); return <div role="status"><p>{t("study.practiceSectionUnavailable")}</p><button type="button" onClick={retry}>{t("study.retry")}</button></div>; }

function Flashcard({ card, index, total, revealed, pending, error, onReveal, onGrade, onExit }: { card: StudyFlashcard; index: number; total: number; revealed: boolean; pending: boolean; error: string; onReveal: () => void; onGrade: (grade: Grade) => void; onExit: () => void }) {
  const { t } = useI18n();
  const onKeyDown = (event: React.KeyboardEvent<HTMLElement>) => {
    if (event.repeat || event.target !== event.currentTarget || document.activeElement !== event.currentTarget || pending) return;
    if (event.key === " ") { event.preventDefault(); if (!revealed) onReveal(); return; }
    const grade = ({ "1": "again", "2": "hard", "3": "good", "4": "easy" } as const)[event.key];
    if (revealed && grade) { event.preventDefault(); onGrade(grade); }
  };
  return <article id="study-practice-surface" className="kq-study-practice-surface" tabIndex={0} onKeyDown={onKeyDown}><p>{t("study.practiceProgress", { current: index + 1, total })}</p><h2>{card.front}</h2>{revealed ? <><p className="kq-study-practice-answer">{card.back}</p>{card.hint ? <p>{card.hint}</p> : null}<div className="kq-study-inline-actions">{GRADES.map(({ grade, key }) => <button key={grade} type="button" disabled={pending} onClick={() => onGrade(grade)}>{t(`study.${key}`)}</button>)}</div></> : <button type="button" className="kq-study-primary-link" onClick={onReveal}>{t("study.practiceReveal")}</button>}{error ? <p role="alert" className="kq-study-page-error">{error}</p> : null}<button type="button" onClick={onExit}>{t("study.practiceExit")}</button></article>;
}

function QuizQuestion({ question, index, total, response, pending, error, onResponse, onPrevious, onNext, onSubmit, onGenerate }: { question: StudyQuizQuestion; index: number; total: number; response: Record<string, unknown>; pending: boolean; error: string; onResponse: (itemId: string, response: Record<string, unknown>) => void; onPrevious: () => void; onNext: () => void; onSubmit: () => void; onGenerate: (itemId: string, kind: "transcribe" | "variant") => void }) {
  const { t } = useI18n();
  const select = (selected: number[]) => onResponse(question.item_id, { selected });
  const derivationSteps = response.steps && typeof response.steps === "object" && !Array.isArray(response.steps)
    ? response.steps as Record<string, { expr?: string; expr_py?: string; justification?: string }>
    : {};
  const canGenerate = question.type === "code" || question.type === "derivation";
  const canGenerateVariant = question.type === "code" && question.language === "python";
  const unsupportedCode = question.type === "code" && Boolean(question.language && question.language !== "python");
  return <article id="study-practice-surface" className="kq-study-practice-surface" tabIndex={-1}><p>{t("study.practiceProgress", { current: index + 1, total })}</p><h2>{question.prompt}</h2>{question.type === "choice" ? <div className="kq-study-practice-options">{(question.options ?? []).map((option, optionIndex) => { const selected = Array.isArray(response.selected) ? response.selected as number[] : []; const active = selected.includes(optionIndex); return <button key={optionIndex} type="button" aria-pressed={active} onClick={() => select(question.multiple ? (active ? selected.filter((value) => value !== optionIndex) : [...selected, optionIndex]) : [optionIndex])}>{option}</button>; })}</div> : question.type === "true_false" ? <div className="kq-study-practice-options">{[true, false].map((value) => <button key={String(value)} type="button" aria-pressed={response.value === value} onClick={() => onResponse(question.item_id, { value })}>{value ? t("chat.quizTrue") : t("chat.quizFalse")}</button>)}</div> : question.type === "code" ? unsupportedCode ? <p>{t("study.practiceCodeUnsupported")}</p> : <Suspense fallback={<p role="status">{t("study.practiceEditorLoading")}</p>}><CodePracticeSurface key={`${question.item_id}:${question.mode ?? ""}`} starter={question.starter ?? ""} targetCode={question.mode === "transcribe" ? question.target_code : undefined} value={String(response.code ?? "")} onChange={(code) => onResponse(question.item_id, { code })} /></Suspense> : question.type === "derivation" ? <Suspense fallback={<p role="status">{t("study.practiceEditorLoading")}</p>}><DerivationPracticeSurface steps={question.steps ?? []} targetSteps={question.mode === "transcribe" ? question.target_steps : undefined} check={question.check} value={derivationSteps} onChange={(steps) => onResponse(question.item_id, { steps })} /></Suspense> : <textarea value={String(response.text ?? "")} onChange={(event) => onResponse(question.item_id, { text: event.currentTarget.value })} placeholder={t("study.practiceTextPlaceholder")} />}{error ? <p role="alert" className="kq-study-page-error">{error}</p> : null}<div className="kq-study-inline-actions">{canGenerate ? <button type="button" disabled={pending} onClick={() => onGenerate(question.item_id, "transcribe")}>{t("study.practiceGenerateTranscribe")}</button> : null}{canGenerateVariant ? <button type="button" disabled={pending} onClick={() => onGenerate(question.item_id, "variant")}>{t("study.practiceGenerateVariant")}</button> : null}<button type="button" disabled={index === 0 || pending} onClick={onPrevious}>{t("chat.quizPrev")}</button>{index + 1 < total ? <button type="button" disabled={pending} onClick={onNext}>{t("chat.quizNext")}</button> : <button type="button" disabled={pending} onClick={onSubmit}>{t("chat.quizSubmit")}</button>}</div></article>;
}

function QuizResult({ result, onRetry, onHome }: { result: StudyQuizResult; onRetry: () => void; onHome: () => void }) { const { t } = useI18n(); return <article id="study-practice-surface" className="kq-study-practice-surface" tabIndex={-1} aria-live="polite"><h2>{t("study.practiceResultTitle")}</h2><p>{t("chat.quizScore", { score: result.score, max: result.maxScore, percent: result.percent })}</p><p>{t("chat.quizCorrectCount", { correct: result.correctCount, total: result.total })}</p>{result.weakTags?.length ? <p>{t("study.practiceWeakTags", { tags: result.weakTags.join(" · ") })}</p> : null}<ol className="kq-study-practice-feedback">{result.perQuestion.map((question, index) => <li key={question.item_id}><strong>{t(question.ungraded ? "study.practiceUngraded" : question.correct ? "study.practiceCorrect" : "study.practiceIncorrect", { current: index + 1 })}</strong>{question.timed_out ? <span>{t("study.practiceTimedOut")}</span> : null}{question.ungraded_steps?.length ? <span>{t("study.practiceUngradedSteps", { steps: question.ungraded_steps.map((step) => step + 1).join(", ") })}</span> : null}{question.failure_summary ? <details><summary>{question.failure_kind || t("study.practiceFailure")}</summary><p>{question.failure_summary}</p></details> : null}</li>)}</ol><div className="kq-study-inline-actions"><button type="button" onClick={onRetry}>{t("study.practiceRetry")}</button><button type="button" onClick={onHome}>{t("study.practiceExit")}</button></div></article>; }
