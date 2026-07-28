// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useEffect, useMemo, useRef, type ReactNode } from "react";
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
import { DraftInboxButton } from "../DraftInboxButton";
import type { DeskCourseChatRequest } from "./DeskTutorInvoke";
import type { DeskCreateChatRequest } from "./DeskWorkFolder";
import { createStudyDeskAdapter } from "./studyDeskAdapter";

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
  const spaceTitle = spaces.find((space) => space.id === spaceId)?.title || "我的课程";
  // 课程列表不经网络：练习数据打不开时，书立与换课照样要能用。
  const bookstandFallback = {
    title: "我的课程本",
    hint: "换课就是换一本本子。",
    books: spaces.map((space) => ({ id: space.id, name: space.title, current: space.id === spaceId })),
    newBookLabel: "开新本",
    currentTitle: spaceTitle,
  };

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
      currentPage={page}
      pageBody={pageBody}
      draftInbox={<DraftInboxButton />}
      bookstandFallback={bookstandFallback}
      switchingSpace={switchingSpace}
      onDirtyChange={onDirtyChange}
      onImportMaterial={onImportMaterial}
      onNavigatePage={navigatePage}
      onOpenChatSession={(sessionId) => onNavigateAway("/chat", { openSessionId: sessionId })}
      onStartCourseChat={startCourseChat}
      onStartCreateChat={startCreateChat}
      onOpenActivity={() => navigatePage("evaluate")}
      onSelectSpace={onSelectSpace}
      onOpenMaterials={() => navigatePage("learn")}
      onNewBook={() => onNavigateAway("/chat", {
        draftPrompt: "我想开一本新的课程笔记本。请先问我课程名称、学习目标和现有材料，再帮我确认创建请求。",
      })}
    />
  );
}
