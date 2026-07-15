// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { BookOpen, Lightbulb, PencilLine } from "lucide-react";
import { useI18n } from "../../lib/i18n";
import type { StudyArtifactSummary } from "../../chat/study/study-api";
import { ArtifactAdvancedPanel } from "../ArtifactAdvancedPanel";
import { useStudyDrafts } from "../DraftContext";
import { LearnArtifactContent } from "../LearnArtifactContent";
import { RequestCoordinator, type Loadable } from "../loadable";
import type { StudyArtifactDetail, StudyLearnHome } from "../repository";
import { useStudyRepository } from "../repositoryContext";
import { studyPath } from "../routeModel";

const M5_KINDS = ["knowledge_base", "resource_pack", "tutoring_note"] as const;
type M5Kind = (typeof M5_KINDS)[number];

function pageData(snapshot: Loadable<StudyLearnHome>): StudyLearnHome | undefined {
  if (snapshot.status === "ready") return snapshot.data;
  if (snapshot.status === "loading" || snapshot.status === "error") return snapshot.previous;
  return undefined;
}

function detailData(detail: Loadable<StudyArtifactDetail> | undefined): StudyArtifactDetail | undefined {
  if (!detail) return undefined;
  if (detail.status === "ready") return detail.data;
  return detail.status === "loading" || detail.status === "error" ? detail.previous : undefined;
}

function draftItems(snapshot: ReturnType<typeof useStudyDrafts>["snapshot"]): StudyArtifactSummary[] {
  const data = snapshot.status === "ready"
    ? snapshot.data
    : snapshot.status === "loading" || snapshot.status === "error"
      ? snapshot.previous
      : undefined;
  return (data?.items ?? []).filter((item) => M5_KINDS.includes(item.kind as M5Kind));
}

function kindTitle(kind: M5Kind, t: (key: string) => string): string {
  if (kind === "knowledge_base") return t("study.learnKnowledgeBase");
  if (kind === "resource_pack") return t("study.learnResources");
  return t("study.learnTutoringNotes");
}

function ArtifactChooser({
  kind,
  artifacts,
  selectedId,
  onSelect,
}: {
  kind: M5Kind;
  artifacts: StudyArtifactSummary[];
  selectedId: string;
  onSelect: (artifactId: string) => void;
}) {
  const { t } = useI18n();
  return (
    <section className="kq-study-learn-section" aria-labelledby={`learn-${kind}`}>
      <h2 id={`learn-${kind}`}>{kindTitle(kind, t)}</h2>
      {artifacts.length ? <div className="kq-study-inline-actions">{artifacts.map((artifact) => <button key={artifact.artifact_id} type="button" aria-pressed={selectedId === artifact.artifact_id} onClick={() => onSelect(artifact.artifact_id)}>{artifact.title}</button>)}</div> : <p className="kq-study-muted">{t("study.learnEmptyTitle")}</p>}
    </section>
  );
}

