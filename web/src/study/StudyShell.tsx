// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useI18n } from "../lib/i18n";
import { RequestCoordinator } from "./loadable";
import type { StudySpaces } from "./repository";
import { useStudyRepository } from "./repositoryContext";
import { studyPath, type StudyPageSlug } from "./routeModel";
import { StudyLifecycleNav } from "./StudyLifecycleNav";
import { StudyTopBar } from "./StudyTopBar";
import { PlaceholderPage } from "./pages/PlaceholderPage";

const STUDY_LEARNING_EVENT = "study-learning-event";

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
  const draftRequests = useRef(new RequestCoordinator());
  const switchRequests = useRef(new RequestCoordinator());
  const [draftCounts, setDraftCounts] = useState<Record<string, number>>({});
  const [switching, setSwitching] = useState(false);
  const [switchError, setSwitchError] = useState(false);

  const loadDrafts = useCallback(() => {
    if (!spaceId) { setDraftCounts({}); return; }
    const request = draftRequests.current.begin();
    void repository.listDrafts(request.signal).then((drafts) => {
      if (!draftRequests.current.isCurrent(request.generation)) return;
      setDraftCounts({ ...drafts.kindCounts });
    }, () => undefined);
  }, [repository, spaceId]);

  useEffect(() => {
    const activeDraftRequests = draftRequests.current;
    loadDrafts();
    const refresh = () => { loadDrafts(); onRevalidate?.(); };
    window.addEventListener(STUDY_LEARNING_EVENT, refresh);
    return () => {
      window.removeEventListener(STUDY_LEARNING_EVENT, refresh);
      activeDraftRequests.cancel();
    };
  }, [loadDrafts, onRevalidate]);

  const selectSpace = useCallback((nextSpaceId: string) => {
    if (!page || switching || nextSpaceId === spaceId) return;
    const request = switchRequests.current.begin();
    setSwitching(true);
    setSwitchError(false);
    void repository.selectSpace(nextSpaceId, request.signal).then(() => {
      if (!switchRequests.current.isCurrent(request.generation)) return;
      setSwitching(false);
      navigate(studyPath(nextSpaceId, page));
      onRevalidate?.();
    }, () => {
      if (!switchRequests.current.isCurrent(request.generation)) return;
      setSwitching(false);
      setSwitchError(true);
    });
  }, [navigate, onRevalidate, page, repository, spaceId, switching]);

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
    return (
      <>
        <StudyTopBar
          spaces={spaces.spaces}
          currentSpaceId={spaceId}
          draftCounts={draftCounts}
          switching={switching}
          switchError={switchError}
          onSelectSpace={selectSpace}
        />
        <StudyLifecycleNav spaceId={spaceId} />
        {refreshing ? <p className="kq-study-refresh-status" role="status">{t("study.refreshing")}</p> : null}
        {refreshFailed ? (
          <div className="kq-study-refresh-error" role="alert">
            <span>{t("study.refreshFailed")}</span>
            <button type="button" onClick={onRevalidate}>{t("study.retry")}</button>
          </div>
        ) : null}
        <div className="kq-study-page"><PlaceholderPage page={page} /></div>
      </>
    );
  }, [draftCounts, onRevalidate, page, refreshFailed, refreshing, selectSpace, spaceId, spaces.spaces, switchError, switching, t]);

  return <div className="kq-study-shell" data-testid="study-shell">{shell}</div>;
}
