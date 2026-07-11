// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import type { StudyStudentStatePayload } from "../../chat/study/study-api";
import { loadStudyContext, type StudyContext } from "../../chat/study/studyStore";
import { useI18n } from "../../lib/i18n";
import { RequestCoordinator, type Loadable } from "../loadable";
import type { StudyFlyleafSnapshot } from "../repository";
import { useStudyRepository } from "../repositoryContext";

const STUDY_LEARNING_EVENT = "study-learning-event";

function hasLegacyContext(context: StudyContext): boolean {
  return Object.values(context).some((value) => value.trim().length > 0);
}

function payloadRows(
  payload: StudyStudentStatePayload,
  labels: Record<string, string>,
): Array<{ key: string; label: string; value: string }> {
  const preferences = Object.entries(payload.preferences ?? {})
    .map(([key, value]) => `${key}: ${value}`)
    .join(" · ");
  return [
    { key: "course", label: labels.course, value: payload.course ?? "" },
    { key: "goals", label: labels.goals, value: (payload.goals ?? []).join("；") },
    { key: "preferences", label: labels.preferences, value: preferences },
    { key: "constraints", label: labels.constraints, value: (payload.constraints ?? []).join("；") },
    { key: "progress", label: labels.progress, value: (payload.progress_notes ?? []).join("；") },
    { key: "stage", label: labels.stage, value: payload.current_stage ?? "" },
    { key: "adjustment", label: labels.adjustment, value: payload.next_adjustment ?? "" },
  ].filter((row) => row.value.trim().length > 0);
}

