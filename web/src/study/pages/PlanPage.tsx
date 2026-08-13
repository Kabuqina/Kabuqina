// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import type { StudyArtifactSummary, StudyPlanItem } from "../../chat/study/study-api";
import { useI18n } from "../../lib/i18n";
import { RequestCoordinator, type Loadable } from "../loadable";
import { deriveStudyRequestState } from "../pageState";
import { STUDY_LEARNING_EVENT } from "../learningEvent";
import type { StudyOutlineNode, StudyPlanSnapshot } from "../repository";
import { useStudyRepository } from "../repositoryContext";
import { useStudyDrafts } from "../DraftContext";
import { readStudyLocation, selectOutlineScope, selectPlanItem } from "../studyLocation";
import { studyPath } from "../routeModel";
import { requestStudyNana } from "../studyNanaRequest";
import { requestStudyDraft } from "../studyDraftRequest";
import { requestStudyMaterial } from "../studyMaterialRequest";

type PlanActionMode = "learn" | "practice" | "review";
type PlanDraftTask = {
  title: string;
  doneWhen: string;
  mode: PlanActionMode;
};
type PlanDraftPhase = { title: string; tasks: PlanDraftTask[] };
type PlanSource = Pick<StudyArtifactSummary, "artifact_id" | "title">;
function planMode(value: unknown): PlanActionMode {
  return value === "practice" || value === "review" ? value : "learn";
}

function planModeLabel(mode: PlanActionMode): string {
  if (mode === "practice") return "练习";
  if (mode === "review") return "错题回访";
  return "学习";
}

