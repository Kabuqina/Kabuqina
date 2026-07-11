// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import type {
  StudyActivitiesResponse,
  StudyWrongbookResponse,
} from "../../chat/study/study-api";
import { useI18n } from "../../lib/i18n";
import { RequestCoordinator, type Loadable } from "../loadable";
import type { StudyEvaluationSnapshot } from "../repository";
import { useStudyRepository } from "../repositoryContext";
import { studyPath } from "../routeModel";

const STUDY_LEARNING_EVENT = "study-learning-event";

function retained<T>(state: Loadable<T>): T | undefined {
  if (state.status === "ready") return state.data;
  if (state.status === "loading" || state.status === "error") return state.previous;
  return undefined;
}

function SectionState<T>({ state, retry, empty, children }: {
  state: Loadable<T>;
  retry: () => void;
  empty: ReactNode;
  children: (data: T) => ReactNode;
}) {
  const { t } = useI18n();
  const data = retained(state);
  return (
    <>
      {state.status === "loading" && !data ? <p role="status">{t("study.pageLoading")}</p> : null}
      {state.status === "error" && !data ? (
        <div className="kq-study-page-alert" role="alert">
          <span>{t("study.pageLoadFailed")}</span>
          <button type="button" onClick={retry}>{t("study.retry")}</button>
        </div>
      ) : null}
      {state.status === "error" && data ? (
        <div className="kq-study-page-alert" role="alert">
          <span>{t("study.pageStale")}</span>
          <button type="button" onClick={retry}>{t("study.retry")}</button>
        </div>
      ) : null}
      {data ? children(data) : state.status === "ready" ? empty : null}
    </>
  );
}

function shortTime(value: string): string {
  return value ? value.replace("T", " ").slice(0, 16) : "";
}