export function FlyleafPage({ spaceId }: { spaceId: string }) {
  const { t } = useI18n();
  const repository = useStudyRepository();
  const heading = useRef<HTMLHeadingElement>(null);
  const requests = useRef(new RequestCoordinator());
  const mutations = useRef(new RequestCoordinator());
  const migrationAttempted = useRef("");
  const [snapshot, setSnapshot] = useState<Loadable<StudyFlyleafSnapshot>>({ status: "idle" });
  const [pendingDraft, setPendingDraft] = useState(false);
  const [draftError, setDraftError] = useState(false);
  const [migrationError, setMigrationError] = useState(false);

  const load = useCallback(() => {
    const request = requests.current.begin();
    setSnapshot((current) => ({
      status: "loading",
      ...(current.status === "ready" ? { previous: current.data } : {}),
      ...(current.status === "error" && current.previous ? { previous: current.previous } : {}),
    }));
    void repository.loadFlyleaf(spaceId, request.signal).then(
      (data) => {
        if (requests.current.isCurrent(request.generation)) {
          setSnapshot({ status: "ready", data });
        }
      },
      (error) => {
        if (!requests.current.isCurrent(request.generation)) return;
        setSnapshot((current) => ({
          status: "error",
          error,
          ...(current.status === "loading" && current.previous
            ? { previous: current.previous }
            : {}),
        }));
      },
    );
  }, [repository, spaceId]);

  const migrateLegacy = useCallback(() => {
    const legacy = loadStudyContext();
    if (!hasLegacyContext(legacy)) return;
    const request = mutations.current.begin();
    setMigrationError(false);
    void repository.migrateLegacyContext(spaceId, legacy, request.signal).then(
      () => {
        if (!mutations.current.isCurrent(request.generation)) return;
        load();
        window.dispatchEvent(new Event(STUDY_LEARNING_EVENT));
      },
      () => {
        if (mutations.current.isCurrent(request.generation)) setMigrationError(true);
      },
    );
  }, [load, repository, spaceId]);

  useEffect(() => {
    const activeRequests = requests.current;
    const activeMutations = mutations.current;
    heading.current?.focus();
    load();
    const refresh = () => load();
    window.addEventListener(STUDY_LEARNING_EVENT, refresh);
    if (migrationAttempted.current !== spaceId) {
      migrationAttempted.current = spaceId;
      migrateLegacy();
    }
    return () => {
      window.removeEventListener(STUDY_LEARNING_EVENT, refresh);
      activeRequests.cancel();
      activeMutations.cancel();
    };
  }, [load, migrateLegacy, spaceId]);

  const data = snapshot.status === "ready"
    ? snapshot.data
    : snapshot.status === "loading" || snapshot.status === "error"
      ? snapshot.previous
      : undefined;
  const labels = useMemo(() => ({
    course: t("study.flyleafCourse"),
    goals: t("study.flyleafGoals"),
    preferences: t("study.flyleafPreferences"),
    constraints: t("study.flyleafConstraints"),
    progress: t("study.flyleafProgress"),
    stage: t("study.flyleafStage"),
    adjustment: t("study.flyleafAdjustment"),
  }), [t]);

  const updateDraft = (status: "active" | "rejected") => {
    if (!data?.draft || pendingDraft) return;
    const draft = data.draft;
    const request = mutations.current.begin();
    setPendingDraft(true);
    setDraftError(false);
    void repository.setArtifactStatus(spaceId, draft.artifact_id, status, request.signal).then(
      () => {
        if (!mutations.current.isCurrent(request.generation)) return;
        setPendingDraft(false);
        setSnapshot({
          status: "ready",
          data: {
            active: status === "active" ? { ...draft, status: "active" } : data.active,
            draft: null,
          },
        });
        window.dispatchEvent(new Event(STUDY_LEARNING_EVENT));
      },
      () => {
        if (!mutations.current.isCurrent(request.generation)) return;
        setPendingDraft(false);
        setDraftError(true);
      },
    );
  };

  return (
    <section className="kq-study-content-page" aria-labelledby="study-page-title">
      <header className="kq-study-page-heading">
        <p className="kq-study-placeholder-kicker">{t("study.lifecycle")}</p>
        <h1 id="study-page-title" ref={heading} tabIndex={-1}>{t("study.pageFlyleaf")}</h1>
        <p>{t("study.flyleafLead")}</p>
      </header>

      {snapshot.status === "loading" && !data ? <p role="status">{t("study.pageLoading")}</p> : null}
      {snapshot.status === "error" && !data ? (
        <div className="kq-study-page-alert" role="alert">
          <p>{t("study.pageLoadFailed")}</p>
          <button type="button" onClick={load}>{t("study.retry")}</button>
          <Link to="/chat">{t("study.backToChat")}</Link>
        </div>
      ) : null}
      {snapshot.status === "error" && data ? (
        <div className="kq-study-page-alert" role="alert">
          <span>{t("study.pageStale")}</span>
          <button type="button" onClick={load}>{t("study.retry")}</button>
        </div>
      ) : null}
      {migrationError ? (
        <div className="kq-study-page-alert" role="alert">
          <span>{t("study.flyleafMigrationFailed")}</span>
          <button type="button" onClick={migrateLegacy}>{t("study.retry")}</button>
        </div>
      ) : null}

      {data?.draft ? (
        <article className="kq-study-flyleaf-card is-pencil">
          <div className="kq-study-card-title">
            <div>
              <p>{t("study.flyleafDraftKicker")}</p>
              <h2>{t("study.flyleafDraftTitle")}</h2>
            </div>
            <div className="kq-study-inline-actions">
              <button type="button" disabled={pendingDraft} onClick={() => updateDraft("active")}>
                {t("study.flyleafInk")}
              </button>
              <button type="button" disabled={pendingDraft} onClick={() => updateDraft("rejected")}>
                {t("study.flyleafErase")}
              </button>
            </div>
          </div>
          <dl className="kq-study-flyleaf-rows">
            {payloadRows(data.draft.payload, labels).map((row) => (
              <div key={row.key}><dt>{row.label}</dt><dd>{row.value}</dd></div>
            ))}
          </dl>
          {draftError ? <p className="kq-study-page-error" role="alert">{t("study.flyleafDraftFailed")}</p> : null}
        </article>
      ) : null}

      {data?.active ? (
        <article className="kq-study-flyleaf-card is-ink">
          <div className="kq-study-card-title">
            <div><p>{t("study.flyleafInkKicker")}</p><h2>{t("study.flyleafInkTitle")}</h2></div>
          </div>
          <dl className="kq-study-flyleaf-rows">
            {payloadRows(data.active.payload, labels).map((row) => (
              <div key={row.key}><dt>{row.label}</dt><dd>{row.value}</dd></div>
            ))}
          </dl>
        </article>
      ) : null}

      {data && !data.active && !data.draft ? (
        <div className="kq-study-page-empty">
          <h2>{t("study.flyleafEmptyTitle")}</h2>
          <p>{t("study.flyleafEmptyBody")}</p>
          <Link className="kq-study-primary-link" to="/chat">{t("study.askNana")}</Link>
        </div>
      ) : null}
    </section>
  );
}
