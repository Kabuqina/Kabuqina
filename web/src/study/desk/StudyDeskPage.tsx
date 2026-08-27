// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import {
  buildStudyChatPrompt,
  getStudyReturnState,
  resolveStudyChatSessionId,
  type StudyChatHandoff,
  type StudyChatHandoffV2,
  type StudyNanaPage,
} from "../../lib/studyChatHandoff";
import { useStudyRepository } from "../repositoryContext";
import { studyPath, type StudyPageSlug, type StudySurfaceSlug } from "../routeModel";
import type { StudyOutlineNode, StudySpaceSummary } from "../repository";
import DeskScene from "./DeskScene";
import { DraftInboxButton } from "../DraftInboxButton";
import type { DeskCourseChatRequest } from "./DeskTutorInvoke";
import type { DeskCreateChatRequest } from "./DeskWorkFolder";
import { createStudyDeskAdapter, resolveWrongbookPracticeTarget } from "./studyDeskAdapter";
import { readStudyLearnDraft } from "../pages/LearnPage";
import {
  readStudyLocation,
  selectKnowledgeCore,
  studyContinueMeta,
  studyContinueTitle,
  STUDY_LOCATION_EVENT,
  switchStudyMode,
  type StudyLocation,
} from "../studyLocation";
import { type StudyKnowledgePoint } from "../../chat/study/study-api";
import { StudyNanaPanel } from "./StudyNanaPanel";
import { StudyCaptureFlow } from "../capture/StudyCaptureFlow";
import { StudyMaterialReader } from "./StudyMaterialReader";
import { useStudyLocationSync } from "../studyLocationSync";
import {
  onStudyNanaRequest,
  type StudyNanaRequest,
} from "../studyNanaRequest";
import { onStudyMaterialRequest } from "../studyMaterialRequest";

function outlineForNana(nodes: StudyOutlineNode[], remaining = { value: 80 }): Array<Record<string, unknown>> {
  const output: Array<Record<string, unknown>> = [];
  for (const node of nodes) {
    if (remaining.value <= 0) break;
    remaining.value -= 1;
    output.push({
      title: node.title,
      level: node.level,
      ...(node.page ? { page: node.page } : {}),
      children: outlineForNana(node.children, remaining),
    });
  }
  return output;
}

