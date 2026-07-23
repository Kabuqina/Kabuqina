// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { StudyPageSlug } from "../routeModel";
import { createFixtureDeskAdapter, type DeskAdapter } from "./deskAdapter";
import { defaultDeskArtAssets, type DeskArtAssets } from "./artAssets";
import { completedResult, needsRevisionResult } from "./deskFixtures";
import { DeskChrome } from "./DeskChrome";
import { DeskCup } from "./DeskCup";
import { DeskNotebook } from "./DeskNotebook";
import { DeskLeftObjects, DeskRightObjects } from "./DeskObjects";
import type { CheckResult, DeskData, DeskDensity, StudyActivity } from "./types";
import "./desk.css";

const SAVE_DEBOUNCE_MS = 260;
const COMPLETED_FIXTURE_ANSWER =
  "代入后得到 0/0。0/0 是未定式，不是极限值，所以还需要继续分析并做等价变形。";
const FUTURE_FEATURE_MESSAGE = "该功能将在后续版本开放。";
const FUTURE_CHAT_MESSAGE = "课程对话将在后续版本开放。";

type FixtureId = "d0" | "n0" | "a1" | "f0" | "f1";

function readFixtureParam(): FixtureId | null {
  if (!import.meta.env.DEV || typeof window === "undefined") return null;
  const value = new URLSearchParams(window.location.search).get("fixture");
  return value === "d0" || value === "n0" || value === "a1" || value === "f0" || value === "f1"
    ? value
    : null;
}

function stepSpeech(kicker: string): string {
  return kicker.replace(/ · /g, " ");
}

function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === "AbortError";
}

interface Announcement {
  id: number;
  text: string;
}

function Announcer({ announcement }: { announcement: Announcement | null }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el || !announcement) return;
    el.textContent = "";
    const raf = requestAnimationFrame(() => {
      el.textContent = announcement.text;
    });
    return () => cancelAnimationFrame(raf);
  }, [announcement]);
  return (
    <div
      ref={ref}
      className="kd-sr-only"
      role="status"
      aria-live="polite"
      data-testid="kd-announcer"
    />
  );
}

export interface DeskSceneProps {
  adapter?: DeskAdapter;
  art?: Partial<DeskArtAssets>;
  currentPage?: StudyPageSlug;
  onNavigatePage?: (page: StudyPageSlug) => void;
  onOpenChat?: () => void;
  onOpenActivity?: () => void;
  onOpenSettings?: () => void;
  onSelectSpace?: (spaceId: string) => void;
  onOpenMaterials?: () => void;
  onReviewCards?: () => void;
  onNewBook?: () => void;
  onDirtyChange?: (dirty: boolean) => void;
}

