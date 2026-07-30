// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { Link, useNavigate } from "react-router-dom";
import type { StudyPlanItem } from "../../chat/study/study-api";
import { useI18n } from "../../lib/i18n";
import { RequestCoordinator, type Loadable } from "../loadable";
import { STUDY_LEARNING_EVENT } from "../learningEvent";
import type { StudyArtifactDetail, StudyOutlineNode, StudyPlanSnapshot } from "../repository";
import { useStudyRepository } from "../repositoryContext";
import { useStudyDrafts } from "../DraftContext";
import { resolveKnowledgeCore, selectKnowledgeCore } from "../studyLocation";
import { studyPath } from "../routeModel";

type PlanActionMode = "learn" | "practice" | "review";
type PlanDraftPhase = { title: string; tasks: Array<{ title: string; doneWhen: string; mode: PlanActionMode }> };

function planMode(value: unknown): PlanActionMode {
  return value === "practice" || value === "review" ? value : "learn";
}

function planModeLabel(mode: PlanActionMode): string {
  if (mode === "practice") return "练习";
  if (mode === "review") return "错题回访";
  return "学习";
}

function draftDetailData(value: Loadable<StudyArtifactDetail> | undefined): StudyArtifactDetail | null {
  if (value?.status === "ready") return value.data;
  if (value?.status === "loading" || value?.status === "error") return value.previous ?? null;
  return null;
}

function planDraftPhases(detail: StudyArtifactDetail | null): PlanDraftPhase[] {
  const payload = detail?.envelope.payload;
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) return [];
  const phases = (payload as Record<string, unknown>).phases;
  if (!Array.isArray(phases)) return [];
  return phases.slice(0, 30).flatMap((phase) => {
    if (!phase || typeof phase !== "object" || Array.isArray(phase)) return [];
    const row = phase as Record<string, unknown>;
    const title = typeof row.title === "string" ? row.title.trim() : "";
    if (!title || !Array.isArray(row.tasks)) return [];
    const tasks = row.tasks.slice(0, 50).flatMap((task) => {
      if (!task || typeof task !== "object" || Array.isArray(task)) return [];
      const item = task as Record<string, unknown>;
      const taskTitle = typeof item.title === "string" ? item.title.trim() : "";
      if (!taskTitle) return [];
      return [{
        title: taskTitle,
        doneWhen: typeof item.done_when === "string" ? item.done_when.trim() : "",
        mode: planMode(item.mode),
      }];
    });
    return tasks.length ? [{ title, tasks }] : [];
  });
}

function outlineNodeIds(nodes: StudyOutlineNode[], result = new Set<string>()): Set<string> {
  nodes.forEach((node) => {
    result.add(node.id);
    outlineNodeIds(node.children, result);
  });
  return result;
}

function OutlineBranch({
  nodes,
  actions,
  renderAction,
}: {
  nodes: StudyOutlineNode[];
  actions: StudyPlanItem[];
  renderAction: (item: StudyPlanItem) => ReactNode;
}) {
  return (
    <ol className="kq-study-plan-items kq-study-outline-list">
      {nodes.map((node) => {
        const nodeActions = actions.filter((item) => item.outlineNodeId === node.id);
        return (
        <li key={node.id}>
          <div className="kq-study-plan-item-copy">
            <h3>{node.title}</h3>
            {node.page || (node.level === 3 && node.sourcePath && node.sourcePath !== node.title) ? (
              <p>{[
                node.page ? `第 ${node.page} 页` : "",
                node.level === 3 && node.sourcePath !== node.title ? node.sourcePath : "",
              ].filter(Boolean).join(" · ")}</p>
            ) : null}
          </div>
          {nodeActions.length ? (
            <section className="kq-study-outline-actions" aria-label={`${node.title}的行动`}>
              <p>本节行动</p>
              <ol className="kq-study-plan-items">{nodeActions.map(renderAction)}</ol>
            </section>
          ) : null}
          {node.children.length ? <OutlineBranch nodes={node.children} actions={actions} renderAction={renderAction} /> : null}
        </li>
        );
      })}
    </ol>
  );
}

