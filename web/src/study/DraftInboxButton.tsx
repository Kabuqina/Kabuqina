// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { Inbox, X } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useNavigate } from "react-router-dom";
import { useI18n } from "../lib/i18n";
import { type StudyArtifactSummary } from "../chat/study/study-api";
import { ArtifactAdvancedPanel } from "./ArtifactAdvancedPanel";
import { useStudyDrafts } from "./DraftContext";
import { LearnArtifactContent } from "./LearnArtifactContent";
import type { Loadable } from "./loadable";
import type { StudyArtifactDetail } from "./repository";
import { studyPath, type StudyPageSlug } from "./routeModel";

function pageForKind(kind: string): StudyPageSlug | null {
  if (kind === "student_state") return "flyleaf";
  if (kind === "learning_plan") return "plan";
  if (kind === "knowledge_base" || kind === "resource_pack" || kind === "tutoring_note") return "learn";
  if (kind === "flashcard_deck" || kind === "quiz") return "practice";
  if (kind === "evaluation") return "evaluate";
  return null;
}

function kindLabel(kind: string, t: (key: string) => string): string {
  const key = `study.draftKind.${kind}`;
  const translated = t(key);
  return translated === key ? kind.replaceAll("_", " ") : translated;
}

function snapshotItems(snapshot: ReturnType<typeof useStudyDrafts>["snapshot"]): StudyArtifactSummary[] {
  if (snapshot.status === "ready") return snapshot.data.items;
  if (snapshot.status === "loading" || snapshot.status === "error") return snapshot.previous?.items ?? [];
  return [];
}

function detailData(detail: Loadable<StudyArtifactDetail> | undefined): StudyArtifactDetail | undefined {
  if (!detail) return undefined;
  if (detail.status === "ready") return detail.data;
  return detail.status === "loading" || detail.status === "error" ? detail.previous : undefined;
}