export default function DeskScene({
  adapter,
  art,
  currentPage = "practice",
  onNavigatePage,
  onOpenChat,
  onOpenActivity,
  onOpenSettings,
  onSelectSpace,
  onOpenMaterials,
  onReviewCards,
  onNewBook,
  onDirtyChange,
}: DeskSceneProps) {
  const deskAdapter = useMemo(() => adapter ?? createFixtureDeskAdapter(), [adapter]);
  const icons = useMemo<DeskArtAssets>(() => ({ ...defaultDeskArtAssets, ...art }), [art]);

  const [data, setData] = useState<DeskData | null>(null);
  const [loadError, setLoadError] = useState(false);
  const [reloadGeneration, setReloadGeneration] = useState(0);
  const [density, setDensity] = useState<DeskDensity>("overview");
  const [activity, setActivity] = useState<StudyActivity>("ready");
  const [stepIndex, setStepIndex] = useState(0);
  const [answer, setAnswer] = useState("");
  const [checkResult, setCheckResult] = useState<CheckResult | null>(null);
  const [saving, setSaving] = useState(false);
  const [operationError, setOperationError] = useState<string | null>(null);
  const [announcement, setAnnouncement] = useState<Announcement | null>(null);

  const taskSurfaceRef = useRef<HTMLElement>(null);
  const answerRef = useRef<HTMLDivElement>(null);
  const feedbackRef = useRef<HTMLDivElement>(null);
  const saveTimerRef = useRef<number | null>(null);
  const saveControllerRef = useRef<AbortController | null>(null);
  const checkControllerRef = useRef<AbortController | null>(null);
  const saveGenerationRef = useRef(0);
  const announcementIdRef = useRef(0);

  const announce = useCallback((text: string) => {
    announcementIdRef.current += 1;
    setAnnouncement({ id: announcementIdRef.current, text });
  }, []);

  const focusAfterPaint = useCallback((target: { current: { focus: () => void } | null }) => {
    requestAnimationFrame(() => {
      target.current?.focus();
    });
  }, []);

  const focusAnswerAfterPaint = useCallback(() => {
    requestAnimationFrame(() => {
      const root = answerRef.current;
      const target = root?.querySelector<HTMLElement>(
        "textarea, input, button:not(:disabled), [contenteditable='true']",
      );
      target?.focus();
    });
  }, []);

  const clearSaveTimer = useCallback(() => {
    if (saveTimerRef.current === null) return;
    window.clearTimeout(saveTimerRef.current);
    saveTimerRef.current = null;
  }, []);

  const saveDraft = useCallback(async (stepId: string, value: string) => {
    saveControllerRef.current?.abort();
    const controller = new AbortController();
    saveControllerRef.current = controller;
    const generation = ++saveGenerationRef.current;
    setSaving(true);
    try {
      await deskAdapter.saveDraft(stepId, value, controller.signal);
      if (generation !== saveGenerationRef.current || controller.signal.aborted) return;
      setSaving(false);
      setOperationError(null);
    } catch (error) {
      if (generation !== saveGenerationRef.current || isAbortError(error)) return;
      setSaving(false);
      setOperationError("草稿暂时没有保存成功，请稍后再试。");
    }
  }, [deskAdapter]);

  useEffect(() => {
    const controller = new AbortController();
    setData(null);
    setLoadError(false);
    setOperationError(null);
    void deskAdapter.loadDesk(controller.signal).then((deskData) => {
      if (controller.signal.aborted) return;
      const initialIndex = Math.min(
        Math.max(deskData.initialStepIndex ?? 0, 0),
        deskData.steps.length - 1,
      );
      const step = deskData.steps[initialIndex];
      if (!step) {
        setLoadError(true);
        return;
      }
      setData(deskData);
      setStepIndex(initialIndex);
      deskAdapter.markCurrentStep?.(step.id);

      const fixture = readFixtureParam();
      setDensity(fixture === null || fixture === "d0" ? "overview" : "focused");
      setActivity(
        fixture === "a1"
          ? "dirty"
          : fixture === "f0"
            ? "needs_revision"
            : fixture === "f1"
              ? "completed"
              : "ready",
      );
      setAnswer(fixture === "f1" ? COMPLETED_FIXTURE_ANSWER : step.initialDraft);
      setCheckResult(
        fixture === "f0"
          ? needsRevisionResult
          : fixture === "f1"
            ? completedResult
            : null,
      );
    }).catch((error) => {
      if (!controller.signal.aborted && !isAbortError(error)) setLoadError(true);
    });
    return () => controller.abort();
  }, [deskAdapter, reloadGeneration]);

  const shouldProtectLeave =
    activity === "dirty" || activity === "checking" || activity === "needs_revision";

  useEffect(() => {
    onDirtyChange?.(shouldProtectLeave);
  }, [onDirtyChange, shouldProtectLeave]);

  useEffect(() => {
    if (!shouldProtectLeave) return;
    const beforeUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", beforeUnload);
    return () => window.removeEventListener("beforeunload", beforeUnload);
  }, [shouldProtectLeave]);

  useEffect(() => () => {
    clearSaveTimer();
    saveControllerRef.current?.abort();
    checkControllerRef.current?.abort();
    onDirtyChange?.(false);
  }, [clearSaveTimer, onDirtyChange]);

  const announceFutureFeature = useCallback(() => announce(FUTURE_FEATURE_MESSAGE), [announce]);
  const announceFutureChat = useCallback(() => announce(FUTURE_CHAT_MESSAGE), [announce]);

  const handleResume = useCallback(() => {
    setDensity("focused");
    const step = data?.steps[stepIndex];
    if (step) {
      deskAdapter.markCurrentStep?.(step.id);
      announce(`已翻到${stepSpeech(step.kicker)}。`);
    }
    focusAfterPaint(taskSurfaceRef);
  }, [announce, data, deskAdapter, focusAfterPaint, stepIndex]);

  const handleStartWriting = useCallback(() => {
    setActivity("dirty");
    setOperationError(null);
    announce("可以继续写这一步。");
    focusAnswerAfterPaint();
  }, [announce, focusAnswerAfterPaint]);

  const handleAnswerChange = useCallback((value: string) => {
    setAnswer(value);
    setActivity("dirty");
    setCheckResult(null);
    setOperationError(null);
    clearSaveTimer();
    const stepId = data?.steps[stepIndex]?.id;
    if (!stepId) return;
    try {
      deskAdapter.persistDraft?.(stepId, value);
    } catch {
      setOperationError("草稿暂时没有保存成功，请稍后再试。");
    }
    saveTimerRef.current = window.setTimeout(() => {
      saveTimerRef.current = null;
      void saveDraft(stepId, value);
    }, SAVE_DEBOUNCE_MS);
  }, [clearSaveTimer, data, deskAdapter, saveDraft, stepIndex]);

  const handleCheck = useCallback(() => {
    const step = data?.steps[stepIndex];
    if (!step || activity === "checking") return;
    clearSaveTimer();
    saveControllerRef.current?.abort();
    saveGenerationRef.current += 1;
    checkControllerRef.current?.abort();
    const controller = new AbortController();
    checkControllerRef.current = controller;
    setSaving(true);
    setActivity("checking");
    setOperationError(null);
    announce("正在检查这一步。");

    void (async () => {
      try {
        await deskAdapter.saveDraft(step.id, answer, controller.signal);
        if (controller.signal.aborted) return;
        setSaving(false);
        const result = await deskAdapter.checkAnswer(step.id, answer, controller.signal);
        if (controller.signal.aborted) return;
        setCheckResult(result);
        setActivity(result.verdict);
        announce(result.verdict === "completed" ? "本步完成。" : "需要修改：还差一步。");
        focusAfterPaint(feedbackRef);
      } catch (error) {
        if (controller.signal.aborted || isAbortError(error)) return;
        setSaving(false);
        setActivity("dirty");
        setOperationError("暂时无法检查这一步；原答案仍在纸页上，请稍后再试。");
        announce("检查没有完成，答案仍在原位。");
      }
    })();
  }, [activity, announce, answer, clearSaveTimer, data, deskAdapter, focusAfterPaint, stepIndex]);

  const handleModify = useCallback(() => {
    setActivity("dirty");
    setOperationError(null);
    announce("继续修改原答案。");
    focusAnswerAfterPaint();
  }, [announce, focusAnswerAfterPaint]);

  const handleNextStep = useCallback(() => {
    if (!data) return;
    if (stepIndex + 1 >= data.steps.length) {
      setDensity("overview");
      setActivity("ready");
      setCheckResult(null);
      announce("本练习已完成，回到练习总览。");
      return;
    }
    const nextIndex = stepIndex + 1;
    const next = data.steps[nextIndex];
    clearSaveTimer();
    saveControllerRef.current?.abort();
    setStepIndex(nextIndex);
    setDensity("focused");
    setActivity("ready");
    setAnswer(next.initialDraft);
    setCheckResult(null);
    setSaving(false);
    setOperationError(null);
    deskAdapter.markCurrentStep?.(next.id);
    announce(`已进入${stepSpeech(next.kicker)}。`);
    focusAfterPaint(taskSurfaceRef);
  }, [announce, clearSaveTimer, data, deskAdapter, focusAfterPaint, stepIndex]);

  const chrome = (
    <DeskChrome
      art={icons}
      onFutureFeature={announceFutureFeature}
      onOpenChat={onOpenChat}
      onOpenActivity={onOpenActivity}
      onOpenSettings={onOpenSettings}
    />
  );

  if (!data) {
    return (
      <div className="kq-desk" data-density="overview">
        {chrome}
        <div className="kd-canvas">
          <main className="kd-desk kd-load-layout">
            <section className="kd-load-card" role={loadError ? "alert" : "status"}>
              <p className="kd-page-kicker">学习书桌</p>
              <h1>{loadError ? "这本笔记本暂时没有打开" : "正在打开你的笔记本…"}</h1>
              <p>
                {loadError
                  ? "课程与草稿都没有被改动。可以再试一次。"
                  : "正在整理当前练习和上次留下的草稿。"}
              </p>
              {loadError ? (
                <button
                  type="button"
                  className="kd-primary"
                  onClick={() => setReloadGeneration((value) => value + 1)}
                >
                  再试一次
                </button>
              ) : null}
            </section>
          </main>
        </div>
        <Announcer announcement={announcement} />
      </div>
    );
  }

  const step = data.steps[stepIndex];
  const hasDraft = answer.trim() !== "";
  const hasNextStep = stepIndex + 1 < data.steps.length;
  const answerStateText =
    activity === "completed"
      ? "已落墨"
      : activity === "checking"
        ? "保持原答案"
        : activity === "dirty" || activity === "needs_revision"
          ? "我的草稿"
          : hasDraft
            ? "已保存的草稿"
            : "尚未开始";

  const saveStatusText =
    activity === "checking"
      ? "正在检查这一步…答案仍留在原位"
      : activity === "completed"
        ? "本步学习证据已保存"
        : activity === "dirty" && saving
          ? "正在保存草稿…"
          : !hasDraft && activity === "ready"
            ? "这一步还没有草稿"
            : "草稿已保存在这本笔记本中";

  return (
    <div className="kq-desk" data-density={density}>
      {chrome}
      <div className="kd-canvas">
        <main className="kd-desk">
          <section className="kd-center-stage" aria-label="当前课程笔记本">
            <DeskNotebook
              art={icons}
              course={data.course}
              overview={data.overview}
              step={step}
              density={density}
              activity={activity}
              answer={answer}
              answerStateText={answerStateText}
              saveStatusText={saveStatusText}
              operationError={operationError}
              checkResult={checkResult}
              currentPage={currentPage}
              hasNextStep={hasNextStep}
              taskSurfaceRef={taskSurfaceRef}
              answerRef={answerRef}
              feedbackRef={feedbackRef}
              onResume={handleResume}
              onStartWriting={handleStartWriting}
              onAnswerChange={handleAnswerChange}
              onCheck={handleCheck}
              onModify={handleModify}
              onAskTutor={onOpenChat ?? announceFutureChat}
              onNextStep={handleNextStep}
              onNavigatePage={onNavigatePage}
              onFutureFeature={announceFutureFeature}
            />
            <button type="button" className="kd-work-folder" onClick={announceFutureFeature}>
              <icons.folderPlus /> ＋ 制作 / 成果
            </button>
          </section>
          <aside className="kd-right-objects" aria-label="复习卡片与小娜">
            <DeskRightObjects
              art={icons}
              bookstand={data.bookstand}
              materials={data.materials}
              dueCount={data.dueCount}
              onFutureFeature={announceFutureFeature}
              onReviewCards={onReviewCards}
            />
            <DeskCup art={icons} onAskTutor={onOpenChat ?? announceFutureChat} />
          </aside>
          <DeskLeftObjects
            art={icons}
            bookstand={data.bookstand}
            materials={data.materials}
            dueCount={data.dueCount}
            onFutureFeature={announceFutureFeature}
            onSelectSpace={onSelectSpace}
            onOpenMaterials={onOpenMaterials}
            onNewBook={onNewBook}
          />
        </main>
      </div>
      <Announcer announcement={announcement} />
    </div>
  );
}