function planDraftPhases(detail: ReturnType<typeof draftDetailData>): PlanDraftPhase[] {
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

function draftDetailData(value: ReturnType<typeof useStudyDrafts>["details"][string] | undefined) {
  if (value?.status === "ready") return value.data;
  if (value?.status === "loading" || value?.status === "error") return value.previous ?? null;
  return null;
}

function outlineNodeIds(nodes: StudyOutlineNode[], result = new Set<string>()): Set<string> {
  nodes.forEach((node) => {
    result.add(node.id);
    outlineNodeIds(node.children, result);
  });
  return result;
}

function outlineScopeIds(nodes: StudyOutlineNode[], targetId: string): Set<string> {
  const addBranch = (node: StudyOutlineNode, result: Set<string>) => {
    result.add(node.id);
    node.children.forEach((child) => addBranch(child, result));
  };
  for (const node of nodes) {
    if (node.id === targetId) {
      const result = new Set<string>();
      addBranch(node, result);
      return result;
    }
    const nested = outlineScopeIds(node.children, targetId);
    if (nested.size) return nested;
  }
  return new Set([targetId]);
}

function planItemStateLabel(item: StudyPlanItem): string {
  if (item.status === "completed") return "已完成";
  if (item.status === "skipped") return "已跳过";
  return "待学习";
}

function branchActions(node: StudyOutlineNode, actions: StudyPlanItem[]): StudyPlanItem[] {
  const scope = outlineScopeIds([node], node.id);
  return actions.filter((item) => Boolean(item.outlineNodeId && scope.has(item.outlineNodeId)));
}

function outlineStateLabel(
  node: StudyOutlineNode,
  actions: StudyPlanItem[],
  currentItemId?: string,
  nextItemId?: string,
): string {
  const scoped = branchActions(node, actions);
  if (currentItemId && scoped.some((item) => item.item_id === currentItemId)) return "进行中";
  if (nextItemId && scoped.some((item) => item.item_id === nextItemId)) return "下一项";
  if (scoped.length && scoped.every((item) => item.status === "completed")) return "已完成";
  if (scoped.some((item) => item.status === "open")) return "待学习";
  if (scoped.length) return "已调整";
  return "";
}

function OutlineBranch({
  nodes,
  actions,
  renderAction,
  currentItemId,
  nextItemId,
  onOpenNode,
  onStartNode,
}: {
  nodes: StudyOutlineNode[];
  actions: StudyPlanItem[];
  renderAction: (item: StudyPlanItem) => ReactNode;
  currentItemId?: string;
  nextItemId?: string;
  onOpenNode: (node: StudyOutlineNode) => void;
  onStartNode: (node: StudyOutlineNode) => void;
}) {
  return (
    <ol className="kq-study-outline-tree">
      {nodes.map((node) => {
        const nodeActions = actions.filter((item) => item.outlineNodeId === node.id);
        const stateLabel = outlineStateLabel(node, actions, currentItemId, nextItemId);
        return (
        <li
          key={node.id}
          className={`kq-study-outline-node is-level-${node.level}`}
          data-state={stateLabel || undefined}
        >
          <div className="kq-study-outline-row">
            <span className="kq-study-outline-marker" aria-hidden="true" />
            <div>
              <h3>
                {node.sourceArtifactId ? (
                  <button type="button" onClick={() => onOpenNode(node)}>{node.title}</button>
                ) : node.title}
              </h3>
              {node.page || (node.level === 3 && node.sourcePath && node.sourcePath !== node.title) ? (
                <p>{[
                  node.page ? `第 ${node.page} 页` : "",
                  node.level === 3 && node.sourcePath !== node.title ? node.sourcePath : "",
                ].filter(Boolean).join(" · ")}</p>
              ) : null}
            </div>
            {stateLabel ? <span className="kq-study-outline-state">{stateLabel}</span> : null}
            <button type="button" className="kq-study-outline-start" onClick={() => onStartNode(node)}>学习</button>
          </div>
          {nodeActions.length ? (
            <section className="kq-study-outline-actions" aria-label={`${node.title}的学习安排`}>
              <ol className="kq-study-plan-items">{nodeActions.map(renderAction)}</ol>
            </section>
          ) : null}
          {node.children.length ? (
            <OutlineBranch
              nodes={node.children}
              actions={actions}
              renderAction={renderAction}
              currentItemId={currentItemId}
              nextItemId={nextItemId}
              onOpenNode={onOpenNode}
              onStartNode={onStartNode}
            />
          ) : null}
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
  const location = useLocation();
  const pageRegion = useRef<HTMLElement>(null);
  const requests = useRef(new RequestCoordinator());
  const sourceRequests = useRef(new RequestCoordinator());
  const mutations = useRef(new RequestCoordinator());
  const [snapshot, setSnapshot] = useState<Loadable<StudyPlanSnapshot>>({ status: "idle" });
  const [pendingItem, setPendingItem] = useState("");
  const [mutationError, setMutationError] = useState("");
  const [pendingPlanDraftAction, setPendingPlanDraftAction] = useState<"activate" | "reject" | "">("");
  const [planDraftError, setPlanDraftError] = useState("");
  const [adoptedPlanDraftId, setAdoptedPlanDraftId] = useState("");
  const [sourceState, setSourceState] = useState<"idle" | "loading" | "empty" | "error">("idle");
  const [sourceChoices, setSourceChoices] = useState<PlanSource[]>([]);
  const [generatingSource, setGeneratingSource] = useState<PlanSource | null>(null);

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
    const activeSourceRequests = sourceRequests.current;
    const activeMutations = mutations.current;
    pageRegion.current?.focus();
    load();
    const refresh = () => load();
    window.addEventListener(STUDY_LEARNING_EVENT, refresh);
    return () => {
      window.removeEventListener(STUDY_LEARNING_EVENT, refresh);
      activeRequests.cancel();
      activeSourceRequests.cancel();
      activeMutations.cancel();
    };
  }, [load]);

  const requestState = deriveStudyRequestState(snapshot);
  const data = requestState.data;
  const itemsUnavailable = Boolean(data?.unavailable?.includes("items"));
  const knowledgeSourcesUnavailable = Boolean(data?.unavailable?.includes("knowledgeSources"));
  const items = useMemo(() => data?.items ?? [], [data?.items]);
  const draftItems = drafts.snapshot.status === "ready"
    ? drafts.snapshot.data.items
    : drafts.snapshot.status === "loading" || drafts.snapshot.status === "error"
      ? drafts.snapshot.previous?.items ?? []
      : [];
  const draftsResolved = drafts.snapshot.status === "ready"
    || ((drafts.snapshot.status === "loading" || drafts.snapshot.status === "error") && Boolean(drafts.snapshot.previous));
  const draftsUnavailable = drafts.snapshot.status === "error" && !drafts.snapshot.previous;
  const planDraft = [...draftItems]
    .filter((item) => item.kind === "learning_plan" && item.artifact_id !== adoptedPlanDraftId)
    .sort((a, b) => `${b.updated_at ?? ""}:${b.artifact_id}`.localeCompare(`${a.updated_at ?? ""}:${a.artifact_id}`))[0] ?? null;
  const planDraftDetail = planDraft ? draftDetailData(drafts.details[planDraft.artifact_id]) : null;
  const draftPhases = planDraftPhases(planDraftDetail);
  const waitingForPlanState = Boolean(data && !data.plan && (!draftsResolved || adoptedPlanDraftId));
  const visibleItems = useMemo(() => {
    if (!data?.outline?.length) return items.filter((item) => Boolean(item.outlineNodeId));
    const boundOutlineIds = outlineNodeIds(data?.outline ?? []);
    return items.filter((item) => Boolean(item.outlineNodeId && boundOutlineIds.has(item.outlineNodeId)));
  }, [data?.outline, items]);
  const currentItem = data?.location?.page !== "plan" && data?.location?.planItemId
    ? visibleItems.find((item) => item.item_id === data.location?.planItemId && item.status === "open") ?? null
    : null;
  const nextItem = visibleItems.find((item) => item.status === "open") ?? null;

  useEffect(() => {
    if (!data?.plan || !nextItem) return;
    if (data.location && data.location.page !== "plan") return;
    const local = readStudyLocation(spaceId);
    if (local && local.page !== "plan") return;
    const candidate = data.location?.planItemId
      ? visibleItems.find((item) => item.item_id === data.location?.planItemId && item.status === "open") ?? nextItem
      : nextItem;
    selectPlanItem(spaceId, {
      itemId: candidate.item_id,
      title: candidate.title,
      ...(candidate.phaseTitle ? { phaseTitle: candidate.phaseTitle } : {}),
      ...(candidate.outlineNodeId ? { outlineNodeId: candidate.outlineNodeId } : {}),
    });
  }, [data?.location, data?.plan, nextItem, spaceId, visibleItems]);

  useEffect(() => {
    if (!data || !location.hash) return;
    let targetId = "";
    try {
      targetId = decodeURIComponent(location.hash.slice(1));
    } catch {
      return;
    }
    if (!targetId.startsWith("study-plan-item-")) return;
    const target = document.getElementById(targetId);
    if (!target) return;
    target.scrollIntoView?.({ block: "center" });
    target.focus();
  }, [data, location.hash]);

  useEffect(() => {
    if (planDraft && data && !data.plan) drafts.openDetail(planDraft.artifact_id);
  }, [data, drafts, planDraft]);

  useEffect(() => {
    if (planDraft) setGeneratingSource(null);
  }, [planDraft]);

  const decidePlanDraft = (action: "activate" | "reject") => {
    if (!planDraft || pendingPlanDraftAction) return;
    setPendingPlanDraftAction(action);
    setPlanDraftError("");
    if (action === "activate") setAdoptedPlanDraftId(planDraft.artifact_id);
    const operation = action === "activate"
      ? drafts.activate(planDraft.artifact_id)
      : drafts.reject(planDraft.artifact_id);
    void operation.then((applied) => {
      if (!applied) {
        setPendingPlanDraftAction("");
        if (action === "activate") setAdoptedPlanDraftId("");
        setPlanDraftError(action === "activate" ? "暂时不能采用这份计划，草稿仍然保留。" : "暂时不能放弃这份计划，草稿仍然保留。");
        return;
      }
      setPendingPlanDraftAction("");
      load();
    });
  };

  const openOutlineNode = (node: StudyOutlineNode) => {
    const artifactId = node.sourceArtifactId || data?.outlineSourceArtifactId;
    if (!artifactId) return;
    requestStudyMaterial({
      spaceId,
      artifactId,
      ...(node.page ? { page: node.page } : {}),
    });
  };

  const startOutlineNode = (node: StudyOutlineNode) => {
    selectOutlineScope(spaceId, { title: node.title, outlineNodeId: node.id });
    navigate(studyPath(spaceId, "learn"));
  };

  const beginPlanGeneration = (source: PlanSource) => {
    setSourceChoices([]);
    setSourceState("idle");
    setGeneratingSource(source);
    requestStudyNana({
      spaceId,
      page: "plan",
      focusId: `new-learning-plan:${source.artifact_id}`,
      focusLabel: `用《${source.title}》生成学习计划`,
      selectedSource: { id: source.artifact_id, title: source.title },
      autoSend: true,
      initialPrompt: `请只基于我选择的知识源《${source.title}》和已经确认的学习设定，生成一份待采用的学习计划草稿。计划必须保留真实来源，不要自动采用，也不要把推断结构说成原文件目录。`,
    });
  };

  const createPlanDraft = () => {
    if (sourceState === "loading") return;
    const request = sourceRequests.current.begin();
    setSourceState("loading");
    setSourceChoices([]);
    void repository.loadLearnHome(spaceId, request.signal).then(
      (home) => {
        if (!sourceRequests.current.isCurrent(request.generation)) return;
        if (home.unavailableKinds?.includes("resource_pack")) {
          setSourceState("error");
          return;
        }
        const sources = home.artifacts
          .filter((artifact) => artifact.kind === "resource_pack" && artifact.status === "active")
          .filter((artifact, index, all) => all.findIndex((item) => item.artifact_id === artifact.artifact_id) === index)
          .map((artifact) => ({ artifact_id: artifact.artifact_id, title: artifact.title }));
        if (!sources.length) {
          setSourceState("empty");
          return;
        }
        if (sources.length === 1) {
          beginPlanGeneration(sources[0]);
          return;
        }
        setSourceState("idle");
        setSourceChoices(sources);
      },
      () => {
        if (sourceRequests.current.isCurrent(request.generation)) setSourceState("error");
      },
    );
  };

  const addKnowledgeSource = () => {
    document.querySelector<HTMLButtonElement>('button[aria-label="添加知识源"]')?.click();
  };

  const startItem = (item: StudyPlanItem) => {
    if (!item.outlineNodeId) return;
    selectPlanItem(spaceId, {
      itemId: item.item_id,
      title: item.title,
      ...(item.phaseTitle ? { phaseTitle: item.phaseTitle } : {}),
      outlineNodeId: item.outlineNodeId,
    });
    navigate(studyPath(spaceId, "learn"));
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

  const renderPlanItem = (item: StudyPlanItem) => {
    const isCurrent = currentItem?.item_id === item.item_id;
    const isNext = !currentItem && nextItem?.item_id === item.item_id;
    const actionLabel = isCurrent ? "继续学习" : "开始学习";
    const copy = (
      <>
        <span className="kq-study-plan-mode">{planModeLabel(planMode(item.mode))}</span>
        <span className="kq-study-plan-item-title" role="heading" aria-level={3}>{item.title}</span>
        <small>
          {isCurrent ? "正在进行" : isNext ? "下一项" : planItemStateLabel(item)}
        </small>
      </>
    );
    return (
      <li
        id={`study-plan-item-${item.item_id}`}
        key={item.item_id}
        tabIndex={-1}
        className={`is-${item.status}${isCurrent ? " is-current" : ""}${isNext ? " is-next" : ""}`}
      >
        <span className="kq-study-plan-item-marker" aria-hidden="true" />
        <div className="kq-study-plan-item-select">{copy}</div>
        <div className="kq-study-plan-item-secondary">
          {item.status === "open" ? (
            <>
              <button
                type="button"
                className="kq-study-plan-item-start"
                onClick={() => startItem(item)}
              >
                {actionLabel}
              </button>
              <details>
                <summary>更多</summary>
                <div className="kq-study-plan-item-menu">
                  {item.done_when ? <p>{t("study.planDoneWhen", { value: item.done_when })}</p> : null}
                  {item.note ? <p>{item.note}</p> : null}
                  <button type="button" disabled={pendingItem === item.item_id} onClick={() => updateItem(item.item_id, "complete")}>{t("study.planComplete")}</button>
                  <button type="button" disabled={pendingItem === item.item_id} onClick={() => updateItem(item.item_id, "skip")}>{t("study.planSkip")}</button>
                </div>
              </details>
            </>
          ) : <strong>{item.status === "completed" ? t("study.planCompleted") : t("study.planSkipped")}</strong>}
        </div>
        {mutationError === item.item_id ? <p className="kq-study-page-error" role="alert">{t("study.planMutationFailed")}</p> : null}
      </li>
    );
  };

  return (
    <section
      ref={pageRegion}
      className="kq-study-content-page"
      aria-label={t("study.pagePlan")}
      tabIndex={-1}
    >
      {requestState.phase === "loading" && !data ? <p role="status">{t("study.pageLoading")}</p> : null}
      {requestState.phase === "error" && !data ? (
        <div className="kq-study-page-alert" role="alert">
          <p>{t("study.pageLoadFailed")}</p>
          <button type="button" onClick={load}>{t("study.retry")}</button>
          <Link to="/chat">{t("study.backToChat")}</Link>
        </div>
      ) : null}
      {requestState.refreshErrorWithData ? (
        <div className="kq-study-page-alert" role="alert">
          <span>{t("study.pageStale")}</span>
          <button type="button" onClick={load}>{t("study.retry")}</button>
        </div>
      ) : null}
      {data?.plan && itemsUnavailable ? (
        <div className="kq-study-page-alert" role="alert">
          <span>学习计划已经打开，但行动进度暂时无法读取。</span>
          <button type="button" onClick={load}>{t("study.retry")}</button>
        </div>
      ) : null}
      {!data?.plan && knowledgeSourcesUnavailable ? (
        <div className="kq-study-page-alert" role="alert">
          <span>暂时无法确认知识源状态，已有计划和草稿没有改变。</span>
          <button type="button" onClick={load}>{t("study.retry")}</button>
        </div>
      ) : null}
      {waitingForPlanState ? <p role="status">{adoptedPlanDraftId ? "正在采用学习计划…" : "正在打开学习计划…"}</p> : null}
      {data && !data.plan && draftsUnavailable ? (
        <div className="kq-study-page-alert" role="alert">
          <span>暂时无法确认是否有计划草稿。</span>
          <button type="button" onClick={drafts.refresh}>{t("study.retry")}</button>
        </div>
      ) : null}
      {planDraft && data?.plan && draftsResolved ? (
        <article className="kq-study-page-alert" aria-labelledby="study-replacement-plan-title">
          <div>
            <strong id="study-replacement-plan-title">有一份新的学习计划草稿</strong>
            <p>{planDraft.title}</p>
          </div>
          <button
            type="button"
            onClick={() => requestStudyDraft({ spaceId, artifactId: planDraft.artifact_id })}
          >
            查看并采用
          </button>
        </article>
      ) : null}

      {planDraft && data && !data.plan && draftsResolved && !adoptedPlanDraftId ? (
        <article className="kq-study-plan-phase kq-study-plan-draft-preview" aria-labelledby="study-plan-draft-title">
          <header>
            <p className="kq-study-placeholder-kicker">待采用</p>
            <h2 id="study-plan-draft-title">{planDraft.title || "学习计划草稿"}</h2>
            <p>这份计划尚未生效。确认后才会成为正式计划。</p>
          </header>
          {!planDraftDetail ? <p role="status">正在打开计划草稿…</p> : null}
          {draftPhases.map((phase) => (
            <section key={phase.title}>
              <h3>{phase.title}</h3>
              <ol className="kq-study-plan-items">
                {phase.tasks.map((task, taskIndex) => (
                  <li key={`${phase.title}:${task.title}:${taskIndex}`}>
                    <div className="kq-study-plan-item-copy">
                      <span>{planModeLabel(task.mode)}</span>
                      <h3>{task.title}</h3>
                      {task.doneWhen ? <p>做到：{task.doneWhen}</p> : null}
                    </div>
                  </li>
                ))}
              </ol>
            </section>
          ))}
          {planDraftError ? <p className="kq-study-page-error" role="alert">{planDraftError}</p> : null}
          <div className="kq-study-inline-actions">
            <button type="button" disabled={!planDraftDetail || Boolean(pendingPlanDraftAction)} onClick={() => decidePlanDraft("activate")}>
              {pendingPlanDraftAction === "activate" ? "正在采用…" : "采用计划"}
            </button>
            <button type="button" disabled={Boolean(pendingPlanDraftAction)} onClick={() => decidePlanDraft("reject")}>
              {pendingPlanDraftAction === "reject" ? "正在处理…" : "不采用"}
            </button>
          </div>
        </article>
      ) : null}

      {data?.plan && data.outline?.length ? (
        <section className="kq-study-plan-outline" aria-labelledby="study-source-outline">
          <header className="kq-study-plan-outline-heading">
            <div>
              <p className="kq-study-placeholder-kicker">学习目录</p>
              <h2 id="study-source-outline">计划安排</h2>
            </div>
            {data.outlineSourceTitle ? <span>知识源 · {data.outlineSourceTitle}</span> : null}
          </header>
          <OutlineBranch
            nodes={data.outline}
            actions={visibleItems}
            renderAction={renderPlanItem}
            currentItemId={currentItem?.item_id}
            nextItemId={!currentItem ? nextItem?.item_id : undefined}
            onOpenNode={openOutlineNode}
            onStartNode={startOutlineNode}
          />
        </section>
      ) : null}

      {data?.plan && !data.outline?.length && visibleItems.length ? (
        <section className="kq-study-plan-outline" aria-labelledby="study-plan-list">
          <header className="kq-study-plan-outline-heading">
            <div>
              <p className="kq-study-placeholder-kicker">学习目录</p>
              <h2 id="study-plan-list">计划安排</h2>
            </div>
          </header>
          <ol className="kq-study-plan-items">{visibleItems.map(renderPlanItem)}</ol>
        </section>
      ) : null}

      {data?.plan && !data.outline?.length && !visibleItems.length && !itemsUnavailable ? (
        <div className="kq-study-page-empty">
          <h2>这份计划还没有可用目录</h2>
          <p>知识源目录准备好后，就可以从这里进入学习。</p>
          <button type="button" className="kq-study-primary-link" onClick={load}>{t("study.retry")}</button>
        </div>
      ) : null}

      {data?.plan && visibleItems.length > 0 && !itemsUnavailable && !nextItem ? <p className="kq-study-plan-source-note">{t("study.planAllDone")}</p> : null}

      {data && !data.plan && draftsResolved && !planDraft && !adoptedPlanDraftId ? (
        <div className="kq-study-page-empty">
          {sourceChoices.length > 1 ? (
            <>
              <h2>选择生成计划的知识源</h2>
              <p>这本本子里有 {sourceChoices.length} 份文件。请选择一份作为这次计划的依据。</p>
              <ul className="kq-study-plan-source-choices">
                {sourceChoices.map((source) => (
                  <li key={source.artifact_id}>
                    <button type="button" onClick={() => beginPlanGeneration(source)}>{source.title}</button>
                  </li>
                ))}
              </ul>
              <button type="button" className="kq-study-secondary-link" onClick={() => setSourceChoices([])}>返回</button>
            </>
          ) : generatingSource ? (
            <>
              <h2>正在拟定学习计划</h2>
              <p>正在根据《{generatingSource.title}》生成待采用的计划草稿。</p>
            </>
          ) : sourceState === "empty" ? (
            <>
              <h2>知识源里还没有文件</h2>
              <p>先上传教材、讲义或习题集，再用它生成学习计划。</p>
              <button type="button" className="kq-study-primary-link" onClick={addKnowledgeSource}>上传资料</button>
            </>
          ) : data.hasKnowledgeSources === false ? (
            <>
              <h2>先放入知识源</h2>
              <p>计划需要依据真实材料安排；添加教材、讲义或习题集后再开始。</p>
              <div className="kq-study-inline-actions">
                <button type="button" className="kq-study-primary-link" onClick={addKnowledgeSource}>添加知识源</button>
                <button type="button" className="kq-study-secondary-link" onClick={() => document.getElementById("kd-cup-chat")?.click()}>问小娜</button>
              </div>
            </>
          ) : (
            <>
              <h2>还没有学习计划</h2>
              <p>知识源已经准备好了，可以据此安排接下来的学习与练习。</p>
              <button type="button" className="kq-study-primary-link" disabled={sourceState === "loading"} onClick={createPlanDraft}>
                {sourceState === "loading" ? "正在读取知识源…" : "+ 学习计划"}
              </button>
              {sourceState === "error" ? <p className="kq-study-page-error" role="alert">暂时没有读到可用于生成计划的知识源文件。</p> : null}
            </>
          )}
        </div>
      ) : null}
    </section>
  );
}
