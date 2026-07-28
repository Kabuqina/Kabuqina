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
import { ImportMaterials, type StudyImportResult } from "./ImportMaterials";
import { ScratchDesk } from "./ScratchDesk";
import { StudyPageOutlet } from "./pages/StudyPageOutlet";
import { useStudyIa } from "./StudyIaContext";
import { StudyDeskPage } from "./desk/StudyDeskPage";

export function StudyShell({ spaces, spaceId, page, scratch = false, onRevalidate, refreshing = false, refreshFailed = false }: {
  spaces: StudySpaces;
  spaceId?: string;
  page?: StudyPageSlug;
  /** 杂记本没有五分页，所以它按 `/study/<id>` 直接摊开（账本 B-12）。 */
  scratch?: boolean;
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
  const [practiceDirty, setPracticeDirty] = useState(false);
  const [importing, setImporting] = useState(false);
  /**
   * 导入弹窗读完就退出，提示落在学生返回的那一页上——所以「下一步是分课与目录」
   * 这句话归 shell 管，不归弹窗管（弹窗那会儿已经关了）。
   */
  const [imported, setImported] = useState<StudyImportResult | null>(null);

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
    if (switching || nextSpaceId === spaceId) return;
    void confirmPracticeLeave().then((approved) => {
      if (!approved) return;
      const request = switchRequests.current.begin();
      setSwitching(true);
      void repository.selectSpace(nextSpaceId, request.signal).then(() => {
        if (!switchRequests.current.isCurrent(request.generation)) return;
        setSwitching(false);
        recordIa({ name: "study.space.switch", action: "switch", success: true });
        const next = spaces.spaces.find((space) => space.id === nextSpaceId);
        navigate(next?.kind === "scratch" ? `/study/${encodeURIComponent(nextSpaceId)}` : studyPath(nextSpaceId, page));
        onRevalidate?.();
      }, () => {
        if (!switchRequests.current.isCurrent(request.generation)) return;
        setSwitching(false);
        recordIa({ name: "study.space.switch", action: "switch", success: false });
      });
    });
  }, [confirmPracticeLeave, navigate, onRevalidate, page, recordIa, repository, spaceId, spaces.spaces, switching]);

  useEffect(() => {
    if (!spaceId || !page) return;
    recordIa(
      { name: "study.page.view", page, action: "view" },
      { dedupeKey: `study-page-view:${location.key}` },
    );
  }, [location.key, page, recordIa, spaceId]);

  useEffect(() => () => switchRequests.current.cancel(), []);

  const shell = useMemo(() => {
    if (spaceId && scratch) {
      return (
        <ScratchDesk
          spaceId={spaceId}
          spaces={spaces.spaces}
          switchingSpace={switching}
          onSelectSpace={selectSpace}
          onNewBook={() => navigateAway("/chat", {
            draftPrompt: "我想开一本新的课程笔记本。请先问我课程名称、学习目标和现有材料，再帮我确认创建请求。",
          })}
          onAskNana={() => navigateAway("/chat")}
        />
      );
    }
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
    /**
     * 五个分页共用**同一张书桌**（原型 `StudyDesk`）：书立在上、笔记本在中、
     * 书堆/复习/杯子在右。练习那一页的正文由书桌自己画（只有它带作答面、
     * 检查反馈和页边批注）；其余四页把 `StudyPageOutlet` 铺进本子里。
     *
     * 所以这里不再按 page 分岔成"书桌 / 非书桌"两套外壳——那正是 0.4 留下的
     * 割裂：同一门课，翻一页就换一个世界。
     */
    const pageBody = page === "practice" ? undefined : (
      <>
        {imported && imported.limited > 0 ? (
          <p className="kq-study-refresh-status" role="status">{t("study.importLimitedSummary")}</p>
        ) : null}
        {imported && imported.paths.length >= 2 ? (
          <p className="kq-study-refresh-status" role="status">{t("study.importNextAlignment")}</p>
        ) : null}
        {refreshing ? <p className="kq-study-refresh-status" role="status">{t("study.refreshing")}</p> : null}
        {refreshFailed ? (
          <div className="kq-study-refresh-error" role="alert">
            <span>{t("study.refreshFailed")}</span>
            <button type="button" onClick={onRevalidate}>{t("study.retry")}</button>
          </div>
        ) : null}
        <StudyPageOutlet
          spaceId={spaceId}
          page={page}
          onPracticeDirtyChange={setPracticeDirty}
          onPracticeNavigateAway={navigateAway}
        />
      </>
    );

    return (
      <StudyDraftProvider key={spaceId} spaceId={spaceId}>
        <StudyDeskPage
          spaceId={spaceId}
          spaces={spaces.spaces}
          page={page}
          pageBody={pageBody}
          switchingSpace={switching}
          onDirtyChange={setPracticeDirty}
          onNavigateAway={navigateAway}
          onSelectSpace={selectSpace}
          onImportMaterial={() => setImporting(true)}
        />
        {importing ? (
          <ImportMaterials onClose={() => setImporting(false)} onImported={setImported} />
        ) : null}
      </StudyDraftProvider>
    );
  }, [imported, importing, navigateAway, onRevalidate, page, refreshFailed, refreshing, scratch, selectSpace, spaceId, spaces.spaces, switching, t]);

  return (
    <div
      className="kq-study-shell"
      data-desk={spaceId && (page || scratch) ? "true" : undefined}
      data-testid="study-shell"
    >
      {shell}
    </div>
  );
}
