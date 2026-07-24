// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useEffect, useMemo, useRef } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import {
  buildStudyChatPrompt,
  getStudyReturnState,
  resolveStudyChatSessionId,
  type StudyChatHandoff,
} from "../../lib/studyChatHandoff";
import { useStudyRepository } from "../repositoryContext";
import { studyPath, type StudyPageSlug } from "../routeModel";
import type { StudySpaceSummary } from "../repository";
import DeskScene from "./DeskScene";
import type { DeskCourseChatRequest } from "./DeskTutorInvoke";
import type { DeskCreateChatRequest } from "./DeskWorkFolder";
import { createStudyDeskAdapter } from "./studyDeskAdapter";

export function StudyDeskPage({
  spaceId,
  spaces,
  onDirtyChange,
  onNavigateAway,
  onSelectSpace,
}: {
  spaceId: string;
  spaces: StudySpaceSummary[];
  onDirtyChange: (dirty: boolean) => void;
  onNavigateAway: (to: string, state?: unknown) => void;
  onSelectSpace: (spaceId: string) => void;
}) {
  const repository = useStudyRepository();
  const location = useLocation();
  const navigate = useNavigate();
  const returnFocusRef = useRef(getStudyReturnState(location.state));
  const returnFocus = returnFocusRef.current;
  const spacesKey = JSON.stringify(spaces);
  const adapter = useMemo(
    () => createStudyDeskAdapter({
      repository,
      spaceId,
      spaces: JSON.parse(spacesKey) as StudySpaceSummary[],
    }),
    [repository, spaceId, spacesKey],
  );
  const navigatePage = (page: StudyPageSlug) => onNavigateAway(studyPath(spaceId, page));
  const spaceTitle = spaces.find((space) => space.id === spaceId)?.title || "我的课程";

  useEffect(() => {
    if (!returnFocus) return;
    navigate(`${location.pathname}${location.search}`, { replace: true, state: null });
  }, [location.pathname, location.search, navigate, returnFocus]);

  const startCourseChat = (request: DeskCourseChatRequest) => {
    const sessionId = resolveStudyChatSessionId(spaceId, request.focusId);
    const handoff: StudyChatHandoff = {
      version: 1,
      mode: "study",
      sessionId,
      spaceId,
      spaceTitle,
      focusKind: "quiz_step",
      focusId: request.focusId,
      focusLabel: request.focusLabel,
      intent: "explain",
      originSurface: "study_desk",
      returnTarget: {
        path: studyPath(spaceId, "practice"),
        fallbackPath: studyPath(spaceId),
        focus: "answer",
      },
      revision: 1,
      question: request.question,
      prompt: request.prompt,
      answer: request.answer,
      feedback: request.feedback,
      deskSnapshot: {
        activity: request.activity,
        answer: request.answer,
        ...(request.checkResult ? { checkResult: request.checkResult } : {}),
      },
      createdAt: new Date().toISOString(),
    };
    onNavigateAway("/chat", {
      studyHandoff: handoff,
      draftPrompt: buildStudyChatPrompt(handoff),
    });
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

  return (
    <DeskScene
      adapter={adapter}
      returnFocus={returnFocus}
      currentPage="practice"
      onDirtyChange={onDirtyChange}
      onNavigatePage={navigatePage}
      onOpenChat={() => onNavigateAway("/chat")}
      onOpenChatSession={(sessionId) => onNavigateAway("/chat", { openSessionId: sessionId })}
      onStartCourseChat={startCourseChat}
      onStartCreateChat={startCreateChat}
      onOpenActivity={() => navigatePage("evaluate")}
      onOpenSettings={() => onNavigateAway("/settings")}
      onSelectSpace={onSelectSpace}
      onOpenMaterials={() => navigatePage("learn")}
      onNewBook={() => onNavigateAway("/chat", {
        draftPrompt: "我想开一本新的课程笔记本。请先问我课程名称、学习目标和现有材料，再帮我确认创建请求。",
      })}
    />
  );
}