export function PlanPage({ spaceId }: { spaceId: string }) {
  const { t } = useI18n();
  const repository = useStudyRepository();
  const drafts = useStudyDrafts();
  const navigate = useNavigate();
  const pageRegion = useRef<HTMLElement>(null);
  const requests = useRef(new RequestCoordinator());
  const mutations = useRef(new RequestCoordinator());
  const [snapshot, setSnapshot] = useState<Loadable<StudyPlanSnapshot>>({ status: "idle" });
  const [pendingItem, setPendingItem] = useState("");
  const [mutationError, setMutationError] = useState("");
  const [pendingStart, setPendingStart] = useState("");
  const [pendingDraft, setPendingDraft] = useState<"confirm" | "reject" | "">("");
  const [draftError, setDraftError] = useState("");

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
  const draftItems = drafts.snapshot.status === "ready"
    ? drafts.snapshot.data.items
    : drafts.snapshot.status === "loading" || drafts.snapshot.status === "error"
      ? drafts.snapshot.previous?.items ?? []
      : [];
  const planDraft = [...draftItems]
    .filter((item) => item.kind === "learning_plan")
    .sort((a, b) => `${b.updated_at ?? ""}:${b.artifact_id}`.localeCompare(`${a.updated_at ?? ""}:${a.artifact_id}`))[0] ?? null;
  const planDraftDetail = planDraft ? draftDetailData(drafts.details[planDraft.artifact_id]) : null;
  const draftPhases = planDraftPhases(planDraftDetail);
  const currentItem = items.find((item) => item.status === "open") ?? null;
  const phases = [...new Set(items.map((item) => item.phaseTitle || data?.plan?.title || "当前范围"))];
  const boundOutlineIds = outlineNodeIds(data?.outline ?? []);
  const unboundItems = items.filter((item) => !item.outlineNodeId || !boundOutlineIds.has(item.outlineNodeId));
  const unboundPhases = [...new Set(unboundItems.map((item) => item.phaseTitle || data?.plan?.title || "当前范围"))];

  useEffect(() => {
    if (planDraft) drafts.openDetail(planDraft.artifact_id);
  }, [drafts, planDraft]);

  const confirmPlanDraft = () => {
    if (!planDraft || !planDraftDetail || pendingDraft) return;
    const request = mutations.current.begin();
    setPendingDraft("confirm");
    setDraftError("");
    void (async () => {
      let reviewStatus = planDraftDetail.review.status;
      if (planDraftDetail.review.mode === "semantic" && reviewStatus !== "passed") {
        reviewStatus = await repository.runSemanticReview(spaceId, planDraft.artifact_id, request.signal);
      }
      if (reviewStatus !== "passed") throw new Error("plan review did not pass");
      await repository.setArtifactStatus(spaceId, planDraft.artifact_id, "active", request.signal);
      if (!mutations.current.isCurrent(request.generation)) return;
      setPendingDraft("");
      window.dispatchEvent(new Event(STUDY_LEARNING_EVENT));
      load();
    })().catch(() => {
      if (!mutations.current.isCurrent(request.generation)) return;
      setPendingDraft("");
      setDraftError("这份计划还没有通过内容检查，已继续保留在草稿中。");
    });
  };

  const rejectPlanDraft = () => {
    if (!planDraft || pendingDraft) return;
    const request = mutations.current.begin();
    setPendingDraft("reject");
    setDraftError("");
    void repository.setArtifactStatus(spaceId, planDraft.artifact_id, "rejected", request.signal).then(
      () => {
        if (!mutations.current.isCurrent(request.generation)) return;
        setPendingDraft("");
        window.dispatchEvent(new Event(STUDY_LEARNING_EVENT));
      },
      () => {
        if (!mutations.current.isCurrent(request.generation)) return;
        setPendingDraft("");
        setDraftError("暂时不能处理这份计划，草稿仍然保留。");
      },
    );
  };

  const startItem = (item: StudyPlanItem) => {
    if (pendingStart) return;
    const request = mutations.current.begin();
    setPendingStart(item.item_id);
    setMutationError("");
    void repository.loadLearnHome(spaceId, request.signal).then(
      (home) => {
        if (!mutations.current.isCurrent(request.generation)) return;
        const resolved = resolveKnowledgeCore(spaceId, home.knowledgePoints);
        setPendingStart("");
        if (!resolved) {
          setMutationError(item.item_id);
          return;
        }
        const targetPage = planMode(item.mode) === "learn" ? "learn" : "practice";
        selectKnowledgeCore(spaceId, resolved.point, targetPage, {
          planItemId: item.item_id,
          outlineLabel: item.phaseTitle,
          outlineNodeId: item.outlineNodeId,
        });
        navigate(studyPath(spaceId, targetPage));
      },
      () => {
        if (!mutations.current.isCurrent(request.generation)) return;
        setPendingStart("");
        setMutationError(item.item_id);
      },
    );
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

  const renderPlanItem = (item: StudyPlanItem) => (
    <li
      id={`study-plan-item-${item.item_id}`}
      key={item.item_id}
      tabIndex={-1}
      className={`is-${item.status}`}
    >
      <div className="kq-study-plan-item-copy">
        <span>{item.phaseTitle}</span>
        <h3>{item.title}</h3>
        <span className="kq-study-plan-mode">{planModeLabel(planMode(item.mode))}</span>
        {item.done_when ? <p>{t("study.planDoneWhen", { value: item.done_when })}</p> : null}
        {item.note ? <p>{item.note}</p> : null}
      </div>
      {item.status === "open" ? (
        <div className="kq-study-inline-actions">
          <button type="button" disabled={Boolean(pendingStart)} onClick={() => startItem(item)}>
            {pendingStart === item.item_id ? "正在打开…" : "开始"}
          </button>
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
  );

  return (
    <section
      ref={pageRegion}
      className="kq-study-content-page"
      aria-label={t("study.pagePlan")}
      tabIndex={-1}
    >
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

      {data?.outline?.length ? (
        <section className="kq-study-plan-phase" aria-labelledby="study-source-outline">
          <p className="kq-study-placeholder-kicker">课程目录</p>
          <h2 id="study-source-outline">{data.outlineSourceTitle || "课程材料"}</h2>
          <p className="kq-study-plan-source-note">来自文件自身的目录结构；计划页最多展示三级。</p>
          <OutlineBranch nodes={data.outline} actions={items} renderAction={renderPlanItem} />
        </section>
      ) : null}

      {planDraft ? (
        <article className="kq-study-plan-phase" aria-labelledby="study-plan-draft-title">
          <h2 id="study-plan-draft-title">小娜推荐学习计划</h2>
          {!planDraftDetail ? <p role="status">正在打开计划草稿…</p> : null}
          {draftPhases.map((phase) => (
            <section key={phase.title}>
              <h3>{phase.title}</h3>
              <ol className="kq-study-plan-items">
                {phase.tasks.map((task) => (
                  <li key={`${phase.title}:${task.title}`}>
                    <div className="kq-study-plan-item-copy">
                      <h3>{task.title}</h3>
                      <span>{planModeLabel(task.mode)}</span>
                      {task.doneWhen ? <p>做到：{task.doneWhen}</p> : null}
                    </div>
                  </li>
                ))}
              </ol>
            </section>
          ))}
          {draftError ? <p className="kq-study-page-error" role="alert">{draftError}</p> : null}
          <div className="kq-study-inline-actions">
            <button type="button" disabled={!planDraftDetail || Boolean(pendingDraft)} onClick={confirmPlanDraft}>
              {pendingDraft === "confirm" ? "正在检查…" : planDraftDetail?.review.status === "passed" ? "采用这个计划" : "检查并采用"}
            </button>
            <button type="button" disabled={Boolean(pendingDraft)} onClick={rejectPlanDraft}>
              {pendingDraft === "reject" ? "正在处理…" : "不采用"}
            </button>
          </div>
        </article>
      ) : null}

      {data?.plan ? (
        <>
          <article className="kq-study-plan-summary">
            <div>
              <p>当前行动范围</p>
              <h2>{currentItem?.phaseTitle || phases.at(-1) || data.plan.title}</h2>
              <span className="kq-study-muted">{data.plan.title}</span>
            </div>
            {!currentItem ? <span className="kq-study-muted">{t("study.planAllDone")}</span> : null}
          </article>

          <p className="kq-study-plan-source-note">材料来源目录尚未整理完成时，只显示已确认的行动阶段；不会把行动名称伪装成教材目录。</p>

          {unboundPhases.map((phase) => (
            <section key={phase} className="kq-study-plan-phase" aria-labelledby={`study-phase-${encodeURIComponent(phase)}`}>
              <h2 id={`study-phase-${encodeURIComponent(phase)}`}>{phase}</h2>
              <ol className="kq-study-plan-items">
              {unboundItems.filter((item) => (item.phaseTitle || data.plan?.title || "当前范围") === phase).map(renderPlanItem)}
              </ol>
            </section>
          ))}
        </>
      ) : null}

      {data && !data.plan && !planDraft ? (
        <div className="kq-study-page-empty">
          <h2>{t("study.planEmptyTitle")}</h2>
          <p>{t("study.planEmptyBody")}</p>
          <button type="button" className="kq-study-primary-link" onClick={() => document.getElementById("kd-cup-chat")?.click()}>{t("study.askNana")}</button>
        </div>
      ) : null}
    </section>
  );
}