export function LearnPage({ spaceId }: { spaceId: string }) {
  const { t } = useI18n();
  const repository = useStudyRepository();
  const drafts = useStudyDrafts();
  const heading = useRef<HTMLHeadingElement>(null);
  const requests = useRef(new RequestCoordinator());
  const [snapshot, setSnapshot] = useState<Loadable<StudyLearnHome>>({ status: "idle" });
  const [selectedId, setSelectedId] = useState("");
  const [selectedDraftId, setSelectedDraftId] = useState("");
  const data = pageData(snapshot);
  const active = data?.artifacts ?? [];
  const selected = active.find((artifact) => artifact.artifact_id === selectedId) ?? null;
  const selectedDetail = selected ? drafts.details[selected.artifact_id] : undefined;
  const selectedData = detailData(selectedDetail);
  const pageDrafts = draftItems(drafts.snapshot);
  const selectedDraft = pageDrafts.find((artifact) => artifact.artifact_id === selectedDraftId) ?? null;
  const selectedDraftDetail = selectedDraft ? drafts.details[selectedDraft.artifact_id] : undefined;
  const selectedDraftData = detailData(selectedDraftDetail);
  const selectedDraftAction = selectedDraft ? drafts.actions[selectedDraft.artifact_id] : undefined;
  const selectedDraftError = selectedDraft ? drafts.actionErrors[selectedDraft.artifact_id] : undefined;
  const draftNeedsReview = selectedDraftData?.review.mode === "semantic" && selectedDraftData.review.status !== "passed";

  const load = useCallback(() => {
    const request = requests.current.begin();
    setSnapshot((current) => ({
      status: "loading",
      ...(current.status === "ready" ? { previous: current.data } : {}),
      ...(current.status === "error" && current.previous ? { previous: current.previous } : {}),
    }));
    void repository.loadLearnHome(spaceId, request.signal).then(
      (next) => {
        if (requests.current.isCurrent(request.generation)) setSnapshot({ status: "ready", data: next });
      },
      (error) => {
        if (!requests.current.isCurrent(request.generation)) return;
        setSnapshot((current) => ({
          status: "error",
          error,
          ...(current.status === "loading" && current.previous ? { previous: current.previous } : {}),
        }));
      },
    );
  }, [repository, spaceId]);

  useEffect(() => {
    const coordinator = requests.current;
    heading.current?.focus();
    setSelectedId("");
    setSelectedDraftId("");
    load();
    return () => coordinator.cancel();
  }, [load, spaceId]);

  useEffect(() => {
    if (selectedId || !active.length) return;
    setSelectedId(active[0].artifact_id);
  }, [active, selectedId]);

  useEffect(() => {
    if (!selected) return;
    drafts.openDetail(selected.artifact_id);
  }, [drafts, selected]);

  useEffect(() => {
    if (!selectedDraft) return;
    drafts.openDetail(selectedDraft.artifact_id);
  }, [drafts, selectedDraft]);

  const grouped = useMemo<Record<M5Kind, StudyArtifactSummary[]>>(() => ({
    knowledge_base: active.filter((artifact) => artifact.kind === "knowledge_base"),
    resource_pack: active.filter((artifact) => artifact.kind === "resource_pack"),
    tutoring_note: active.filter((artifact) => artifact.kind === "tutoring_note"),
  }), [active]);

  return (
    <section className="kq-study-content-page" aria-labelledby="study-page-title">
      <header className="kq-study-page-heading">
        <p className="kq-study-placeholder-kicker">{t("study.lifecycle")}</p>
        <h1 id="study-page-title" ref={heading} tabIndex={-1}>{t("study.pageLearn")}</h1>
        <p>{t("study.learnLead")}</p>
      </header>

      {snapshot.status === "loading" && !data ? <p role="status">{t("study.pageLoading")}</p> : null}
      {snapshot.status === "error" && !data ? <div className="kq-study-page-alert" role="alert"><span>{t("study.pageLoadFailed")}</span><button type="button" onClick={load}>{t("study.retry")}</button><Link to="/chat">{t("study.backToChat")}</Link></div> : null}
      {snapshot.status === "error" && data ? <div className="kq-study-page-alert" role="alert"><span>{t("study.pageStale")}</span><button type="button" onClick={load}>{t("study.retry")}</button></div> : null}
      {data?.unavailable?.length ? <div className="kq-study-page-alert" role="status"><span>{t("study.learnSectionUnavailable")}</span><button type="button" onClick={load}>{t("study.retry")}</button></div> : null}

      <section className="kq-study-learn-section kq-study-knowledge-points" aria-labelledby="learn-knowledge-points">
        <div className="kq-study-card-title"><div><p>{t("study.lifecycle")}</p><h2 id="learn-knowledge-points">{t("study.learnKnowledgePoints")}</h2></div><Lightbulb aria-hidden /></div>
        {data?.knowledgePoints.length ? <ul>{data.knowledgePoints.map((point) => <li key={point.item_id}><div><strong>{point.front}</strong><span>{point.gist}</span></div><span className="kq-study-chip"><BookOpen aria-hidden />{t("study.learnOpenPractice")}</span></li>)}</ul> : <p>{t("study.learnKnowledgePointsEmpty")}</p>}
        {data?.knowledgePoints.length ? <Link className="kq-study-secondary-link" to={studyPath(spaceId, "practice")}>{t("study.learnOpenPractice")}</Link> : null}
      </section>

      {data && !active.length ? <div className="kq-study-page-empty"><h2>{t("study.learnEmptyTitle")}</h2><p>{t("study.learnEmptyBody")}</p><Link className="kq-study-secondary-link" to="/chat">{t("study.backToChat")}</Link></div> : null}
      {data && active.length ? <div className="kq-study-learn-grid">
        <div className="kq-study-learn-navigation">
          {M5_KINDS.map((kind) => <ArtifactChooser key={kind} kind={kind} artifacts={grouped[kind]} selectedId={selectedId} onSelect={setSelectedId} />)}
        </div>
        <article className="kq-study-learn-reading" aria-live="polite">
          {!selected ? <p className="kq-study-muted">{t("study.learnSelectArtifact")}</p> : null}
          {selected && selectedDetail?.status === "loading" && !selectedData ? <p role="status">{t("study.learnDetailLoading")}</p> : null}
          {selected && selectedDetail?.status === "error" && !selectedData ? <div className="kq-study-page-alert" role="alert"><span>{t("study.learnDetailFailed")}</span><button type="button" onClick={() => drafts.openDetail(selected.artifact_id, { force: true })}>{t("study.retry")}</button></div> : null}
          {selected && selectedData ? <><h2>{selectedData.title}</h2><LearnArtifactContent detail={selectedData} /><ArtifactAdvancedPanel spaceId={spaceId} detail={selectedData} /></> : null}
        </article>
      </div> : null}

      {pageDrafts.length ? <section className="kq-study-learn-section kq-study-learn-drafts" aria-labelledby="learn-drafts">
        <div className="kq-study-card-title"><div><p><PencilLine aria-hidden /> {t("study.flyleafDraftKicker")}</p><h2 id="learn-drafts">{t("study.learnDrafts")}</h2></div></div>
        <div className="kq-study-inline-actions">{pageDrafts.map((draft) => <button key={draft.artifact_id} type="button" aria-pressed={selectedDraftId === draft.artifact_id} onClick={() => setSelectedDraftId(draft.artifact_id)}>{draft.title}</button>)}</div>
        {selectedDraft && selectedDraftDetail?.status === "loading" && !selectedDraftData ? <p role="status">{t("study.learnDetailLoading")}</p> : null}
        {selectedDraft && selectedDraftDetail?.status === "error" && !selectedDraftData ? <div className="kq-study-page-alert" role="alert"><span>{t("study.learnDetailFailed")}</span><button type="button" onClick={() => drafts.openDetail(selectedDraft.artifact_id, { force: true })}>{t("study.retry")}</button></div> : null}
        {selectedDraft && selectedDraftData ? <article className="kq-study-flyleaf-card is-pencil"><h3>{selectedDraftData.title}</h3><LearnArtifactContent detail={selectedDraftData} /><ArtifactAdvancedPanel spaceId={spaceId} detail={selectedDraftData} />{draftNeedsReview ? <p className="kq-study-page-alert" role="status">{t("study.draftReviewRequired")}</p> : null}{selectedDraftError ? <p className="kq-study-page-error" role="alert">{t("study.draftActionFailed")}</p> : null}<div className="kq-study-inline-actions">{draftNeedsReview ? <button type="button" disabled={Boolean(selectedDraftAction)} onClick={() => drafts.review(selectedDraft.artifact_id)}>{selectedDraftAction === "review" ? t("study.draftReviewing") : t("study.draftRetryReview")}</button> : null}<button type="button" disabled={Boolean(selectedDraftAction) || Boolean(draftNeedsReview)} onClick={() => drafts.activate(selectedDraft.artifact_id)}>{t("study.flyleafInk")}</button><button type="button" disabled={Boolean(selectedDraftAction)} onClick={() => drafts.reject(selectedDraft.artifact_id)}>{t("study.flyleafErase")}</button></div></article> : null}
      </section> : null}
    </section>
  );
}
