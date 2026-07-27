// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useI18n } from "../lib/i18n";
import { confirm } from "../lib/confirmDialog";
import {
  getStudyChatHandoffFromLocation,
  persistPendingStudyHandoff,
} from "../lib/studyChatHandoff";
import { StudyDraftProvider } from "./DraftContext";
import { RequestCoordinator } from "./loadable";
import type { StudySpaces } from "./repository";
import { useStudyRepository } from "./repositoryContext";
import { studyPath, type StudyPageSlug } from "./routeModel";
import { StudyLifecycleNav } from "./StudyLifecycleNav";
import { StudyTopBar } from "./StudyTopBar";
import { StudyPageOutlet } from "./pages/StudyPageOutlet";
import { useStudyIa } from "./StudyIaContext";
import { StudyDeskPage } from "./desk/StudyDeskPage";

export function StudyShell({ spaces, spaceId, page, onRevalidate, refreshing = false, refreshFailed = false }: {
  spaces: StudySpaces;
  spaceId?: string;
  page?: StudyPageSlug;
  onRevalidate?: () => void;
  refreshing?: boolean;
  refreshFailed?: boolean;
}) {
  const { t } = useI18n();
  const repository = useStudyRepository();
  const navigate = useNavigate();
  const location = useLocation();
  const recordIa = useStudyIa();
  const switchRequests = useRef(new RequestCoordinator());
  const [switching, setSwitching] = useState(false);
  const [switchError, setSwitchError] = useState(false);
  const [practiceDirty, setPracticeDirty] = useState(false);

  const confirmPracticeLeave = useCallback(async () => {
    if (!practiceDirty) return true;
    const approved = await confirm({
      title: t("study.practiceLeaveTitle"),
      message: t("study.practiceLeaveBody"),
      confirmLabel: t("study.practiceLeaveConfirm"),
      cancelLabel: t("dialog.cancel"),
      tone: "warning",
    });
    if (approved) setPracticeDirty(false);
    return approved;
  }, [practiceDirty, t]);

  const navigateAway = useCallback((to: string, state?: unknown) => {
    void confirmPracticeLeave().then((approved) => {
      if (!approved) return;
      const handoff = getStudyChatHandoffFromLocation(state);
      if (handoff) persistPendingStudyHandoff(handoff);
      navigate(to, { state });
    });
  }, [confirmPracticeLeave, navigate]);

  const selectSpace = useCallback((nextSpaceId: string) => {
    if (!page || switching || nextSpaceId === spaceId) return;
    void confirmPracticeLeave().then((approved) => {
      if (!approved) return;
      const request = switchRequests.current.begin();
      setSwitching(true);
      setSwitchError(false);
      void repository.selectSpace(nextSpaceId, request.signal).then(() => {
        if (!switchRequests.current.isCurrent(request.generation)) return;
        setSwitching(false);
        recordIa({ name: "study.space.switch", action: "switch", success: true });
        navigate(studyPath(nextSpaceId, page));
        onRevalidate?.();
      }, () => {
        if (!switchRequests.current.isCurrent(request.generation)) return;
        setSwitching(false);
        setSwitchError(true);
        recordIa({ name: "study.space.switch", action: "switch", success: false });
      });
    });
  }, [confirmPracticeLeave, navigate, onRevalidate, page, recordIa, repository, spaceId, switching]);

  useEffect(() => {
    if (!spaceId || !page) return;
    recordIa(
      { name: "study.page.view", page, action: "view" },
      { dedupeKey: `study-page-view:${location.key}` },
    );
  }, [location.key, page, recordIa, spaceId]);

  useEffect(() => () => switchRequests.current.cancel(), []);

  const shell = useMemo(() => {
    if (!spaceId || !page) {
      return (
        <main className="kq-study-empty">
          <p className="kq-study-placeholder-kicker">{t("study.lifecycle")}</p>
          <h1>{t("study.emptyTitle")}</h1>
          <p>{t("study.emptyBody")}</p>
          <Link className="kq-study-primary-link" to="/chat">{t("study.openLegacyStudy")}</Link>
        </main>
      );
    }
    if (page === "practice") {
      return (
        <StudyDraftProvider key={spaceId} spaceId={spaceId}>
          <StudyDeskPage
            spaceId={spaceId}
            spaces={spaces.spaces}
            onDirtyChange={setPracticeDirty}
            onNavigateAway={navigateAway}
            onSelectSpace={selectSpace}
          />
        </StudyDraftProvider>
      );
    }
    return (
      <>
        <StudyDraftProvider key={spaceId} spaceId={spaceId}>
          <StudyTopBar
            spaces={spaces.spaces}
            currentSpaceId={spaceId}
            switching={switching}
            switchError={switchError}
            onSelectSpace={selectSpace}
            onNavigateAway={navigateAway}
          />
          <StudyLifecycleNav spaceId={spaceId} currentPage={page} onNavigate={(nextPage) => navigateAway(studyPath(spaceId, nextPage))} />
          {refreshing ? <p className="kq-study-refresh-status" role="status">{t("study.refreshing")}</p> : null}
          {refreshFailed ? (
            <div className="kq-study-refresh-error" role="alert">
              <span>{t("study.refreshFailed")}</span>
              <button type="button" onClick={onRevalidate}>{t("study.retry")}</button>
            </div>
          ) : null}
          <div className="kq-study-page"><StudyPageOutlet spaceId={spaceId} page={page} onPracticeDirtyChange={setPracticeDirty} onPracticeNavigateAway={navigateAway} /></div>
        </StudyDraftProvider>
      </>
    );
  }, [navigate, navigateAway, onRevalidate, page, refreshFailed, refreshing, selectSpace, spaceId, spaces.spaces, switchError, switching, t]);

  return (
    <div
      className="kq-study-shell"
      data-desk={spaceId && page === "practice" ? "true" : undefined}
      data-testid="study-shell"
    >
      {shell}
    </div>
  );
}
