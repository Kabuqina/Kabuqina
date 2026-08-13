// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { FileStack, X } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useLocation, useNavigate } from "react-router-dom";
import { useI18n } from "../lib/i18n";
import { type StudyArtifactSummary } from "../chat/study/study-api";
import { ArtifactAdvancedPanel } from "./ArtifactAdvancedPanel";
import { useStudyDrafts } from "./DraftContext";
import { LearnArtifactContent } from "./LearnArtifactContent";
import type { Loadable } from "./loadable";
import type { StudyArtifactDetail } from "./repository";
import { studyPath, type StudyPageSlug } from "./routeModel";
import { onStudyDraftRequest } from "./studyDraftRequest";
import { requestStudyMaterial } from "./studyMaterialRequest";

const EXTERNAL_REVIEW_KINDS = new Set([
  "knowledge_base",
  "material_alignment",
  "resource_pack",
  "flashcard_deck",
  "tutoring_note",
]);

function pageForKind(kind: string): StudyPageSlug | null {
  if (kind === "student_state") return "flyleaf";
  if (kind === "learning_plan") return "plan";
  if (kind === "knowledge_base" || kind === "resource_pack" || kind === "tutoring_note") return "learn";
  if (kind === "material_alignment") return "learn";
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

function boundedText(value: unknown, limit = 800): string {
  return typeof value === "string" ? value.trim().slice(0, limit) : "";
}

function questionSourceLabel(value: unknown): string {
  if (typeof value === "string") return boundedText(value, 240);
  if (!value || typeof value !== "object" || Array.isArray(value)) return "";
  const ref = value as Record<string, unknown>;
  const field = (key: string) => {
    const next = ref[key];
    return typeof next === "string" || typeof next === "number" ? String(next).trim() : "";
  };
  return [
    field("title") || field("material_title") || field("source_label"),
    field("section") || field("section_title"),
    field("locator") || field("source_ref") || (field("page") ? `第 ${field("page")} 页` : ""),
  ].filter(Boolean).join(" · ").slice(0, 240);
}

function QuizDraftPreview({ detail }: { detail: StudyArtifactDetail }) {
  const payload = detail.envelope.payload;
  const questions = payload && typeof payload === "object" && !Array.isArray(payload)
    ? (payload as { questions?: unknown }).questions
    : undefined;
  const safeQuestions = Array.isArray(questions)
    ? questions.filter((question): question is Record<string, unknown> => (
      Boolean(question) && typeof question === "object" && !Array.isArray(question)
    )).slice(0, 6)
    : [];
  if (!safeQuestions.length) return <p className="kq-study-draft-preview">这份练习草稿暂时无法预览。</p>;
  return (
    <div className="kq-study-quiz-draft-preview" aria-label="练习草稿预览">
      {safeQuestions.map((question, index) => {
        const origin = question.origin === "source"
          ? "资料原题"
          : question.origin === "adapted"
            ? "根据资料改编"
            : question.origin === "generated"
              ? "小娜生成"
              : "练习草稿";
        const refs = Array.isArray(question.source_refs) ? question.source_refs : [];
        const source = questionSourceLabel(refs[0]);
        return (
          <article key={`${index}:${boundedText(question.prompt, 120)}`}>
            <p><strong>{origin}</strong>{source ? <span>{source}</span> : null}</p>
            <h4>{boundedText(question.prompt) || "未命名题目"}</h4>
          </article>
        );
      })}
    </div>
  );
}

function courseCoreCards(detail: StudyArtifactDetail): Record<string, unknown>[] {
  if (detail.kind !== "flashcard_deck") return [];
  const payload = detail.envelope.payload;
  const cards = payload && typeof payload === "object" && !Array.isArray(payload)
    ? (payload as { cards?: unknown }).cards
    : undefined;
  return Array.isArray(cards)
    ? cards.filter((card): card is Record<string, unknown> => (
      Boolean(card)
      && typeof card === "object"
      && !Array.isArray(card)
      && typeof (card as Record<string, unknown>).knowledge_core_id === "string"
    )).slice(0, 30)
    : [];
}

function sourceTarget(value: unknown): { artifactId: string; page?: number } | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  const ref = value as Record<string, unknown>;
  const artifactId = [ref.artifactId, ref.artifact_id, ref.material_id]
    .find((candidate) => typeof candidate === "string" && candidate.trim());
  if (typeof artifactId !== "string") return null;
  const directPage = Number(ref.page ?? ref.pageStart ?? ref.page_start);
  const locator = typeof ref.locator === "string" ? ref.locator : "";
  const locatorPage = Number(locator.match(/\d+/)?.[0]);
  const page = Number.isInteger(directPage) && directPage > 0
    ? directPage
    : Number.isInteger(locatorPage) && locatorPage > 0 ? locatorPage : undefined;
  return { artifactId, ...(page ? { page } : {}) };
}

function KnowledgeCoreDraftPreview({
  detail,
  onOpenSource,
}: {
  detail: StudyArtifactDetail;
  onOpenSource: (target: { artifactId: string; page?: number }) => void;
}) {
  const cards = courseCoreCards(detail);
  if (!cards.length) return <p className="kq-study-draft-preview">这份卡片草稿暂时无法预览。</p>;
  return (
    <div className="kq-study-quiz-draft-preview" aria-label="知识核草稿预览">
      {cards.map((card, index) => {
        const refs = Array.isArray(card.source_refs) ? card.source_refs : [];
        const source = questionSourceLabel(refs[0]);
        const target = sourceTarget(refs[0]);
        return (
          <article key={`${index}:${boundedText(card.front, 120)}`}>
            <p>
              <strong>学习知识核</strong>
              {source && target ? (
                <button
                  type="button"
                  onClick={() => onOpenSource(target)}
                >
                  {source}
                </button>
              ) : source ? <span>{source}</span> : null}
            </p>
            <h4>{boundedText(card.front) || "未命名知识核"}</h4>
            <p>{boundedText(card.back) || "暂时没有关键说明"}</p>
          </article>
        );
      })}
    </div>
  );
}