export function DraftInboxButton() {
  const { t } = useI18n();
  const navigate = useNavigate();
  const controller = useStudyDrafts();
  const trigger = useRef<HTMLButtonElement>(null);
  const dialog = useRef<HTMLDivElement>(null);
  const close = useRef<HTMLButtonElement>(null);
  const [open, setOpen] = useState(false);
  const [kind, setKind] = useState("all");
  const [selectedId, setSelectedId] = useState("");
  const data = controller.snapshot.status === "ready"
    ? controller.snapshot.data
    : controller.snapshot.status === "loading" || controller.snapshot.status === "error"
      ? controller.snapshot.previous
      : undefined;
  const items = snapshotItems(controller.snapshot);
  const total = data?.total ?? 0;
  const displayCount = total > 99 ? "99+" : String(total);
  const kinds = useMemo(() => Object.keys(data?.kindCounts ?? {}).sort(), [data?.kindCounts]);
  const filtered = useMemo(
    () => items.filter((item) => kind === "all" || item.kind === kind),
    [items, kind],
  );
  const selected = filtered.find((item) => item.artifact_id === selectedId) ?? null;
  const detail = selected ? controller.details[selected.artifact_id] : undefined;
  const openedDetail = detailData(detail);
  const action = selected ? controller.actions[selected.artifact_id] : undefined;
  const actionError = selected ? controller.actionErrors[selected.artifact_id] : undefined;
  const needsReview = openedDetail?.review.mode === "semantic" && openedDetail.review.status !== "passed";

  const closeDialog = useCallback(() => {
    setOpen(false);
    requestAnimationFrame(() => trigger.current?.focus());
  }, []);

  useEffect(() => {
    if (!open) return;
    close.current?.focus();
  }, [closeDialog, open]);

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (event: PointerEvent) => {
      const target = event.target as Node | null;
      if (target && (dialog.current?.contains(target) || trigger.current?.contains(target))) return;
      closeDialog();
    };
    document.addEventListener("pointerdown", onPointerDown);
    return () => document.removeEventListener("pointerdown", onPointerDown);
  }, [closeDialog, open]);

  useEffect(() => {
    if (!open) return;
    const onDocumentKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Escape" || event.defaultPrevented) return;
      event.preventDefault();
      closeDialog();
    };
    document.addEventListener("keydown", onDocumentKeyDown);
    return () => document.removeEventListener("keydown", onDocumentKeyDown);
  }, [closeDialog, open]);

  useEffect(() => {
    if (!open || !selected) return;
    controller.openDetail(selected.artifact_id);
  }, [controller, open, selected]);

  useEffect(() => {
    if (selectedId && !items.some((item) => item.artifact_id === selectedId)) setSelectedId("");
  }, [items, selectedId]);

  const onKeyDown = (event: React.KeyboardEvent) => {
    if (event.key === "Escape") {
      event.preventDefault();
      closeDialog();
      return;
    }
    if (event.key !== "Tab") return;
    const focusable = [...(dialog.current?.querySelectorAll<HTMLElement>("[data-study-focus]") ?? [])]
      .filter((element) => !element.hasAttribute("disabled"));
    if (!focusable.length) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
    if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
  };

  return (
    <>
      <button
        ref={trigger}
        type="button"
        className="kq-study-top-action"
        aria-expanded={open}
        aria-haspopup="dialog"
        onClick={() => setOpen(true)}
      >
        <Inbox aria-hidden />
        <span>{t("study.drafts")}</span>
        <span className="kq-study-count" aria-label={t("study.draftCount", { count: total })}>{displayCount}</span>
      </button>
      {open ? createPortal(
        <div className="kq-study-dialog-backdrop kq-study-draft-backdrop" role="presentation" onPointerDown={(event) => { if (event.target === event.currentTarget) closeDialog(); }}>
          <section
            ref={dialog}
            className="kq-study-dialog kq-study-draft-dialog"
            role="dialog"
            aria-modal="true"
            aria-label={t("study.drafts")}
            onKeyDown={onKeyDown}
          >
            <button ref={close} data-study-focus type="button" className="kq-study-dialog-close" onClick={closeDialog} aria-label={t("dialog.cancel")}><X aria-hidden /></button>
            <header className="kq-study-card-title">
              <div><p>{t("study.draftInboxKicker")}</p><h2>{t("study.drafts")}</h2></div>
              {data?.truncated ? <span className="kq-study-muted">{t("study.listTruncated", { count: data.returned, total: data.total })}</span> : null}
            </header>
            {controller.snapshot.status === "loading" && !data ? <p role="status">{t("study.pageLoading")}</p> : null}
            {controller.snapshot.status === "error" && !data ? <div className="kq-study-page-alert" role="alert"><span>{t("study.pageLoadFailed")}</span><button data-study-focus type="button" onClick={controller.refresh}>{t("study.retry")}</button></div> : null}
            {controller.snapshot.status === "error" && data ? <div className="kq-study-page-alert" role="alert"><span>{t("study.pageStale")}</span><button data-study-focus type="button" onClick={controller.refresh}>{t("study.retry")}</button></div> : null}
            <div className="kq-study-draft-layout">
              <div className="kq-study-draft-list-pane">
                <label className="kq-study-draft-filter">{t("study.draftFilter")}
                  <select data-study-focus value={kind} onChange={(event) => { setKind(event.target.value); setSelectedId(""); }}>
                    <option value="all">{t("study.draftAllKinds")}</option>
                    {kinds.map((nextKind) => <option key={nextKind} value={nextKind}>{kindLabel(nextKind, t)} ({data?.kindCounts[nextKind] ?? 0})</option>)}
                  </select>
                </label>
                {filtered.length ? <ul className="kq-study-draft-list">
                  {filtered.map((item) => (
                    <li key={item.artifact_id}>
                      <button
                        data-study-focus
                        type="button"
                        aria-pressed={selectedId === item.artifact_id}
                        onClick={() => setSelectedId(item.artifact_id)}
                      >
                        <strong>{item.title}</strong>
                        <span>{kindLabel(item.kind, t)} · {item.review?.status ?? item.status}</span>
                      </button>
                    </li>
                  ))}
                </ul> : <p className="kq-study-muted">{t("study.noDrafts")}</p>}
                {data?.truncated ? <button data-study-focus type="button" className="kq-study-secondary-button" onClick={controller.loadMore}>{t("study.loadMore")}</button> : null}
              </div>
              <div className="kq-study-draft-detail-pane">
                {!selected ? <p className="kq-study-muted">{t("study.draftSelectHint")}</p> : null}
                {selected && detail?.status === "loading" && !openedDetail ? <p role="status">{t("study.draftLoading")}</p> : null}
                {selected && detail?.status === "error" && !openedDetail ? <div className="kq-study-page-alert" role="alert"><span>{t("study.draftDetailFailed")}</span><button data-study-focus type="button" onClick={() => controller.openDetail(selected.artifact_id, { force: true })}>{t("study.retry")}</button></div> : null}
                {selected && openedDetail ? (
                  <>
                    <h3>{openedDetail.title}</h3>
                    <p className="kq-study-muted">{kindLabel(selected.kind, t)} · {openedDetail.review.status ?? selected.status}</p>
                    {openedDetail.kind === "knowledge_base" || openedDetail.kind === "resource_pack" || openedDetail.kind === "tutoring_note"
                      ? <LearnArtifactContent detail={openedDetail} />
                      : <p className="kq-study-draft-preview">{t("study.draftDetailPrivate")}</p>}
                    <ArtifactAdvancedPanel spaceId={controller.spaceId} detail={openedDetail} onArtifactStale={() => controller.invalidateArtifact(openedDetail.artifactId)} />
                    {needsReview ? <p className="kq-study-page-alert" role="status">{t("study.draftReviewRequired")}</p> : null}
                    {actionError ? <p className="kq-study-page-error" role="alert">{t("study.draftActionFailed")}</p> : null}
                    <div className="kq-study-inline-actions">
                      {needsReview ? <button data-study-focus type="button" disabled={Boolean(action)} onClick={() => controller.review(selected.artifact_id)}>{action === "review" ? t("study.draftReviewing") : t("study.draftRetryReview")}</button> : null}
                      <button data-study-focus type="button" disabled={Boolean(action) || Boolean(needsReview)} onClick={() => controller.activate(selected.artifact_id)}>{t("study.flyleafInk")}</button>
                      <button data-study-focus type="button" disabled={Boolean(action)} onClick={() => controller.reject(selected.artifact_id)}>{t("study.flyleafErase")}</button>
                      {pageForKind(selected.kind) ? <button data-study-focus type="button" onClick={() => { navigate(studyPath(controller.spaceId, pageForKind(selected.kind)!)); closeDialog(); }}>{t("study.draftOpenPage")}</button> : null}
                    </div>
                  </>
                ) : null}
              </div>
            </div>
          </section>
        </div>,
        document.body,
      ) : null}
    </>
  );
}
