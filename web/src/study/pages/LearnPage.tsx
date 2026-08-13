// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ArrowLeft, ArrowRight, BookOpen, Bookmark, Coffee, Eye, EyeOff, Lightbulb } from "lucide-react";
import { Link } from "react-router-dom";
import type { KnowledgeCoreCompilationRun, StudyKnowledgePoint } from "../../chat/study/study-api";
import { useI18n } from "../../lib/i18n";
import { RequestCoordinator, type Loadable } from "../loadable";
import { deriveStudyRequestState } from "../pageState";
import type { StudyLearnHome } from "../repository";
import { useStudyRepository } from "../repositoryContext";
import { studyPath } from "../routeModel";
import { STUDY_LEARNING_EVENT } from "../learningEvent";
import { requestStudyDraft } from "../studyDraftRequest";
import {
  readStudyLocation,
  resolveKnowledgeCore,
  selectKnowledgeCore,
  switchStudyMode,
} from "../studyLocation";

const DRAFT_PREFIX = "kabuqina.study.learn-draft.v1";

type LearnDraft = { version: 1; text: string; compared: boolean; updatedAt: string };

function retained<T>(state: Loadable<T>): T | undefined {
  return deriveStudyRequestState(state).data;
}

function scopedKnowledgePoints(home: StudyLearnHome, requestedScopeId = ""): StudyKnowledgePoint[] {
  const scopeId = requestedScopeId || home.location?.planOutlineNodeId || "";
  if (!scopeId || !home.learningMap) return home.knowledgePoints;
  const nodes = new Map(home.learningMap.outlineNodes.map((node) => [node.id, node]));
  const withinScope = (outlineNodeId: string | null) => {
    let cursor = outlineNodeId;
    while (cursor) {
      if (cursor === scopeId) return true;
      cursor = nodes.get(cursor)?.parentId ?? null;
    }
    return false;
  };
  const allowed = new Set(
    home.learningMap.knowledgeCores
      .filter((core) => withinScope(core.outlineNodeId))
      .map((core) => core.id),
  );
  return home.knowledgePoints.filter((point) => allowed.has(point.item_id));
}

function draftKey(spaceId: string, coreId: string): string {
  return `${DRAFT_PREFIX}:${spaceId}:${coreId}`;
}

export function readStudyLearnDraft(spaceId: string, coreId: string): LearnDraft {
  const empty: LearnDraft = { version: 1, text: "", compared: false, updatedAt: new Date(0).toISOString() };
  try {
    const raw = window.localStorage.getItem(draftKey(spaceId, coreId));
    if (!raw) return empty;
    const value = JSON.parse(raw) as Partial<LearnDraft>;
    if (value.version !== 1 || typeof value.text !== "string" || typeof value.compared !== "boolean") return empty;
    return { version: 1, text: value.text.slice(0, 12000), compared: value.compared, updatedAt: String(value.updatedAt || empty.updatedAt) };
  } catch {
    return empty;
  }
}

function writeDraft(spaceId: string, coreId: string, draft: LearnDraft): boolean {
  try {
    window.localStorage.setItem(draftKey(spaceId, coreId), JSON.stringify(draft));
    return true;
  } catch {
    return false;
  }
}