export function DraftInboxButton({
  onActivated,
}: {
  onActivated?: (item: StudyArtifactSummary, detail: StudyArtifactDetail) => void | Promise<void>;
} = {}) {
  const { t } = useI18n();
  const navigate = useNavigate();
  const location = useLocation();
  const controller = useStudyDrafts();
  const trigger = useRef<HTMLButtonElement>(null);
  const dialog = useRef<HTMLDivElement>(null);
  const close = useRef<HTMLButtonElement>(null);
  const requestedId = useRef("");
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
  const needsReview = Boolean(
    openedDetail
    && EXTERNAL_REVIEW_KINDS.has(openedDetail.kind)
    && openedDetail.review.mode === "semantic"
    && openedDetail.review.status !== "passed",
  );

  const closeDialog = useCallback(() => {
    setOpen(false);
    requestAnimationFrame(() => trigger.current?.focus());
  }, []);

  useEffect(() => onStudyDraftRequest((request) => {
    if (request.spaceId !== controller.spaceId) return;
    requestedId.current = request.artifactId;
    setKind("all");
    setSelectedId(request.artifactId);
    setOpen(true);
    controller.refresh();
  }), [controller]);

  useEffect(() => {
    const artifactId = new URLSearchParams(location.search).get("draft")?.trim();
    if (!artifactId) return;
    requestedId.current = artifactId;
    setKind("all");
    setSelectedId(artifactId);
    setOpen(true);
    controller.refresh();
    navigate(location.pathname, { replace: true });
  }, [controller, location.pathname, location.search, navigate]);

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
    if (requestedId.current && items.some((item) => item.artifact_id === requestedId.current)) {
      setSelectedId(requestedId.current);
      requestedId.current = "";
      return;
    }
    if (
      selectedId
      && !requestedId.current
      && controller.snapshot.status === "ready"
      && !items.some((item) => item.artifact_id === selectedId)
    ) setSelectedId("");
  }, [controller.snapshot.status, items, selectedId]);

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

  const activateSelected = async () => {
    if (!selected || !openedDetail) return;
    const activated = await controller.activate(selected.artifact_id);
    if (!activated) return;
    const isCourseCoreDeck = courseCoreCards(openedDetail).length > 0;
    if (selected.kind !== "quiz" && !isCourseCoreDeck) return;
    closeDialog();
    if (selected.kind === "quiz" && onActivated) {
      await onActivated(selected, openedDetail);
      return;
    }
    const destination = isCourseCoreDeck ? "learn" : pageForKind(selected.kind);
    if (destination) navigate(studyPath(controller.spaceId, destination));
  };

  return (
    <>
      {/* 降权（v0.5.0）：没有待采用的草稿时，这颗触发钮根本不渲染——它不再是
          常驻的「收件箱」。但整个组件保持挂载：Activity 的「查看草稿」深链和
          onStudyDraftRequest 事件仍要能把复核对话框拉起来（open 时也渲染触发钮）。 */}
      {total > 0 || open ? (
        <button
          ref={trigger}
          type="button"
          className="kq-study-top-action"
          aria-expanded={open}
          aria-haspopup="dialog"
          onClick={() => setOpen(true)}
        >
          <FileStack aria-hidden />
          <span>{t("study.drafts")}</span>
          <span className="kq-study-count" aria-label={t("study.draftCount", { count: total })}>{displayCount}</span>
        </button>
      ) : null}
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
                    {openedDetail.kind === "quiz"
                      ? <QuizDraftPreview detail={openedDetail} />
                      : openedDetail.kind === "flashcard_deck"
                      ? (
                        <KnowledgeCoreDraftPreview
                          detail={openedDetail}
                          onOpenSource={(target) => {
                            closeDialog();
                            requestStudyMaterial({ spaceId: controller.spaceId, ...target });
                          }}
                        />
                      )
                      : openedDetail.kind === "knowledge_base" || openedDetail.kind === "resource_pack" || openedDetail.kind === "tutoring_note"
                      ? <LearnArtifactContent detail={openedDetail} />
                      : <p className="kq-study-draft-preview">{t("study.draftDetailPrivate")}</p>}
                    <ArtifactAdvancedPanel spaceId={controller.spaceId} detail={openedDetail} onArtifactStale={() => controller.invalidateArtifact(openedDetail.artifactId)} />
                    {needsReview ? <p className="kq-study-page-alert" role="status">{t("study.draftReviewRequired")}</p> : null}
                    {actionError ? <p className="kq-study-page-error" role="alert">{t("study.draftActionFailed")}</p> : null}
                    <div className="kq-study-inline-actions">
                      {needsReview ? <button data-study-focus type="button" disabled={Boolean(action)} onClick={() => controller.review(selected.artifact_id)}>{action === "review" ? t("study.draftReviewing") : t("study.draftRetryReview")}</button> : null}
                      <button data-study-focus type="button" disabled={Boolean(action) || Boolean(needsReview)} onClick={() => { void activateSelected(); }}>{selected.kind === "quiz" ? t("study.practiceDraftAdopt") : courseCoreCards(openedDetail).length ? "采用知识核" : t("study.flyleafInk")}</button>
                      <button data-study-focus type="button" disabled={Boolean(action)} onClick={() => controller.reject(selected.artifact_id)}>{selected.kind === "quiz" ? t("study.practiceDraftReject") : t("study.flyleafErase")}</button>
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
