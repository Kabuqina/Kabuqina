// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useI18n } from "../../lib/i18n";
import { RequestCoordinator, type Loadable } from "../loadable";
import { STUDY_LEARNING_EVENT } from "../learningEvent";
import type { StudyPlanSnapshot } from "../repository";
import { useStudyRepository } from "../repositoryContext";
import { useStudyIa } from "../StudyIaContext";

export function PlanPage({ spaceId }: { spaceId: string }) {
  const { t } = useI18n();
  const repository = useStudyRepository();
  const recordIa = useStudyIa();
  const pageRegion = useRef<HTMLElement>(null);
  const requests = useRef(new RequestCoordinator());
  const mutations = useRef(new RequestCoordinator());
  const [snapshot, setSnapshot] = useState<Loadable<StudyPlanSnapshot>>({ status: "idle" });
  const [pendingItem, setPendingItem] = useState("");
  const [mutationError, setMutationError] = useState("");

  const load = useCallback(() => {
    const request = requests.current.begin();
    setSnapshot((current) => ({
      status: "loading",
      ...(current.status === "ready" ? { previous: current.data } : {}),
      ...(current.status === "error" && current.previous ? { previous: current.previous } : {}),
    }));
    void repository.loadPlan(spaceId, request.signal).then(
      (data) => {
        if (requests.current.isCurrent(request.generation)) setSnapshot({ status: "ready", data });
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
    const activeRequests = requests.current;
    const activeMutations = mutations.current;
    pageRegion.current?.focus();
    load();
    const refresh = () => load();
    window.addEventListener(STUDY_LEARNING_EVENT, refresh);
    return () => {
      window.removeEventListener(STUDY_LEARNING_EVENT, refresh);
      activeRequests.cancel();
      activeMutations.cancel();
    };
  }, [load]);

  const data = snapshot.status === "ready"
    ? snapshot.data
    : snapshot.status === "loading" || snapshot.status === "error"
      ? snapshot.previous
      : undefined;
  const items = data?.items ?? [];
  const currentItem = items.find((item) => item.status === "open") ?? null;
  const phases = [...new Set(items.map((item) => item.phaseTitle).filter(Boolean))];

  const continueCurrent = () => {
    if (!currentItem) return;
    recordIa({ name: "study.resume", page: "plan", action: "resume" });
    document.getElementById(`study-plan-item-${currentItem.item_id}`)?.focus();
  };

  const updateItem = (itemId: string, action: "complete" | "skip") => {
    if (pendingItem) return;
    const request = mutations.current.begin();
    setPendingItem(itemId);
    setMutationError("");
    const invoke = action === "complete"
      ? repository.completePlanItem(spaceId, itemId, request.signal)
      : repository.skipPlanItem(spaceId, itemId, request.signal);
    void invoke.then(
      (updated) => {
        if (!mutations.current.isCurrent(request.generation)) return;
        setPendingItem("");
        setSnapshot((current) => {
          const present = current.status === "ready" ? current.data : data;
          return present ? {
            status: "ready",
            data: {
              ...present,
              items: present.items.map((item) => item.item_id === itemId ? updated : item),
            },
          } : current;
        });
        window.dispatchEvent(new Event(STUDY_LEARNING_EVENT));
      },
      () => {
        if (!mutations.current.isCurrent(request.generation)) return;
        setPendingItem("");
        setMutationError(itemId);
      },
    );
  };

  return (
    <section
      ref={pageRegion}
      className="kq-study-content-page"
      aria-label={t("study.pagePlan")}
      tabIndex={-1}
    >
      <header className="kq-study-page-heading">
        <p className="kq-study-placeholder-kicker">{t("study.lifecycle")}</p>
        <p>{t("study.planLead")}</p>
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

      {data?.plan ? (
        <>
          <article className="kq-study-plan-summary">
            <div>
              <p>{t("study.planCurrentPhase")}</p>
              <h2>{currentItem?.phaseTitle || phases.at(-1) || data.plan.title}</h2>
            </div>
            {currentItem ? (
              <button type="button" className="kq-study-bookmark" onClick={continueCurrent}>
                <span>{t("study.planResume")}</span>
                <small>{currentItem.title}</small>
              </button>
            ) : <span className="kq-study-muted">{t("study.planAllDone")}</span>}
          </article>

          {phases.length ? (
            <div className="kq-study-phase-list" aria-label={t("study.planRecentPhases")}>
              <span>{t("study.planRecentPhases")}</span>
              {phases.slice(-3).map((phase) => <span key={phase}>{phase}</span>)}
            </div>
          ) : null}

          <ol className="kq-study-plan-items">
            {items.map((item) => (
              <li
                id={`study-plan-item-${item.item_id}`}
                key={item.item_id}
                tabIndex={-1}
                className={`is-${item.status}`}
              >
                <div className="kq-study-plan-item-copy">
                  <span>{item.phaseTitle}</span>
                  <h3>{item.title}</h3>
                  {item.done_when ? <p>{t("study.planDoneWhen", { value: item.done_when })}</p> : null}
                  {item.note ? <p>{item.note}</p> : null}
                </div>
                {item.status === "open" ? (
                  <div className="kq-study-inline-actions">
                    <button type="button" disabled={pendingItem === item.item_id} onClick={() => updateItem(item.item_id, "complete")}>
                      {t("study.planComplete")}
                    </button>
                    <button type="button" disabled={pendingItem === item.item_id} onClick={() => updateItem(item.item_id, "skip")}>
                      {t("study.planSkip")}
                    </button>
                  </div>
                ) : <strong>{item.status === "completed" ? t("study.planCompleted") : t("study.planSkipped")}</strong>}
                {mutationError === item.item_id ? <p className="kq-study-page-error" role="alert">{t("study.planMutationFailed")}</p> : null}
              </li>
            ))}
          </ol>
        </>
      ) : null}

      {data && !data.plan ? (
        <div className="kq-study-page-empty">
          <h2>{t("study.planEmptyTitle")}</h2>
          <p>{t("study.planEmptyBody")}</p>
          <Link className="kq-study-primary-link" to="/chat">{t("study.askNana")}</Link>
        </div>
      ) : null}
    </section>
  );
}
