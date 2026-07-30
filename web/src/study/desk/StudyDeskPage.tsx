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
import { studyPath, type StudyPageSlug } from "../routeModel";
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
import { cmdStudyArtifactStatus, type StudyKnowledgePoint } from "../../chat/study/study-api";
import { StudyNanaPanel } from "./StudyNanaPanel";
import { StudyMaterialReader } from "./StudyMaterialReader";

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
  pageBody?: ReactNode;
  switchingSpace?: boolean;
  onDirtyChange: (dirty: boolean) => void;
  onNavigateAway: (to: string, state?: unknown) => void;
  onSelectSpace: (spaceId: string) => void;
  onImportMaterial?: () => void;
}) {
  const repository = useStudyRepository();
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
  } | null>(null);
  const [readerMaterialId, setReaderMaterialId] = useState<string | null>(null);
  const [recoveryNotice, setRecoveryNotice] = useState("");
  const nanaGenerationRef = useRef(0);
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
  const openMaterial = (artifactId?: string) => {
    if (!artifactId) return;
    nanaGenerationRef.current += 1;
    setNanaPanel(null);
    setReaderMaterialId(artifactId);
  };
  const removeMaterial = (artifactId: string, title: string) => {
    const confirmed = window.confirm(
      `要把“${title}”从本课移出吗？\n\n只会移除课程引用，不会删除电脑上的原文件。`,
    );
    if (!confirmed) return;
    void cmdStudyArtifactStatus(spaceId, artifactId, "archived")
      .then(() => setAdapterGeneration((generation) => generation + 1))
      .catch(() => window.alert("这份资料暂时没有移出，请稍后重试。原文件没有被改动。"));
  };
  const spaceTitle = spaces.find((space) => space.id === spaceId)?.title || "我的课程";
  // 课程列表不经网络：练习数据打不开时，书立与换课照样要能用。
  const bookstandFallback = {
    title: "我的课程本",
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
          setRecoveryNotice("原题已经不可用，已留在当前知识核。课程记录没有改变。");
        } else {
          setRecoveryNotice("");
          onNavigateAway(studyPath(spaceId, "plan"));
          return;
        }
        navigate(studyPath(spaceId, "practice"), { replace: true });
      },
      () => {
        if (controller.signal.aborted) return;
        setRecoveryNotice("暂时无法恢复原题，已留在当前知识核。课程记录没有改变。");
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

  const startPageChat = async (practiceRequest?: DeskCourseChatRequest) => {
    if (practiceRequest) {
      startCourseChat(practiceRequest);
      return;
    }
    const generation = ++nanaGenerationRef.current;
    setReaderMaterialId(null);
    setNanaPanel({ loading: true, error: false, handoff: null });
    const nanaPage = page as StudyNanaPage;
    const route = studyPath(spaceId, page);
    const focusId = (page === "learn" || page === "practice") && continueLocation?.knowledgeCoreId
      ? continueLocation.knowledgeCoreId
      : `${page}:${spaceId}`;
    const focusLabel = page === "flyleaf"
      ? "课程目标与约束"
      : page === "plan"
        ? "当前学习计划"
        : page === "learn"
          ? continueLocation?.knowledgeCoreTitle ?? "当前知识核"
          : page === "evaluate"
            ? "最近评估与回访"
            : continueLocation?.knowledgeCoreTitle ?? "当前知识核的练习";
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
        outlinePath: [],
        currentNodeId: sourceOutline[0]?.id ?? "source-outline-unavailable",
        structureStatus: plan.structureStatus ?? "unknown",
        sourceOutline: outlineForNana(sourceOutline),
        planItems: plan.items.slice(0, 12).map((item) => ({
          id: item.item_id,
          title: item.title,
          mode: item.mode ?? "learn",
          status: item.status,
        })),
      };
      if (plan.outlineSourceArtifactId) {
        sourceRefs = [{ id: plan.outlineSourceArtifactId, title: plan.outlineSourceTitle || "课程目录来源" }];
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
        setNanaPanel({ loading: false, error: false, handoff });
      }
    } catch {
      if (nanaGenerationRef.current === generation) {
        setNanaPanel({ loading: false, error: true, handoff: null });
      }
    }
  };

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
      pageBody={pageBody}
      continueTitle={continueLocation ? studyContinueTitle(continueLocation) : undefined}
      continueMeta={continueLocation ? studyContinueMeta(continueLocation) : undefined}
      pageNotice={recoveryNotice}
      draftInbox={<DraftInboxButton onActivated={(item) => enterActivatedPracticeDraft(item.artifact_id)} />}
      bookstandFallback={bookstandFallback}
      switchingSpace={switchingSpace}
      onDirtyChange={onDirtyChange}
      onImportMaterial={onImportMaterial}
      onNavigatePage={navigatePage}
      onResumeLocation={() => {
        if (!continueLocation) return;
        onNavigateAway(studyPath(spaceId, continueLocation.page));
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
      onRemoveMaterial={removeMaterial}
      onNewBook={() => onNavigateAway("/chat", {
        draftPrompt: "我想开一本新的课程笔记本。请先问我课程名称、学习目标和现有材料，再帮我确认创建请求。",
      })}
      />
      {nanaPanel ? (
        <StudyNanaPanel
          handoff={nanaPanel.handoff}
          loading={nanaPanel.loading}
          contextError={nanaPanel.error}
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
          key={`${spaceId}:${readerMaterialId}`}
          spaceId={spaceId}
          artifactId={readerMaterialId}
          onClose={() => setReaderMaterialId(null)}
        />
      ) : null}
    </>
  );
}