export function StudyDeskPage({
  spaceId,
  spaces,
  page,
  surface,
  mode = "practice",
  flyleafOpen = false,
  pageBody,
  switchingSpace,
  onDirtyChange,
  onNavigateAway,
  onSelectSpace,
  onImportMaterial,
}: {
  spaceId: string;
  spaces: StudySpaceSummary[];
  /** 当前分页；书桌承载全部五页，不再只是练习专用。 */
  page: StudyPageSlug;
  /** v0.5.0 canonical surface. */
  surface?: StudySurfaceSlug;
  /** Notebook work mode. */
  mode?: "learn" | "practice";
  /** Whether the flyleaf first page is open. */
  flyleafOpen?: boolean;
  pageBody?: ReactNode;
  switchingSpace?: boolean;
  onDirtyChange: (dirty: boolean) => void;
  onNavigateAway: (to: string, state?: unknown) => void;
  onSelectSpace: (spaceId: string) => void;
  onImportMaterial?: () => void;
}) {
  const repository = useStudyRepository();
  useStudyLocationSync(repository, spaceId);
  const location = useLocation();
  const navigate = useNavigate();
  const returnFocusRef = useRef(getStudyReturnState(location.state));
  const returnFocus = returnFocusRef.current;
  const [continueLocation, setContinueLocation] = useState<StudyLocation | null>(() => readStudyLocation(spaceId));
  const [adapterGeneration, setAdapterGeneration] = useState(0);
  const [nanaPanel, setNanaPanel] = useState<{
    loading: boolean;
    error: boolean;
    handoff: StudyChatHandoffV2 | null;
    initialPrompt?: string;
    autoSend?: boolean;
  } | null>(null);
  const [readerMaterialId, setReaderMaterialId] = useState<string | null>(null);
  const [readerInitialPage, setReaderInitialPage] = useState<number | undefined>();
  const [recoveryNotice, setRecoveryNotice] = useState("");
  const nanaGenerationRef = useRef(0);
  const startPageChatRef = useRef<(request: StudyNanaRequest) => void>(() => undefined);
  const spacesKey = JSON.stringify(spaces);
  const adapter = useMemo(
    () => createStudyDeskAdapter({
      repository,
      spaceId,
      spaces: JSON.parse(spacesKey) as StudySpaceSummary[],
    }),
    [repository, spaceId, spacesKey],
  );
  const navigatePage = (nextPage: StudyPageSlug) => onNavigateAway(studyPath(spaceId, nextPage));
  // 学/练原地切换与扉页翻页都只是换 URL（同一本本子）；离开时仍走 onNavigateAway
  // 的脏练习确认，未保存的答案不会被静默丢掉。
  const changeMode = (nextMode: "learn" | "practice") => {
    if (nextMode === mode) return;
    switchStudyMode(spaceId, nextMode);
    navigatePage(nextMode);
  };
  const toggleFlyleaf = () => navigatePage(flyleafOpen ? mode : "flyleaf");
  const openMaterial = (artifactId?: string) => {
    if (!artifactId) return;
    nanaGenerationRef.current += 1;
    setNanaPanel(null);
    setReaderInitialPage(undefined);
    setReaderMaterialId(artifactId);
  };

  useEffect(() => onStudyMaterialRequest((request) => {
    if (request.spaceId !== spaceId) return;
    nanaGenerationRef.current += 1;
    setNanaPanel(null);
    setReaderInitialPage(request.page);
    setReaderMaterialId(request.artifactId);
  }), [spaceId]);
  const spaceTitle = spaces.find((space) => space.id === spaceId)?.title || "我的本子";
  // 课程列表不经网络：练习数据打不开时，书立与换课照样要能用。
  const bookstandFallback = {
    title: "我的本子",
    hint: "换课就是换一本本子。",
    books: spaces
      .filter((space) => space.kind !== "scratch")
      .map((space) => ({ id: space.id, name: space.title, current: space.id === spaceId })),
    scratch: (() => {
      const book = spaces.find((space) => space.kind === "scratch");
      return book ? { id: book.id, name: book.title, current: false } : null;
    })(),
    newBookLabel: "开新本",
    currentTitle: spaceTitle,
  };

  useEffect(() => {
    if (!returnFocus) return;
    navigate(`${location.pathname}${location.search}`, { replace: true, state: null });
  }, [location.pathname, location.search, navigate, returnFocus]);

  useEffect(() => {
    setContinueLocation(readStudyLocation(spaceId));
    setReaderMaterialId(null);
    setNanaPanel(null);
    const refresh = () => setContinueLocation(readStudyLocation(spaceId));
    window.addEventListener(STUDY_LOCATION_EVENT, refresh);
    return () => window.removeEventListener(STUDY_LOCATION_EVENT, refresh);
  }, [spaceId]);

  useEffect(() => {
    if (page !== "learn" && page !== "practice") return;
    const next = switchStudyMode(spaceId, page);
    if (next) setContinueLocation(next);
  }, [page, spaceId]);

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const activityId = page === "practice" && params.get("source") === "wrongbook"
      ? params.get("activityId")
      : null;
    if (!activityId) return;
    const controller = new AbortController();
    setRecoveryNotice("正在恢复这道练习…");
    void resolveWrongbookPracticeTarget(repository, spaceId, activityId, controller.signal).then(
      (target) => {
        if (controller.signal.aborted) return;
        if (target.status === "resolved") {
          const restored = selectKnowledgeCore(spaceId, target.point, "practice", { exerciseId: target.exerciseId });
          setContinueLocation(restored);
          setRecoveryNotice("已回到这条证据对应的知识核和题目。");
          setAdapterGeneration((generation) => generation + 1);
        } else if (readStudyLocation(spaceId)?.knowledgeCoreId) {
          setRecoveryNotice("原题已经不可用，已留在当前知识核。学习记录没有改变。");
        } else {
          setRecoveryNotice("");
          onNavigateAway(studyPath(spaceId, "plan"));
          return;
        }
        navigate(studyPath(spaceId, "practice"), { replace: true });
      },
      () => {
        if (controller.signal.aborted) return;
        setRecoveryNotice("暂时无法恢复原题，已留在当前知识核。学习记录没有改变。");
        navigate(studyPath(spaceId, "practice"), { replace: true });
      },
    );
    return () => controller.abort();
  }, [location.search, navigate, onNavigateAway, page, repository, spaceId]);

  const startCourseChat = (request: DeskCourseChatRequest) => {
    setReaderMaterialId(null);
    const sessionId = resolveStudyChatSessionId(spaceId, request.focusId);
    const coreTitle = continueLocation?.knowledgeCoreTitle ?? request.focusLabel;
    const route = studyPath(spaceId, "practice");
    const handoff: StudyChatHandoffV2 = {
      version: 2,
      mode: "study",
      sessionId,
      spaceId,
      spaceTitle,
      focusKind: "practice",
      focusId: request.focusId,
      focusLabel: request.focusLabel,
      intent: "collaborate",
      originSurface: "study_desk",
      returnTarget: {
        path: route,
        fallbackPath: studyPath(spaceId),
        focus: "answer",
      },
      revision: 1,
      nanaContext: {
        schemaVersion: 1,
        course: { id: spaceId, title: spaceTitle },
        origin: {
          page: "practice",
          route,
          focusId: request.focusId,
          revision: 1,
          ...(continueLocation?.knowledgeCoreId ? { knowledgeCoreId: continueLocation.knowledgeCoreId } : {}),
          exerciseId: request.focusId,
        },
        returnTarget: { path: route, fallbackPath: studyPath(spaceId), focus: "answer", revision: 1 },
        pageContext: {
          kind: "practice",
          outlineNodeId: continueLocation?.outlineLabel ?? "source-outline-unavailable",
          knowledgeCore: {
            id: continueLocation?.knowledgeCoreId ?? "unresolved",
            title: coreTitle,
            keyStatement: "",
          },
          exercise: {
            id: request.focusId,
            prompt: request.prompt,
            answerDraft: request.answer,
            answerRevision: 1,
          },
          ...(request.checkResult ? { check: request.checkResult } : {}),
        },
        sourceRefs: [],
      },
      deskSnapshot: {
        activity: request.activity,
        answer: request.answer,
        ...(request.checkResult ? { checkResult: request.checkResult } : {}),
      },
      createdAt: new Date().toISOString(),
    };
    setNanaPanel({ loading: false, error: false, handoff });
  };

  const startCreateChat = (request: DeskCreateChatRequest) => {
    const sessionId = resolveStudyChatSessionId(spaceId, `create:${request.focusId}`);
    const handoff: StudyChatHandoff = {
      version: 1,
      mode: "study",
      sessionId,
      spaceId,
      spaceTitle,
      focusKind: "course",
      focusId: request.focusId,
      focusLabel: request.focusLabel,
      intent: "create",
      originSurface: "study_desk",
      returnTarget: {
        path: studyPath(spaceId, "practice"),
        fallbackPath: studyPath(spaceId),
        focus: "notebook",
      },
      revision: 1,
      question: request.question,
      prompt: request.prompt,
      selectedSources: request.selectedSources,
      createdAt: new Date().toISOString(),
    };
    onNavigateAway("/chat", {
      studyHandoff: handoff,
      draftPrompt: buildStudyChatPrompt(handoff),
    });
  };

  const startPageChat = async (
    practiceRequest?: DeskCourseChatRequest,
    scopedRequest?: StudyNanaRequest,
  ) => {
    if (practiceRequest) {
      startCourseChat(practiceRequest);
      return;
    }
    const generation = ++nanaGenerationRef.current;
    setReaderMaterialId(null);
    setNanaPanel({
      loading: true,
      error: false,
      handoff: null,
      ...(scopedRequest?.initialPrompt ? { initialPrompt: scopedRequest.initialPrompt } : {}),
      ...(scopedRequest?.autoSend ? { autoSend: true } : {}),
    });
    const nanaPage = page as StudyNanaPage;
    const route = studyPath(spaceId, page);
    const focusId = scopedRequest?.focusId
      ?? ((page === "learn" || page === "practice") && continueLocation?.knowledgeCoreId
        ? continueLocation.knowledgeCoreId
        : `${page}:${spaceId}`);
    const focusLabel = scopedRequest?.focusLabel ?? (page === "flyleaf"
      ? "目标与约束"
      : page === "plan"
        ? "当前学习计划"
        : page === "learn"
          ? continueLocation?.knowledgeCoreTitle ?? "当前知识核"
          : page === "evaluate"
            ? "最近评估与回访"
            : continueLocation?.knowledgeCoreTitle ?? "当前知识核的练习");
    try {
      const signal = new AbortController().signal;
      let pageContext: Record<string, unknown> & { kind: StudyNanaPage };
      let sourceRefs: StudyChatHandoffV2["nanaContext"]["sourceRefs"] = [];

    if (page === "flyleaf") {
      const active = (await repository.loadFlyleaf(spaceId, signal)).active;
      pageContext = {
        kind: "flyleaf",
        ...(active ? {
          active: {
            goals: active.payload.goals,
            preferences: active.payload.preferences,
            constraints: active.payload.constraints,
            revision: 1,
          },
        } : {}),
      };
    } else if (page === "plan") {
      const plan = await repository.loadPlan(spaceId, signal);
      const sourceOutline = plan.outline ?? [];
      pageContext = {
        kind: "plan",
        outlinePath: scopedRequest?.focusLabel ? [scopedRequest.focusLabel] : [],
        currentNodeId: scopedRequest?.outlineNodeId ?? sourceOutline[0]?.id ?? "source-outline-unavailable",
        structureStatus: plan.structureStatus ?? "unknown",
        sourceOutline: outlineForNana(sourceOutline),
        planItems: plan.items.slice(0, 12).map((item) => ({
          id: item.item_id,
          title: item.title,
          mode: item.mode ?? "learn",
          status: item.status,
        })),
        ...(scopedRequest?.selectedSource ? { selectedSource: scopedRequest.selectedSource } : {}),
      };
      if (scopedRequest?.selectedSource) {
        sourceRefs = [{ id: scopedRequest.selectedSource.id, title: scopedRequest.selectedSource.title }];
      } else if (plan.outlineSourceArtifactId) {
        sourceRefs = [{ id: plan.outlineSourceArtifactId, title: plan.outlineSourceTitle || "目录来源" }];
      }
    } else if (page === "learn") {
      const home = await repository.loadLearnHome(spaceId, signal);
      const core = home.knowledgePoints.find((point) => point.item_id === continueLocation?.knowledgeCoreId)
        ?? home.knowledgePoints[0];
      const learnerDraft = core ? readStudyLearnDraft(spaceId, core.item_id) : null;
      pageContext = {
        kind: "learn",
        outlineNodeId: continueLocation?.outlineLabel ?? "source-outline-unavailable",
        knowledgeCore: core ? { id: core.item_id, title: core.front, keyStatement: core.gist } : null,
        learnerDraft: learnerDraft?.text ?? "",
        comparisonStage: learnerDraft?.compared ? "compared" : learnerDraft?.text ? "drafted" : "not_started",
      };
      if (core) sourceRefs = [{ id: core.artifact_id, title: core.front }];
    } else if (page === "evaluate") {
      const [evaluation, wrongbook] = await Promise.all([
        repository.loadLatestEvaluation(spaceId, signal),
        repository.loadWrongbook(spaceId, signal),
      ]);
      pageContext = {
        kind: "evaluate",
        ...(evaluation.evaluation ? {
          latestEvaluation: {
            summary: evaluation.evaluation.title,
            observations: evaluation.evaluation.observations,
            suggestions: evaluation.evaluation.suggestions,
            evidenceRefs: (evaluation.evaluation.evidence_refs ?? []).slice(0, 10).map((_, index) => `evidence-${index + 1}`),
          },
        } : {}),
        returnCandidates: wrongbook.evidence.slice(0, 10).map((item) => ({
          label: item.weak_tags.join(" · ") || "回到这道练习",
          page: "practice",
          knowledgeCoreId: item.weak_tags[0] ?? "unresolved",
          exerciseId: item.activity_id,
        })),
      };
      sourceRefs = wrongbook.evidence.slice(0, 6).map((item) => ({ id: item.activity_id, title: item.weak_tags.join(" · ") || "练习证据" }));
    } else {
      pageContext = {
        kind: "practice",
        outlineNodeId: continueLocation?.outlineLabel ?? "source-outline-unavailable",
        knowledgeCore: {
          id: continueLocation?.knowledgeCoreId ?? "unresolved",
          title: continueLocation?.knowledgeCoreTitle ?? "当前知识核",
          keyStatement: "",
        },
        exercise: null,
      };
    }

      const sessionId = resolveStudyChatSessionId(spaceId, `${page}:${focusId}`);
      const handoff: StudyChatHandoffV2 = {
      version: 2,
      mode: "study",
      sessionId,
      spaceId,
      spaceTitle,
      focusKind: nanaPage,
      focusId,
      focusLabel,
      intent: "collaborate",
      originSurface: "study_desk",
      returnTarget: { path: route, fallbackPath: studyPath(spaceId), focus: focusId },
      revision: 1,
      nanaContext: {
        schemaVersion: 1,
        course: { id: spaceId, title: spaceTitle },
        origin: {
          page: nanaPage,
          route,
          focusId,
          revision: 1,
          ...(continueLocation?.planItemId ? { planItemId: continueLocation.planItemId } : {}),
          ...(continueLocation?.knowledgeCoreId ? { knowledgeCoreId: continueLocation.knowledgeCoreId } : {}),
          ...(continueLocation?.exerciseId ? { exerciseId: continueLocation.exerciseId } : {}),
        },
        returnTarget: { path: route, fallbackPath: studyPath(spaceId), focus: focusId, revision: 1 },
        pageContext,
        sourceRefs,
      },
      createdAt: new Date().toISOString(),
      };
      if (nanaGenerationRef.current === generation) {
        setNanaPanel({
          loading: false,
          error: false,
          handoff,
          ...(scopedRequest?.initialPrompt ? { initialPrompt: scopedRequest.initialPrompt } : {}),
          ...(scopedRequest?.autoSend ? { autoSend: true } : {}),
        });
      }
    } catch {
      if (nanaGenerationRef.current === generation) {
        setNanaPanel({
          loading: false,
          error: true,
          handoff: null,
          ...(scopedRequest?.initialPrompt ? { initialPrompt: scopedRequest.initialPrompt } : {}),
          ...(scopedRequest?.autoSend ? { autoSend: true } : {}),
        });
      }
    }
  };

  startPageChatRef.current = (request) => {
    void startPageChat(undefined, request);
  };

  useEffect(() => onStudyNanaRequest((request) => {
    if (request.spaceId !== spaceId || request.page !== page) return;
    startPageChatRef.current(request);
  }), [page, spaceId]);

  const enterActivatedPracticeDraft = async (artifactId: string) => {
    const controller = new AbortController();
    let target: { questionId: string; core: StudyKnowledgePoint } | null = null;
    try {
      const [questions, home] = await Promise.all([
        repository.loadQuizQuestions(spaceId, artifactId, controller.signal),
        repository.loadLearnHome(spaceId, controller.signal),
      ]);
      const firstExact = questions.find((question) => (
        Boolean(continueLocation?.knowledgeCoreId)
        && question.knowledge_core_id === continueLocation?.knowledgeCoreId
      )) ?? questions.find((question) => Boolean(question.knowledge_core_id));
      const core = firstExact
        ? home.knowledgePoints.find((point) => point.item_id === firstExact.knowledge_core_id)
        : null;
      if (firstExact && core) {
        target = { questionId: firstExact.item_id, core };
      } else {
        setRecoveryNotice("已采用这份练习；没有可靠知识核关联时仍留在当前范围。");
      }
    } catch {
      // Activation already succeeded. The practice page reload is the safe
      // fallback; it will either resolve the active quiz or keep the honest
      // current-core empty state without inventing a mapping.
      setRecoveryNotice("练习已经采用，正在从当前知识核重新载入。");
    }
    setAdapterGeneration((generation) => generation + 1);
    onNavigateAway(studyPath(spaceId, "practice"));
    await Promise.resolve();
    // Write the practice bookmark after requesting the route change. This
    // prevents a departing LearnPage effect from restoring the same core with
    // page="learn" between activation and the practice desk mount.
    if (target) {
      const next = selectKnowledgeCore(spaceId, target.core, "practice", {
        exerciseId: target.questionId,
      });
      setContinueLocation(next);
      setRecoveryNotice("已采用这份练习，并回到对应知识核。");
    }
  };

  return (
    <>
      <DeskScene
      key={`${spaceId}:${page}:${adapterGeneration}`}
      adapter={adapter}
      returnFocus={returnFocus}
      currentPage={page}
      surface={surface}
      mode={mode}
      flyleafOpen={flyleafOpen}
      spaceTitle={spaces.find((space) => space.id === spaceId)?.title || "我的本子"}
      pageBody={pageBody}
      rightPage={surface === "notebook" && !flyleafOpen ? (
        <StudyCaptureFlow purpose={mode === "practice" ? "review" : "stuck"} />
      ) : undefined}
      continueTitle={continueLocation ? studyContinueTitle(continueLocation) : undefined}
      continueMeta={continueLocation ? studyContinueMeta(continueLocation) : undefined}
      continueLabel={continueLocation?.page === "plan" ? "从这里开始" : "继续"}
      pageNotice={recoveryNotice}
      draftInbox={<DraftInboxButton onActivated={(item) => enterActivatedPracticeDraft(item.artifact_id)} />}
      bookstandFallback={bookstandFallback}
      switchingSpace={switchingSpace}
      onDirtyChange={onDirtyChange}
      onImportMaterial={onImportMaterial}
      onNavigatePage={navigatePage}
      onModeChange={changeMode}
      onToggleFlyleaf={toggleFlyleaf}
      onResumeLocation={() => {
        if (!continueLocation) return;
        const targetPath = studyPath(spaceId, continueLocation.page);
        if (continueLocation.page !== "plan" || !continueLocation.planItemId) {
          onNavigateAway(targetPath);
          return;
        }
        const targetId = `study-plan-item-${continueLocation.planItemId}`;
        if (page === "plan") {
          const target = document.getElementById(targetId);
          target?.scrollIntoView?.({ block: "center" });
          target?.focus();
          return;
        }
        onNavigateAway(`${targetPath}#${encodeURIComponent(targetId)}`);
      }}
      onChangeKnowledgeCore={(point) => {
        selectKnowledgeCore(spaceId, point, "practice");
        setAdapterGeneration((generation) => generation + 1);
      }}
      onBackToLearn={() => {
        switchStudyMode(spaceId, "learn");
        onNavigateAway(studyPath(spaceId, "learn"));
      }}
      onAskPage={(request) => { void startPageChat(request); }}
      onOpenChatSession={(sessionId) => onNavigateAway("/chat", { openSessionId: sessionId })}
      onStartCourseChat={startCourseChat}
      onStartCreateChat={startCreateChat}
      onOpenActivity={() => navigatePage("evaluate")}
      onSelectSpace={onSelectSpace}
      onOpenMaterials={openMaterial}
      onNewBook={() => onNavigateAway("/chat", {
        draftPrompt: "我想开一本新的学习本。请先问我本子名称、学习目标和现有材料，再帮我确认创建请求。",
      })}
      />
      {nanaPanel ? (
        <StudyNanaPanel
          handoff={nanaPanel.handoff}
          loading={nanaPanel.loading}
          contextError={nanaPanel.error}
          initialPrompt={nanaPanel.initialPrompt}
          autoSend={nanaPanel.autoSend}
          onClose={() => {
            nanaGenerationRef.current += 1;
            setNanaPanel(null);
          }}
          onOpenFull={(handoff, draftPrompt) => onNavigateAway("/chat", {
            studyHandoff: handoff,
            openSessionId: handoff.sessionId,
            draftPrompt,
          })}
        />
      ) : null}
      {readerMaterialId ? (
        <StudyMaterialReader
          key={`${spaceId}:${readerMaterialId}:${readerInitialPage ?? "saved"}`}
          spaceId={spaceId}
          artifactId={readerMaterialId}
          initialPage={readerInitialPage}
          onClose={() => setReaderMaterialId(null)}
          onDeleted={() => setAdapterGeneration((generation) => generation + 1)}
        />
      ) : null}
    </>
  );
}