export function EvaluatePage({ spaceId }: { spaceId: string }) {
  const { t } = useI18n();
  const repository = useStudyRepository();
  const heading = useRef<HTMLHeadingElement>(null);
  const wrongbookRequests = useRef(new RequestCoordinator());
  const evaluationRequests = useRef(new RequestCoordinator());
  const activityRequests = useRef(new RequestCoordinator());
  const [wrongbook, setWrongbook] = useState<Loadable<StudyWrongbookResponse>>({ status: "idle" });
  const [evaluation, setEvaluation] = useState<Loadable<StudyEvaluationSnapshot>>({ status: "idle" });
  const [activities, setActivities] = useState<Loadable<StudyActivitiesResponse>>({ status: "idle" });

  const loadWrongbook = useCallback(() => {
    const request = wrongbookRequests.current.begin();
    setWrongbook((current) => ({ status: "loading", ...(retained(current) ? { previous: retained(current) } : {}) }));
    void repository.loadWrongbook(spaceId, request.signal).then(
      (data) => { if (wrongbookRequests.current.isCurrent(request.generation)) setWrongbook({ status: "ready", data }); },
      (error) => { if (wrongbookRequests.current.isCurrent(request.generation)) setWrongbook((current) => ({ status: "error", error, ...(retained(current) ? { previous: retained(current) } : {}) })); },
    );
  }, [repository, spaceId]);

  const loadEvaluation = useCallback(() => {
    const request = evaluationRequests.current.begin();
    setEvaluation((current) => ({ status: "loading", ...(retained(current) ? { previous: retained(current) } : {}) }));
    void repository.loadLatestEvaluation(spaceId, request.signal).then(
      (data) => { if (evaluationRequests.current.isCurrent(request.generation)) setEvaluation({ status: "ready", data }); },
      (error) => { if (evaluationRequests.current.isCurrent(request.generation)) setEvaluation((current) => ({ status: "error", error, ...(retained(current) ? { previous: retained(current) } : {}) })); },
    );
  }, [repository, spaceId]);

  const loadActivities = useCallback(() => {
    const request = activityRequests.current.begin();
    setActivities((current) => ({ status: "loading", ...(retained(current) ? { previous: retained(current) } : {}) }));
    void repository.loadActivities(spaceId, request.signal).then(
      (data) => { if (activityRequests.current.isCurrent(request.generation)) setActivities({ status: "ready", data }); },
      (error) => { if (activityRequests.current.isCurrent(request.generation)) setActivities((current) => ({ status: "error", error, ...(retained(current) ? { previous: retained(current) } : {}) })); },
    );
  }, [repository, spaceId]);

  useEffect(() => {
    const wrongbookCoordinator = wrongbookRequests.current;
    const evaluationCoordinator = evaluationRequests.current;
    const activityCoordinator = activityRequests.current;
    heading.current?.focus();
    const loadAll = () => { loadWrongbook(); loadEvaluation(); loadActivities(); };
    loadAll();
    window.addEventListener(STUDY_LEARNING_EVENT, loadAll);
    return () => {
      window.removeEventListener(STUDY_LEARNING_EVENT, loadAll);
      wrongbookCoordinator.cancel();
      evaluationCoordinator.cancel();
      activityCoordinator.cancel();
    };
  }, [loadActivities, loadEvaluation, loadWrongbook]);

  return (
    <section className="kq-study-content-page" aria-labelledby="study-page-title">
      <header className="kq-study-page-heading">
        <p className="kq-study-placeholder-kicker">{t("study.lifecycle")}</p>
        <h1 id="study-page-title" ref={heading} tabIndex={-1}>{t("study.pageEvaluate")}</h1>
        <p>{t("study.evaluateLead")}</p>
      </header>

      <section className="kq-study-evaluate-section" aria-labelledby="wrongbook-title">
        <h2 id="wrongbook-title">{t("study.wrongbookTitle")}</h2>
        <SectionState state={wrongbook} retry={loadWrongbook} empty={<p>{t("study.wrongbookEmpty")}</p>}>
          {(data) => data.evidence.length ? (
            <>
              {data.weak_points.length ? <div className="kq-study-weak-tags">{data.weak_points.map((point) => <span key={point}>{point}</span>)}</div> : null}
              <ol className="kq-study-wrongbook-list">
                {data.evidence.map((item) => (
                  <li key={item.activity_id}>
                    <div>
                      <strong>{t("study.wrongbookScore", { score: item.score, max: item.max_score, percent: item.percent })}</strong>
                      <p>{item.weak_tags.join(" · ") || t("study.wrongbookNoTags")}</p>
                      <time dateTime={item.created_at}>{shortTime(item.created_at)}</time>
                    </div>
                    <Link to={`${studyPath(spaceId, "practice")}?source=wrongbook&activityId=${encodeURIComponent(item.activity_id)}`}>
                      {t("study.wrongbookRetry")}
                    </Link>
                  </li>
                ))}
              </ol>
              {data.truncated ? <p className="kq-study-muted">{t("study.listTruncated", { count: data.returned, total: data.count })}</p> : null}
            </>
          ) : <p>{t("study.wrongbookEmpty")}</p>}
        </SectionState>
      </section>

      <section className="kq-study-evaluate-section" aria-labelledby="evaluation-title">
        <h2 id="evaluation-title">{t("study.latestEvaluationTitle")}</h2>
        <SectionState state={evaluation} retry={loadEvaluation} empty={<p>{t("study.latestEvaluationEmpty")}</p>}>
          {(data) => data.evaluation ? (
            <div className="kq-study-evaluation-note">
              <h3>{data.evaluation.title}</h3>
              <ul>{data.evaluation.payload.observations.map((value) => <li key={value}>{value}</li>)}</ul>
              {data.evaluation.payload.suggestions.length ? (
                <><h4>{t("study.evaluationSuggestions")}</h4><ul>{data.evaluation.payload.suggestions.map((value) => <li key={value}>{value}</li>)}</ul></>
              ) : null}
            </div>
          ) : <p>{t("study.latestEvaluationEmpty")}</p>}
        </SectionState>
      </section>

      <section className="kq-study-evaluate-section" aria-labelledby="activity-title">
        <h2 id="activity-title">{t("study.activityTitle")}</h2>
        <p className="kq-study-muted">{t("study.activityLead")}</p>
        <SectionState state={activities} retry={loadActivities} empty={<p>{t("study.activityEmpty")}</p>}>
          {(data) => data.items.length ? (
            <>
              <ol className="kq-study-activity-list">
                {data.items.map((item) => (
                  <li key={item.activity_id}>
                    <time dateTime={item.created_at}>{shortTime(item.created_at)}</time>
                    <span>{t("study.activityEvent", { type: item.activity_type })}</span>
                  </li>
                ))}
              </ol>
              {data.truncated ? <p className="kq-study-muted">{t("study.listTruncated", { count: data.returned, total: data.count })}</p> : null}
            </>
          ) : <p>{t("study.activityEmpty")}</p>}
        </SectionState>
      </section>
    </section>
  );
}
