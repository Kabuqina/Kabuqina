// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import type { StudyPageSlug } from "../routeModel";
import type { StudyKnowledgePoint } from "../../chat/study/study-api";
import type { DeskAdapter } from "./deskAdapter";
import { defaultDeskArtAssets, type DeskArtAssets } from "./artAssets";
import { onOpenActivityRequest } from "../../shell/activityBridge";
import { DeskActivityPanel } from "./DeskActivityPanel";
import { DeskCardReview, type DeskCardGrade } from "./DeskCardReview";
import { DeskCup } from "./DeskCup";
import { DeskNotebook } from "./DeskNotebook";
import { DeskBookend } from "./DeskBookend";
import { DeskRightObjects } from "./DeskObjects";
import type { DeskCourseChatRequest } from "./DeskTutorInvoke";
import { DeskWorkFolder, type DeskCreateChatRequest } from "./DeskWorkFolder";
import type { CheckResult, DeskBookstand, DeskData, DeskDensity, StudyActivity } from "./types";
import type { StudyReturnState } from "../../lib/studyChatHandoff";
import "./desk.css";

const SAVE_DEBOUNCE_MS = 260;
const FUTURE_FEATURE_MESSAGE = "该功能将在后续版本开放。";
const FUTURE_CHAT_MESSAGE = "课程对话将在后续版本开放。";

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
  adapter: DeskAdapter;
  initialSnapshot?: {
    density?: DeskDensity;
    activity?: StudyActivity;
    answer?: string;
    checkResult?: CheckResult | null;
  };
  art?: Partial<DeskArtAssets>;
  currentPage?: StudyPageSlug;
  /**
   * 非练习分页的正文。五个分页共用同一本本子，所以书桌不是"练习专用"的——
   * 扉页 / 计划 / 学习 / 评估 由 `StudyShell` 把 `StudyPageOutlet` 传进来铺在本子里。
   */
  pageBody?: ReactNode;
  /**
   * 草稿箱（「等你过目」）。原型把待审核的东西归在 Activity 里，S10 会把它搬过去；
   * 在那之前它安静地待在书桌右栏，**不能因为重排 IA 就把一个能用的功能弄丢**。
   */
  draftInbox?: ReactNode;
  /** 不依赖网络的课程列表：练习数据打不开时，书立与换课仍要能用。 */
  bookstandFallback?: DeskBookstand & { currentTitle: string };
  switchingSpace?: boolean;
  onNavigatePage?: (page: StudyPageSlug) => void;
  onImportMaterial?: () => void;
  onOpenChatSession?: (sessionId: string) => void;
  onStartCourseChat?: (request: DeskCourseChatRequest) => void;
  onStartCreateChat?: (request: DeskCreateChatRequest) => void;
  onOpenActivity?: () => void;
  onSelectSpace?: (spaceId: string) => void;
  onOpenMaterials?: (materialId?: string) => void;
  onRemoveMaterial?: (materialId: string, title: string) => void;
  onReviewCards?: () => void;
  onNewBook?: () => void;
  onDirtyChange?: (dirty: boolean) => void;
  returnFocus?: StudyReturnState | null;
  continueTitle?: string;
  continueMeta?: string;
  pageNotice?: string;
  onResumeLocation?: () => void;
  onChangeKnowledgeCore?: (point: StudyKnowledgePoint, index: number) => void;
  onBackToLearn?: () => void;
  onAskPage?: (request?: DeskCourseChatRequest) => void;
}