export function LearnPage({ spaceId }: { spaceId: string }) {
  const { t } = useI18n();
  const repository = useStudyRepository();
  const pageRegion = useRef<HTMLElement>(null);
  const requests = useRef(new RequestCoordinator());
  const compilationRequests = useRef(new RequestCoordinator());
  const compilationMutations = useRef(new RequestCoordinator());
  const compilationScope = useRef("");
  const attemptedCompilations = useRef(new Set<string>());
  const [snapshot, setSnapshot] = useState<Loadable<StudyLearnHome>>({ status: "idle" });
  const [compilationSnapshot, setCompilationSnapshot] = useState<Loadable<KnowledgeCoreCompilationRun[]>>({ status: "idle" });
  const [compilationMutation, setCompilationMutation] = useState<"idle" | "starting" | "retrying" | "error">("idle");
  const [coreIndex, setCoreIndex] = useState<number | null>(null);
  const [draft, setDraft] = useState<LearnDraft | null>(null);
  const [saveFailed, setSaveFailed] = useState(false);
  const data = retained(snapshot);
  const localLocation = readStudyLocation(spaceId);
  const outlineNodeId = localLocation?.outlineNodeId
    || data?.location?.planOutlineNodeId
    || data?.location?.outlineNodeId
    || "";
  const planItemId = localLocation?.planItemId || data?.location?.planItemId || "";
  const points = useMemo(() => data ? scopedKnowledgePoints(data, outlineNodeId) : [], [data, outlineNodeId]);
  const point = coreIndex === null ? null : points[coreIndex] ?? null;

  const load = useCallback(() => {
    const request = requests.current.begin();
    setSnapshot((current) => ({
      status: "loading",
      ...(retained(current) ? { previous: retained(current) } : {}),
    }));
    void repository.loadLearnHome(spaceId, request.signal).then(
      (next) => {
        if (!requests.current.isCurrent(request.generation)) return;
        setSnapshot({ status: "ready", data: next });
        const requestedScopeId = readStudyLocation(spaceId)?.outlineNodeId
          || next.location?.planOutlineNodeId
          || next.location?.outlineNodeId
          || "";
        const nextPoints = scopedKnowledgePoints(next, requestedScopeId);
        const resolved = resolveKnowledgeCore(spaceId, nextPoints);
        if (resolved) {
          setCoreIndex(resolved.index);
          if (!resolved.recovered) selectKnowledgeCore(spaceId, resolved.point, "learn");
        } else {
          setCoreIndex(null);
        }
      },
      (error) => {
        if (!requests.current.isCurrent(request.generation)) return;
        setSnapshot((current) => ({
          status: "error",
          error,
          ...(retained(current) ? { previous: retained(current) } : {}),
        }));
      },
    );
  }, [repository, spaceId]);

  useEffect(() => {
    const coordinator = requests.current;
    const compilationCoordinator = compilationRequests.current;
    const compilationMutationCoordinator = compilationMutations.current;
    pageRegion.current?.focus();
    load();
    const refresh = () => load();
    window.addEventListener(STUDY_LEARNING_EVENT, refresh);
    return () => {
      coordinator.cancel();
      compilationCoordinator.cancel();
      compilationMutationCoordinator.cancel();
      window.removeEventListener(STUDY_LEARNING_EVENT, refresh);
    };
  }, [load]);
  const loadCompilations = useCallback(() => {
    if (!outlineNodeId || !repository.listKnowledgeCoreCompilations) {
      compilationScope.current = "";
      setCompilationSnapshot({ status: "ready", data: [] });
      return;
    }
    const request = compilationRequests.current.begin();
    const sameScope = compilationScope.current === outlineNodeId;
    compilationScope.current = outlineNodeId;
    setCompilationSnapshot((current) => ({
      status: "loading",
      ...(sameScope && retained(current) ? { previous: retained(current) } : {}),
    }));
    void repository.listKnowledgeCoreCompilations(spaceId, outlineNodeId, request.signal).then(
      (runs) => {
        if (compilationRequests.current.isCurrent(request.generation)) setCompilationSnapshot({ status: "ready", data: runs });
      },
      (error) => {
        if (!compilationRequests.current.isCurrent(request.generation)) return;
        setCompilationSnapshot((current) => ({
          status: "error",
          error,
          ...(retained(current) ? { previous: retained(current) } : {}),
        }));
      },
    );
  }, [outlineNodeId, repository, spaceId]);

  useEffect(() => {
    if (point) return;
    loadCompilations();
  }, [loadCompilations, point]);

  const compilationState = deriveStudyRequestState(compilationSnapshot);
  const latestCompilation = useMemo(() => [...(compilationState.data ?? [])]
    .sort((a, b) => `${b.updatedAt}:${b.runId}`.localeCompare(`${a.updatedAt}:${a.runId}`))[0], [compilationState.data]);
  const compilationRunning = latestCompilation
    && ["queued", "reading", "generating", "validating"].includes(latestCompilation.status);

  const mergeCompilation = useCallback((run: KnowledgeCoreCompilationRun) => {
    setCompilationSnapshot((current) => {
      const runs = deriveStudyRequestState(current).data ?? [];
      return {
        status: "ready",
        data: [run, ...runs.filter((candidate) => candidate.runId !== run.runId)],
      };
    });
  }, []);

  const createCompilation = useCallback((kind: "automatic" | "manual") => {
    if (!outlineNodeId || !data?.learningMap || !repository.createKnowledgeCoreCompilation) return;
    const request = compilationMutations.current.begin();
    setCompilationMutation("starting");
    const scopeKey = planItemId || outlineNodeId;
    void repository.createKnowledgeCoreCompilation({
      spaceId,
      outlineNodeId,
      ...(planItemId ? { planItemId } : {}),
      trigger: "start_learning",
      expectedMapRevision: data.learningMap.revision,
      idempotencyKey: `${kind}:learn:${scopeKey}:${data.learningMap.revision}`.slice(0, 200),
      priority: 10,
    }, request.signal).then(
      (run) => {
        if (!compilationMutations.current.isCurrent(request.generation)) return;
        setCompilationMutation("idle");
        mergeCompilation(run);
      },
      () => {
        if (!compilationMutations.current.isCurrent(request.generation)) return;
        setCompilationMutation("error");
      },
    );
  }, [data?.learningMap, mergeCompilation, outlineNodeId, planItemId, repository, spaceId]);

  const retryCompilation = useCallback(() => {
    if (!latestCompilation || !repository.retryKnowledgeCoreCompilation) {
      createCompilation("manual");
      return;
    }
    const request = compilationMutations.current.begin();
    setCompilationMutation("retrying");
    void repository.retryKnowledgeCoreCompilation(spaceId, latestCompilation.runId, request.signal).then(
      (run) => {
        if (!compilationMutations.current.isCurrent(request.generation)) return;
        setCompilationMutation("idle");
        mergeCompilation(run);
      },
      () => {
        if (!compilationMutations.current.isCurrent(request.generation)) return;
        setCompilationMutation("error");
      },
    );
  }, [createCompilation, latestCompilation, mergeCompilation, repository, spaceId]);

  useEffect(() => {
    if (
      point
      || !outlineNodeId
      || !data?.learningMap
      || compilationState.phase !== "ready"
      || latestCompilation
      || compilationMutation !== "idle"
      || !repository.createKnowledgeCoreCompilation
    ) return;
    const key = `${spaceId}:${outlineNodeId}:${planItemId}:${data.learningMap.revision}`;
    if (attemptedCompilations.current.has(key)) return;
    attemptedCompilations.current.add(key);
    createCompilation("automatic");
  }, [
    compilationMutation,
    compilationState.phase,
    createCompilation,
    data?.learningMap,
    latestCompilation,
    outlineNodeId,
    planItemId,
    point,
    repository.createKnowledgeCoreCompilation,
    spaceId,
  ]);

  useEffect(() => {
    if (!compilationRunning) return;
    const timer = window.setTimeout(loadCompilations, 1_500);
    return () => window.clearTimeout(timer);
  }, [compilationRunning, loadCompilations]);

  useEffect(() => {
    if (!point) {
      setDraft(null);
      return;
    }
    // The shared desk owns the lifecycle page recorded in the bookmark. This
    // effect may run while LearnPage is departing after an async load; writing
    // page="learn" here would race a deliberate transition into practice.
    // Core changes themselves are written by load() and moveTo().
    setDraft(readStudyLearnDraft(spaceId, point.item_id));
    setSaveFailed(false);
  }, [point, spaceId]);

  const moveTo = (index: number) => {
    const next = points[index];
    if (!next) return;
    selectKnowledgeCore(spaceId, next, "learn");
    setCoreIndex(index);
  };

  const updateDraft = (update: (current: LearnDraft) => LearnDraft) => {
    if (!point) return;
    setDraft((current) => {
      const next = update(current ?? readStudyLearnDraft(spaceId, point.item_id));
      setSaveFailed(!writeDraft(spaceId, point.item_id, next));
      return next;
    });
  };

  const coreCard = (current: StudyKnowledgePoint) => (
    <article className="kq-study-core-sheet" aria-labelledby="study-current-core">
      <header>
        <div>
          <p className="kq-study-placeholder-kicker">这一步要弄懂的</p>
          <h2 id="study-current-core">{current.front}</h2>
        </div>
        <span className="kq-study-core-count">{(coreIndex ?? 0) + 1} / {points.length}</span>
      </header>
      <p className="kq-study-core-statement">{current.gist}</p>
      <p className="kq-study-core-source"><BookOpen aria-hidden /> 来自这本本子中已确认的知识点</p>

      <section className="kq-study-restate" aria-labelledby="study-learner-draft">
        <div>
          <h3 id="study-learner-draft">用自己的话说说</h3>
          <span>可以不完整，这里不评分。</span>
        </div>
        <textarea
          value={draft?.text ?? ""}
          onChange={(event) => {
            const value = event.currentTarget.value;
            updateDraft((currentDraft) => ({
              ...currentDraft,
              text: value,
              updatedAt: new Date().toISOString(),
            }));
          }}
          placeholder="我现在的理解是……"
          aria-label="我的说法"
        />
        <div className="kq-study-inline-actions">
          <button
            type="button"
            onClick={() => updateDraft((currentDraft) => ({
              ...currentDraft,
              compared: !currentDraft.compared,
              updatedAt: new Date().toISOString(),
            }))}
          >
            {draft?.compared ? <EyeOff aria-hidden /> : <Eye aria-hidden />}
            {draft?.compared ? "收起教材对照" : "和教材对一下"}
          </button>
          <button type="button" className="kq-study-secondary-link" onClick={() => document.getElementById("kd-cup-chat")?.click()}>
            <Coffee aria-hidden /> 问小娜
          </button>
        </div>
        {saveFailed ? <p className="kq-study-page-error" role="alert">草稿暂时没有保存，请先保留本页再重试。</p> : null}
      </section>

      {draft?.compared ? (
        <section className="kq-study-comparison" aria-label="教材与我的说法对照">
          <article>
            <p>教材说法</p>
            <strong>{current.gist}</strong>
          </article>
          <article>
            <p>我的说法</p>
            <strong>{draft.text.trim()}</strong>
          </article>
          <p>先找出两种说法关注点的不同；这里不判分，也不会替你改写。</p>
        </section>
      ) : null}
    </article>
  );

  return (
    <section ref={pageRegion} className="kq-study-content-page" aria-label={t("study.pageLearn")} tabIndex={-1}>
      <header className="kq-study-page-heading">
        <p className="kq-study-placeholder-kicker">理解与重构</p>
        <p>一次只处理一个知识核；完整资料仍在右侧书堆。</p>
      </header>

      {snapshot.status === "loading" && !data ? <p role="status">{t("study.pageLoading")}</p> : null}
      {snapshot.status === "error" && !data ? (
        <div className="kq-study-page-alert" role="alert">
          <span>{t("study.pageLoadFailed")}</span>
          <button type="button" onClick={load}>{t("study.retry")}</button>
        </div>
      ) : null}
      {snapshot.status === "error" && data ? (
        <div className="kq-study-page-alert" role="alert">
          <span>{t("study.pageStale")}</span>
          <button type="button" onClick={load}>{t("study.retry")}</button>
        </div>
      ) : null}
      {data?.unavailable?.includes("knowledgePoints") ? (
        <div className="kq-study-page-alert" role="status">
          <span>知识核暂时无法读取；材料与本子数据没有被改动。</span>
          <button type="button" onClick={load}>{t("study.retry")}</button>
        </div>
      ) : null}
      {!point && outlineNodeId && compilationState.phase === "error" && !compilationState.data ? (
        <div className="kq-study-page-alert" role="alert">
          <span>知识核整理状态暂时无法读取；当前学习范围没有改变。</span>
          <button type="button" onClick={loadCompilations}>{t("study.retry")}</button>
        </div>
      ) : null}
      {point ? (
        <nav className="kq-study-core-index" aria-label="这一节的知识点">
          <span className="kq-study-core-index-label"><Lightbulb aria-hidden /> 知识点</span>
          <div>
            {points.map((candidate, index) => {
              const current = index === coreIndex;
              return (
                <button
                  key={candidate.item_id}
                  type="button"
                  className={current ? "is-current" : undefined}
                  aria-current={current ? "step" : undefined}
                  onClick={() => moveTo(index)}
                >
                  <Bookmark aria-hidden />
                  {candidate.front}
                </button>
              );
            })}
          </div>
        </nav>
      ) : null}
      {point ? coreCard(point) : data && !data.unavailable?.includes("knowledgePoints") && compilationRunning ? (
        <div className="kq-study-page-empty" role="status">
          <h2>正在准备学习内容</h2>
          <p>小娜正在后台阅读这一段知识源并整理知识核，完成后会在这里继续。</p>
        </div>
      ) : data && !data.unavailable?.includes("knowledgePoints") && compilationMutation === "starting" ? (
        <div className="kq-study-page-empty" role="status">
          <h2>正在准备学习内容</h2>
          <p>正在启动后台整理，不需要打开对话。</p>
        </div>
      ) : data && !data.unavailable?.includes("knowledgePoints") && latestCompilation?.status === "draft_ready" && latestCompilation.draftArtifactId ? (
        <div className="kq-study-page-empty">
          <h2>学习内容已经准备好</h2>
          <p>采用后会直接显示这一段的知识核。</p>
          <button type="button" className="kq-study-primary-link" onClick={() => requestStudyDraft({
            spaceId,
            artifactId: latestCompilation.draftArtifactId!,
          })}>查看并采用</button>
        </div>
      ) : data && !data.unavailable?.includes("knowledgePoints") && latestCompilation && ["needs_source", "failed", "cancelled"].includes(latestCompilation.status) ? (
        <div className="kq-study-page-empty">
          <h2>{latestCompilation.status === "needs_source" ? "这部分知识源暂时无法读取" : "暂时没有准备好学习内容"}</h2>
          <p>当前目录没有改变，可以直接在这里重新尝试。</p>
          <button type="button" className="kq-study-primary-link" disabled={compilationMutation === "retrying"} onClick={retryCompilation}>
            {compilationMutation === "retrying" ? "正在重试…" : "重试"}
          </button>
        </div>
      ) : data && !data.unavailable?.includes("knowledgePoints") && compilationMutation === "error" ? (
        <div className="kq-study-page-empty" role="alert">
          <h2>暂时没有启动学习内容整理</h2>
          <p>当前目录没有改变，可以直接重试。</p>
          <button type="button" className="kq-study-primary-link" onClick={() => createCompilation("manual")}>重试</button>
        </div>
      ) : data && !data.unavailable?.includes("knowledgePoints") && outlineNodeId && ["initial", "loading"].includes(compilationState.phase) && !compilationState.data ? (
        <div className="kq-study-page-empty" role="status">
          <h2>正在打开这一节</h2>
          <p>正在确认已有学习内容。</p>
        </div>
      ) : data && !data.unavailable?.includes("knowledgePoints") && !(outlineNodeId && compilationState.phase === "error" && !compilationState.data) ? (
        <div className="kq-study-page-empty">
          <h2>{outlineNodeId ? "正在准备这一节" : "先选择要学习的目录"}</h2>
          <p>{outlineNodeId ? "学习内容会在这里自动准备。" : "从计划页选择一个目录条目后，会直接回到这里学习。"}</p>
          <Link className="kq-study-primary-link" to={studyPath(spaceId, "plan")}>回到计划</Link>
        </div>
      ) : null}

      {point ? (
        <nav className="kq-study-core-navigation" aria-label="知识核导航">
          <button type="button" disabled={coreIndex === 0} onClick={() => moveTo((coreIndex ?? 0) - 1)}>
            <ArrowLeft aria-hidden /> 上一个
          </button>
          <Link
            className="kq-study-primary-link"
            to={studyPath(spaceId, "practice")}
            onClick={() => switchStudyMode(spaceId, "practice")}
          >
            去练习这个知识核
          </Link>
          <button type="button" disabled={(coreIndex ?? 0) + 1 >= points.length} onClick={() => moveTo((coreIndex ?? 0) + 1)}>
            下一个 <ArrowRight aria-hidden />
          </button>
        </nav>
      ) : null}
    </section>
  );
}
