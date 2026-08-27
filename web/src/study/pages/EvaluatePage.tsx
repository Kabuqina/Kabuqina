// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { Link, useNavigate } from "react-router-dom";
import type {
  StudyWrongbookResponse,
} from "../../chat/study/study-api";
import { useI18n } from "../../lib/i18n";
import { RequestCoordinator, type Loadable } from "../loadable";
import { deriveStudyRequestState } from "../pageState";
import type { StudyEvaluationSnapshot } from "../repository";
import { useStudyRepository } from "../repositoryContext";
import { studyPath } from "../routeModel";
import { STUDY_LEARNING_EVENT } from "../learningEvent";
import { studyIaCountBucket } from "../iaEvents";
import { useStudyIa } from "../StudyIaContext";
import { degradeStudyLocation, selectKnowledgeCore } from "../studyLocation";

function retained<T>(state: Loadable<T>): T | undefined {
  return deriveStudyRequestState(state).data;
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
  const recordIa = useStudyIa();
  const navigate = useNavigate();
  const pageRegion = useRef<HTMLElement>(null);
  const wrongbookOpenSpace = useRef<string | null>(null);
  const wrongbookRequests = useRef(new RequestCoordinator());
  const evaluationRequests = useRef(new RequestCoordinator());
  const returnRequests = useRef(new RequestCoordinator());
  const [wrongbook, setWrongbook] = useState<Loadable<StudyWrongbookResponse>>({ status: "idle" });
  const [evaluation, setEvaluation] = useState<Loadable<StudyEvaluationSnapshot>>({ status: "idle" });
  const [returnPending, setReturnPending] = useState(false);
  const [returnError, setReturnError] = useState(false);
  const wrongbookData = retained(wrongbook);
  const evaluationData = retained(evaluation);
  const zeroEvidence = wrongbook.status === "ready"
    && evaluation.status === "ready"
    && !wrongbookData?.evidence.length
    && !wrongbookData?.weak_points.length
    && !evaluationData?.evaluation;

  const loadWrongbook = useCallback(() => {
    const request = wrongbookRequests.current.begin();
    setWrongbook((current) => ({ status: "loading", ...(retained(current) ? { previous: retained(current) } : {}) }));
    void repository.loadWrongbook(spaceId, request.signal).then(
      (data) => {
        if (!wrongbookRequests.current.isCurrent(request.generation)) return;
        setWrongbook({ status: "ready", data });
        if (wrongbookOpenSpace.current !== spaceId) {
          wrongbookOpenSpace.current = spaceId;
          recordIa({
            name: "study.wrongbook.open",
            page: "evaluate",
            action: "open",
            success: true,
            count_bucket: studyIaCountBucket(data.evidence.length + data.weak_points.length),
          });
        }
      },
      (error) => {
        if (!wrongbookRequests.current.isCurrent(request.generation)) return;
        setWrongbook((current) => ({ status: "error", error, ...(retained(current) ? { previous: retained(current) } : {}) }));
        if (wrongbookOpenSpace.current !== spaceId) {
          wrongbookOpenSpace.current = spaceId;
          recordIa({
            name: "study.wrongbook.open",
            page: "evaluate",
            action: "open",
            success: false,
            count_bucket: "zero",
          });
        }
      },
    );
  }, [recordIa, repository, spaceId]);

  const loadEvaluation = useCallback(() => {
    const request = evaluationRequests.current.begin();
    setEvaluation((current) => ({ status: "loading", ...(retained(current) ? { previous: retained(current) } : {}) }));
    void repository.loadLatestEvaluation(spaceId, request.signal).then(
      (data) => { if (evaluationRequests.current.isCurrent(request.generation)) setEvaluation({ status: "ready", data }); },
      (error) => { if (evaluationRequests.current.isCurrent(request.generation)) setEvaluation((current) => ({ status: "error", error, ...(retained(current) ? { previous: retained(current) } : {}) })); },
    );
  }, [repository, spaceId]);

  useEffect(() => {
    const wrongbookCoordinator = wrongbookRequests.current;
    const evaluationCoordinator = evaluationRequests.current;
    const returnCoordinator = returnRequests.current;
    pageRegion.current?.focus();
    const loadAll = () => { loadWrongbook(); loadEvaluation(); };
    loadAll();
    window.addEventListener(STUDY_LEARNING_EVENT, loadAll);
    return () => {
      window.removeEventListener(STUDY_LEARNING_EVENT, loadAll);
      wrongbookCoordinator.cancel();
      evaluationCoordinator.cancel();
      returnCoordinator.cancel();
    };
  }, [loadEvaluation, loadWrongbook]);

  const returnToLearning = (knowledgeCoreId: string, outlineNodeId?: string) => {
    if (returnPending) return;
    const request = returnRequests.current.begin();
    setReturnPending(true);
    setReturnError(false);
    void repository.loadLearnHome(spaceId, request.signal).then(
      (home) => {
        if (!returnRequests.current.isCurrent(request.generation)) return;
        setReturnPending(false);
        const point = home.knowledgePoints.find((candidate) => candidate.item_id === knowledgeCoreId);
        if (!point) {
          degradeStudyLocation(spaceId);
          navigate(studyPath(spaceId, "plan"));
          return;
        }
        selectKnowledgeCore(spaceId, point, "learn", { outlineNodeId });
        navigate(studyPath(spaceId, "learn"));
      },
      () => {
        if (!returnRequests.current.isCurrent(request.generation)) return;
        setReturnPending(false);
        setReturnError(true);
      },
    );
  };

  return (
    <section
      ref={pageRegion}
      className="kq-study-content-page"
      aria-label={t("study.pageEvaluate")}
      tabIndex={-1}
    >
      <header className="kq-study-page-heading">
        <p className="kq-study-placeholder-kicker">证据与调整</p>
        <p>只看最近可靠证据说明了什么，以及下一步回到哪里。</p>
      </header>

      {zeroEvidence ? (
        <div className="kq-study-page-empty">
          <h2>还没有可以评估的练习证据</h2>
          <p>完成一次可检查的练习后，这里会保留需要回访的证据和调整建议。</p>
          <div className="kq-study-inline-actions">
            <Link className="kq-study-primary-link" to={studyPath(spaceId, "practice")}>去练习</Link>
            <Link className="kq-study-secondary-link" to={studyPath(spaceId, "learn")}>回到学习</Link>
          </div>
        </div>
      ) : (
      <>
      <section className="kq-study-evaluate-section" aria-labelledby="wrongbook-title">
        <h2 id="wrongbook-title">{t("study.wrongbookTitle")}</h2>
        <SectionState state={wrongbook} retry={loadWrongbook} empty={<p>{t("study.wrongbookEmpty")}</p>}>
          {(data) => data.evidence.length || data.weak_points.length ? (
            <>
              {data.weak_points.length ? <div className="kq-study-weak-tags">{data.weak_points.map((point) => <span key={point}>{point}</span>)}</div> : null}
              {data.evidence.length ? <ol className="kq-study-wrongbook-list">
                {data.evidence.map((item) => (
                  <li key={item.activity_id}>
                    <div>
                      <strong>{t("study.wrongbookScore", { score: item.score, max: item.max_score, percent: item.percent })}</strong>
                      <p>{item.weak_tags.join(" · ") || t("study.wrongbookNoTags")}</p>
                      <time dateTime={item.created_at}>{shortTime(item.created_at)}</time>
                    </div>
                    <Link
                      to={studyPath(spaceId, "practice", `?source=wrongbook&activityId=${encodeURIComponent(item.activity_id)}`)}
                      onClick={() => recordIa({ name: "study.wrongbook.retry", page: "evaluate", action: "retry" })}
                    >
                      {t("study.wrongbookRetry")}
                    </Link>
                  </li>
                ))}
              </ol> : null}
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
              {(data.evaluation.evidence_refs ?? []).length ? (
                <>
                  <p className="kq-study-evidence-note">依据：{Math.min(data.evaluation.evidence_refs?.length ?? 0, 12)} 条已绑定记录</p>
                  <ul>{data.evaluation.observations.map((value) => <li key={value}>{value}</li>)}</ul>
                  {data.evaluation.suggestions.length ? (
                    <><h4>{t("study.evaluationSuggestions")}</h4><ul>{data.evaluation.suggestions.map((value) => <li key={value}>{value}</li>)}</ul></>
                  ) : null}
                  <div className="kq-study-inline-actions">
                    {data.evaluation.evidence_refs?.find((ref) => ref.activity_id)?.activity_id ? (
                      <Link to={studyPath(spaceId, "practice", `?source=wrongbook&activityId=${encodeURIComponent(data.evaluation.evidence_refs.find((ref) => ref.activity_id)!.activity_id)}`)}>
                        回到这条练习
                      </Link>
                    ) : null}
                    {data.evaluation.evidence_refs?.find((ref) => ref.knowledge_core_id)?.knowledge_core_id ? (
                      <button
                        type="button"
                        disabled={returnPending}
                        onClick={() => {
                          const ref = data.evaluation!.evidence_refs!.find((candidate) => candidate.knowledge_core_id)!;
                          returnToLearning(ref.knowledge_core_id, ref.outline_node_id);
                        }}
                      >
                        {returnPending ? "正在返回…" : "回学习"}
                      </button>
                    ) : null}
                  </div>
                  {returnError ? <p className="kq-study-page-error" role="alert">暂时无法定位这条学习证据，当前页面已保留。</p> : null}
                </>
              ) : <p className="kq-study-page-alert">这条评估还没有可追溯证据，暂不用于调整。</p>}
            </div>
          ) : <p>{t("study.latestEvaluationEmpty")}</p>}
        </SectionState>
      </section>
      </>
      )}

    </section>
  );
}