export default function DeskScene({
  adapter,
  initialSnapshot,
  art,
  currentPage = "practice",
  pageBody,
  draftInbox,
  bookstandFallback,
  switchingSpace,
  onNavigatePage,
  onImportMaterial,
  onOpenChatSession,
  onStartCourseChat,
  onStartCreateChat,
  onOpenActivity,
  onSelectSpace,
  onOpenMaterials,
  onRemoveMaterial,
  onReviewCards,
  onNewBook,
  onDirtyChange,
  returnFocus,
  continueTitle,
  continueMeta,
  pageNotice,
  onResumeLocation,
  onChangeKnowledgeCore,
  onBackToLearn,
  onAskPage,
}: DeskSceneProps) {
  const deskAdapter = adapter;
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
  const [panel, setPanel] = useState<"work" | "activity" | "cards" | null>(null);
  const [stackIndexOpen, setStackIndexOpen] = useState(false);
  const [initialMaterialId, setInitialMaterialId] = useState<string | null>(null);
  const [cardIndex, setCardIndex] = useState(0);
  const [cardPending, setCardPending] = useState(false);
  const [cardError, setCardError] = useState<string | null>(null);
  const [activityLoading, setActivityLoading] = useState(false);
  const [activityLoadError, setActivityLoadError] = useState(false);

  const taskSurfaceRef = useRef<HTMLElement>(null);
  const answerRef = useRef<HTMLDivElement>(null);
  const feedbackRef = useRef<HTMLDivElement>(null);
  const saveTimerRef = useRef<number | null>(null);
  const saveControllerRef = useRef<AbortController | null>(null);
  const checkControllerRef = useRef<AbortController | null>(null);
  const cardControllerRef = useRef<AbortController | null>(null);
  const activityControllerRef = useRef<AbortController | null>(null);
  const saveGenerationRef = useRef(0);
  const announcementIdRef = useRef(0);
  const returnFocusHandledRef = useRef(false);

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

  const saveDraft = useCallback(async (stepId: string, value: string): Promise<boolean> => {
    saveControllerRef.current?.abort();
    const controller = new AbortController();
    saveControllerRef.current = controller;
    const generation = ++saveGenerationRef.current;
    setSaving(true);
    try {
      await deskAdapter.saveDraft(stepId, value, controller.signal);
      if (generation !== saveGenerationRef.current || controller.signal.aborted) return false;
      setSaving(false);
      setOperationError(null);
      return true;
    } catch (error) {
      if (generation !== saveGenerationRef.current || isAbortError(error)) return false;
      setSaving(false);
      setOperationError("草稿暂时没有保存成功，请稍后再试。");
      return false;
    }
  }, [deskAdapter]);

  useEffect(() => {
    const controller = new AbortController();
    setData(null);
    setLoadError(false);
    setOperationError(null);
    void deskAdapter.loadDesk(controller.signal).then((deskData) => {
      if (controller.signal.aborted) return;
      const requestedIndex = returnFocus
        ? deskData.steps.findIndex((candidate) => candidate.id === returnFocus.stepId)
        : -1;
      const initialIndex = Math.min(
        Math.max(requestedIndex >= 0 ? requestedIndex : deskData.initialStepIndex ?? 0, 0),
        deskData.steps.length - 1,
      );
      const step = deskData.steps[initialIndex];
      if (!step) {
        setData(deskData);
        setStepIndex(0);
        setDensity("overview");
        setActivity("ready");
        setAnswer("");
        setCheckResult(null);
        return;
      }
      setData(deskData);
      setStepIndex(initialIndex);
      deskAdapter.markCurrentStep?.(step.id);

      const returnedSnapshot = requestedIndex >= 0 ? returnFocus?.deskSnapshot : undefined;
      setDensity(returnFocus && requestedIndex >= 0 ? "focused" : initialSnapshot?.density ?? "overview");
      setActivity(returnedSnapshot?.activity ?? initialSnapshot?.activity ?? step.initialActivity ?? "ready");
      setAnswer(returnedSnapshot?.answer ?? initialSnapshot?.answer ?? step.initialDraft);
      setCheckResult(returnedSnapshot?.checkResult ?? initialSnapshot?.checkResult ?? step.initialCheckResult ?? null);
      if (returnFocus && requestedIndex >= 0 && !returnFocusHandledRef.current) {
        returnFocusHandledRef.current = true;
        requestAnimationFrame(() => {
          requestAnimationFrame(() => {
            if (returnFocus.focus === "answer") focusAnswerAfterPaint();
            else focusAfterPaint(taskSurfaceRef);
            announce(`已返回${stepSpeech(step.kicker)}，原答案仍在原位。`);
          });
        });
      }
    }).catch((error) => {
      if (!controller.signal.aborted && !isAbortError(error)) setLoadError(true);
    });
    return () => controller.abort();
  }, [
    announce,
    deskAdapter,
    focusAfterPaint,
    focusAnswerAfterPaint,
    initialSnapshot,
    reloadGeneration,
    returnFocus,
  ]);

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
    cardControllerRef.current?.abort();
    activityControllerRef.current?.abort();
    onDirtyChange?.(false);
  }, [clearSaveTimer, onDirtyChange]);

  const announceFutureFeature = useCallback(() => announce(FUTURE_FEATURE_MESSAGE), [announce]);
  const announceFutureChat = useCallback(() => announce(FUTURE_CHAT_MESSAGE), [announce]);

  const openTutorInvoke = useCallback((_invokerId: string) => {
    if (currentPage !== "practice" || !data?.steps[stepIndex]) {
      if (onAskPage) onAskPage();
      else announce("当前页面的课程上下文还没有准备好。");
      return;
    }
    if (activity === "checking") {
      announce("请等这一步检查完成后再问小娜。");
      return;
    }
    const step = data.steps[stepIndex];
    const feedback = checkResult
      ? [checkResult.good, checkResult.gap, checkResult.next].filter(Boolean).join(" ")
      : "";
    const request: DeskCourseChatRequest = {
      focusId: step.id,
      focusLabel: step.kicker,
      prompt: step.prompt,
      answer,
      feedback,
      question: "",
      activity,
      checkResult,
    };
    if (onAskPage) onAskPage(request);
    else if (onStartCourseChat) onStartCourseChat(request);
    else announceFutureChat();
    announce("小娜已在当前学习页旁边展开。");
  }, [activity, announce, announceFutureChat, answer, checkResult, currentPage, data, onAskPage, onStartCourseChat, stepIndex]);

  const closePanel = useCallback(() => {
    cardControllerRef.current?.abort();
    setCardPending(false);
    setCardError(null);
    setPanel(null);
    announce("已回到书桌。");
    requestAnimationFrame(() => document.getElementById("kd-notebook-surface")?.focus());
  }, [announce]);

  const openWorkFolder = useCallback((materialId?: string) => {
    setInitialMaterialId(materialId ?? null);
    setPanel("work");
    announce("已打开工作夹；先确认材料与制作目标。");
  }, [announce]);

  const refreshActivities = useCallback(() => {
    if (!deskAdapter.loadActivities) return;
    activityControllerRef.current?.abort();
    const controller = new AbortController();
    activityControllerRef.current = controller;
    setActivityLoading(true);
    setActivityLoadError(false);
    void deskAdapter.loadActivities(controller.signal).then((items) => {
      if (controller.signal.aborted) return;
      setActivityLoading(false);
      setData((current) => current ? {
        ...current,
        activities: items,
        activitiesUnavailable: false,
      } : current);
    }).catch((error) => {
      if (isAbortError(error)) return;
      setActivityLoading(false);
      setActivityLoadError(true);
    });
  }, [deskAdapter]);

  const openActivityPanel = useCallback(() => {
    setPanel("activity");
    announce("已打开这本课程的学习动态。");
    refreshActivities();
  }, [announce, refreshActivities]);

  // 入口搬到了全局页眉（架构 §5.4）；书桌只负责响应。
  useEffect(() => onOpenActivityRequest(openActivityPanel), [openActivityPanel]);

  const openCardReview = useCallback(() => {
    if (!data?.dueCards.length || data.cardsUnavailable) {
      announce(data?.cardsUnavailable ? "复习卡片暂时无法读取。" : "今天没有到期卡片。");
      return;
    }
    setCardIndex(0);
    setCardError(null);
    setPanel("cards");
    announce(`开始复习，共 ${data.dueCards.length} 张到期卡片。`);
  }, [announce, data]);

  const reviewCard = useCallback((grade: DeskCardGrade) => {
    const card = data?.dueCards[cardIndex];
    if (!card || cardPending || !deskAdapter.reviewCard) return;
    const controller = new AbortController();
    cardControllerRef.current?.abort();
    cardControllerRef.current = controller;
    setCardPending(true);
    setCardError(null);
    void deskAdapter.reviewCard(card.item_id, grade, controller.signal).then(() => {
      if (controller.signal.aborted) return;
      setCardPending(false);
      if (!data) return;
      if (cardIndex + 1 >= data.dueCards.length) {
        setData({ ...data, dueCards: [], dueCount: 0 });
        setPanel(null);
        announce("今日到期卡片已经复习完成。");
        requestAnimationFrame(() => document.getElementById("kd-notebook-surface")?.focus());
      } else {
        setCardIndex((index) => index + 1);
        announce("复习结果已保存，进入下一张。");
      }
    }).catch((error) => {
      if (isAbortError(error)) return;
      setCardPending(false);
      setCardError("复习结果暂时没有保存，请重试；当前卡片仍在原位。");
    });
  }, [announce, cardIndex, cardPending, data, deskAdapter]);

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
    const stepId = data?.steps[stepIndex]?.id;
    if (stepId) deskAdapter.markPracticeState?.(stepId, "dirty");
    announce("可以继续写这一步。");
    focusAnswerAfterPaint();
  }, [announce, data, deskAdapter, focusAnswerAfterPaint, stepIndex]);

  const handleAnswerChange = useCallback((value: string) => {
    const isRevisingCheckedAnswer = activity === "needs_revision" && checkResult !== null;
    setAnswer(value);
    if (!isRevisingCheckedAnswer) {
      setActivity("dirty");
      setCheckResult(null);
    }
    setOperationError(null);
    clearSaveTimer();
    const stepId = data?.steps[stepIndex]?.id;
    if (!stepId) return;
    try {
      deskAdapter.persistDraft?.(stepId, value);
      deskAdapter.markPracticeState?.(
        stepId,
        isRevisingCheckedAnswer ? "needs_revision" : "dirty",
        isRevisingCheckedAnswer ? checkResult : null,
      );
    } catch {
      setOperationError("草稿暂时没有保存成功，请稍后再试。");
    }
    saveTimerRef.current = window.setTimeout(() => {
      saveTimerRef.current = null;
      void saveDraft(stepId, value);
    }, SAVE_DEBOUNCE_MS);
  }, [activity, checkResult, clearSaveTimer, data, deskAdapter, saveDraft, stepIndex]);

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
    deskAdapter.markPracticeState?.(step.id, "checking");
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
        deskAdapter.markPracticeState?.(step.id, result.verdict, result);
        announce(result.verdict === "completed" ? "本步完成。" : "需要修改：还差一步。");
        focusAfterPaint(feedbackRef);
      } catch (error) {
        if (controller.signal.aborted || isAbortError(error)) return;
        setSaving(false);
        setActivity("dirty");
        deskAdapter.markPracticeState?.(step.id, "dirty");
        setOperationError("暂时无法检查这一步；原答案仍在纸页上，请稍后再试。");
        announce("检查没有完成，答案仍在原位。");
      }
    })();
  }, [activity, announce, answer, clearSaveTimer, data, deskAdapter, focusAfterPaint, stepIndex]);

  const handleSaveAnswer = useCallback(() => {
    const stepId = data?.steps[stepIndex]?.id;
    if (!stepId || saving) return;
    clearSaveTimer();
    void saveDraft(stepId, answer).then((saved) => {
      if (!saved) return;
      setActivity("dirty");
      setCheckResult(null);
      deskAdapter.markPracticeState?.(stepId, "dirty");
      announce("答案已保存，可以再次检查。");
      focusAnswerAfterPaint();
    });
  }, [answer, announce, clearSaveTimer, data, deskAdapter, focusAnswerAfterPaint, saveDraft, saving, stepIndex]);

  const moveToStep = useCallback((nextIndex: number) => {
    if (!data || activity === "checking") return;
    const current = data.steps[stepIndex];
    const next = data.steps[nextIndex];
    if (!current || !next || nextIndex === stepIndex) return;
    clearSaveTimer();
    saveControllerRef.current?.abort();
    saveGenerationRef.current += 1;
    try {
      deskAdapter.persistDraft?.(current.id, answer);
      deskAdapter.markPracticeState?.(current.id, activity, checkResult);
    } catch {
      setOperationError("草稿暂时没有保存成功，请稍后再试。");
      return;
    }
    setData((existing) => existing ? {
      ...existing,
      steps: existing.steps.map((candidate, index) => index === stepIndex ? {
        ...candidate,
        initialDraft: answer,
        initialActivity: activity,
        initialCheckResult: checkResult,
      } : candidate),
    } : existing);
    setStepIndex(nextIndex);
    setDensity("focused");
    setActivity(next.initialActivity ?? (next.initialDraft ? "dirty" : "ready"));
    setAnswer(next.initialDraft);
    setCheckResult(next.initialCheckResult ?? null);
    setSaving(false);
    setOperationError(null);
    deskAdapter.markCurrentStep?.(next.id);
    announce(`已进入${stepSpeech(next.kicker)}。`);
    focusAfterPaint(taskSurfaceRef);
  }, [activity, announce, answer, checkResult, clearSaveTimer, data, deskAdapter, focusAfterPaint, stepIndex]);

  const handlePreviousStep = useCallback(() => {
    if (stepIndex <= 0) return;
    moveToStep(stepIndex - 1);
  }, [moveToStep, stepIndex]);

  const handleNextStep = useCallback(() => {
    if (!data || activity === "checking") return;
    if (stepIndex + 1 >= data.steps.length) {
      setDensity("overview");
      setActivity("ready");
      setCheckResult(null);
      announce("本练习已完成，回到练习总览。");
      return;
    }
    moveToStep(stepIndex + 1);
  }, [activity, announce, data, moveToStep, stepIndex]);

  /**
   * 练习数据打不开时，**只有练习那一页该受影响**。
   *
   * `loadDesk` 在这门课还没有可用测验时就会抛错（`no active quiz`）。如果让它决定
   * 整张书桌在不在，一门刚建、还没出题的课就会连扉页、计划、学习、评估一起打不开——
   * 那不是诚实，是把一个局部缺失说成全盘不可用。所以在承载其它分页时，书桌照常摊开，
   * 只是本子里那一页说清练习还没准备好。
   */
  if (!data && pageBody && bookstandFallback) {
    return (
      <div className="kq-desk" data-density="overview">
        <div className="kd-canvas">
          <main className="kd-desk">
            <DeskBookend
              art={icons}
              bookstand={bookstandFallback}
              disabled={switchingSpace}
              onSelectSpace={onSelectSpace}
              onNewBook={onNewBook}
              onFutureFeature={announceFutureFeature}
            />
            <section className="kd-center-stage" aria-label="当前课程笔记本">
              <DeskNotebook
                art={icons}
                density="overview"
                activity="ready"
                answer=""
                saveStatusText=""
                operationError={null}
                checkResult={null}
                currentPage={currentPage}
                pageBody={pageBody}
                hasPreviousStep={false}
                hasNextStep={false}
                taskSurfaceRef={taskSurfaceRef}
                answerRef={answerRef}
                feedbackRef={feedbackRef}
                onResume={() => undefined}
                onStartWriting={() => undefined}
                onAnswerChange={() => undefined}
                onCheck={() => undefined}
                onSaveAnswer={() => undefined}
                onPreviousStep={() => undefined}
                onNextStep={() => undefined}
                onNavigatePage={onNavigatePage}
                onFutureFeature={announceFutureFeature}
              />
            </section>
            <aside className="kd-right-objects" aria-label="参考资料、复习与小娜">
              {draftInbox ? <div className="kd-rail-drafts">{draftInbox}</div> : null}
              <DeskRightObjects
                art={icons}
                materials={{ title: "参考资料", hint: "", items: [], unavailable: loadError }}
                dueCount={0}
                stackIndexOpen={false}
                onToggleStackIndex={() => undefined}
                onFutureFeature={announceFutureFeature}
                onImportMaterial={onImportMaterial}
              />
              <DeskCup art={icons} onAskTutor={announceFutureFeature} />
            </aside>
          </main>
        </div>
        <Announcer announcement={announcement} />
      </div>
    );
  }

  if (!data) {
    return (
      <div className="kq-desk" data-density="overview">
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
  const saveStatusText =
    activity === "checking"
      ? "正在检查这一步…答案仍留在原位"
      : activity === "completed"
        ? "本步学习证据已保存"
        : (activity === "dirty" || activity === "needs_revision") && saving
          ? "正在保存草稿…"
          : !hasDraft && activity === "ready"
            ? "这一步还没有草稿"
            : "草稿已保存在这本笔记本中";

  if (panel === "work") {
    return (
      <div className="kq-desk" data-density="focused">
          <div className="kd-canvas">
          <DeskWorkFolder
            courseName={data.course.name}
            materials={data.materials}
            initialSourceId={initialMaterialId}
            onCreate={(request) => {
              if (onStartCreateChat) onStartCreateChat({ ...request, focusId: step?.id ?? `course:${currentPage}` });
              else announceFutureChat();
            }}
            onOpenMaterials={onOpenMaterials}
            onClose={closePanel}
          />
        </div>
        <Announcer announcement={announcement} />
      </div>
    );
  }

  if (panel === "activity") {
    return (
      <div className="kq-desk" data-density="focused">
          <div className="kd-canvas">
          <DeskActivityPanel
            activities={data.activities}
            unavailable={data.activitiesUnavailable}
            loading={activityLoading}
            error={activityLoadError}
            spaceId={data.bookstand.books.find((book) => book.current)?.id ?? ""}
            onOpenFull={onOpenActivity}
            onOpenChatSession={onOpenChatSession}
            onRetryStudy={() => {
              refreshActivities();
            }}
            onClose={closePanel}
          />
        </div>
        <Announcer announcement={announcement} />
      </div>
    );
  }

  const reviewCardData = data.dueCards[cardIndex];
  if (panel === "cards" && reviewCardData) {
    return (
      <div className="kq-desk" data-density="focused">
          <div className="kd-canvas">
          <DeskCardReview
            card={reviewCardData}
            index={cardIndex}
            total={data.dueCards.length}
            pending={cardPending}
            error={cardError}
            onGrade={reviewCard}
            onClose={closePanel}
          />
        </div>
        <Announcer announcement={announcement} />
      </div>
    );
  }

  return (
    <div className="kq-desk" data-density={density}>
      <div className="kd-canvas">
        <main className="kd-desk">
          {/* 书立在本子的上边缘：换课＝换一本本子（原型 `Bookend`）。 */}
          <DeskBookend
            art={icons}
            bookstand={data.bookstand}
            disabled={switchingSpace}
            onSelectSpace={onSelectSpace}
            onNewBook={onNewBook}
            onFutureFeature={announceFutureFeature}
          />
          <section className="kd-center-stage" aria-label="当前课程笔记本">
            <DeskNotebook
              art={icons}
              overview={data.overview}
              step={step}
              density={density}
              activity={activity}
              answer={answer}
              saveStatusText={saveStatusText}
              operationError={operationError}
              checkResult={checkResult}
              currentPage={currentPage}
              pageBody={pageBody}
              continueTitle={continueTitle ?? data.knowledgeCores[data.activeKnowledgeCoreIndex]?.front ?? step?.title}
              continueMeta={continueMeta ?? (data.knowledgeCores.length ? "当前知识核 · 练习" : step?.kicker)}
              pageNotice={pageNotice}
              knowledgeCoreTitle={data.knowledgeCores[data.activeKnowledgeCoreIndex]?.front}
              knowledgeCoreIndex={data.activeKnowledgeCoreIndex}
              knowledgeCoreTotal={data.knowledgeCores.length}
              hasPreviousStep={stepIndex > 0}
              hasNextStep={hasNextStep}
              taskSurfaceRef={taskSurfaceRef}
              answerRef={answerRef}
              feedbackRef={feedbackRef}
              onResume={currentPage === "practice" ? handleResume : onResumeLocation ?? handleResume}
              onStartWriting={handleStartWriting}
              onAnswerChange={handleAnswerChange}
              onCheck={handleCheck}
              onSaveAnswer={handleSaveAnswer}
              onPreviousStep={handlePreviousStep}
              onNextStep={handleNextStep}
              onPreviousKnowledgeCore={data.activeKnowledgeCoreIndex > 0 && onChangeKnowledgeCore
                ? () => onChangeKnowledgeCore(
                    data.knowledgeCores[data.activeKnowledgeCoreIndex - 1],
                    data.activeKnowledgeCoreIndex - 1,
                  )
                : undefined}
              onNextKnowledgeCore={data.activeKnowledgeCoreIndex + 1 < data.knowledgeCores.length && onChangeKnowledgeCore
                ? () => onChangeKnowledgeCore(
                    data.knowledgeCores[data.activeKnowledgeCoreIndex + 1],
                    data.activeKnowledgeCoreIndex + 1,
                  )
                : undefined}
              onBackToLearn={onBackToLearn}
              onNavigatePage={onNavigatePage}
              onFutureFeature={announceFutureFeature}
            />
          </section>
          <aside className="kd-right-objects" aria-label="参考资料、复习与小娜">
            {draftInbox ? <div className="kd-rail-drafts">{draftInbox}</div> : null}
            <DeskRightObjects
              art={icons}
              materials={data.materials}
              dueCount={data.dueCount}
              stackIndexOpen={stackIndexOpen}
              onToggleStackIndex={() => setStackIndexOpen((open) => !open)}
              onFutureFeature={announceFutureFeature}
              onOpenMaterials={onOpenMaterials ?? openWorkFolder}
              onRemoveMaterial={onRemoveMaterial}
              onImportMaterial={onImportMaterial}
              onReviewCards={onReviewCards ?? openCardReview}
            />
            <DeskCup art={icons} onAskTutor={() => openTutorInvoke("kd-cup-chat")} />
          </aside>
          {/* 窄窗（720×520）下右栏收起来，三件事退成一条工具条，谁都不藏。 */}
          <nav className="kd-narrow-tools" aria-label="窄窗书桌工具">
            <button
              type="button"
              onClick={() => (onOpenMaterials ?? openWorkFolder)(data.materials.items[0]?.id)}
            >
              <icons.layers /> 参考
            </button>
            <button type="button" onClick={onReviewCards ?? openCardReview}>
              <icons.archive /> 卡片
            </button>
            <button type="button" onClick={() => openTutorInvoke("kd-cup-chat")}>
              <icons.coffee /> 小娜
            </button>
          </nav>
        </main>
      </div>
      <Announcer announcement={announcement} />
    </div>
  );
}
