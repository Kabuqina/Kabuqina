// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ArrowLeft, ArrowRight, BookOpen, Coffee, Eye, EyeOff } from "lucide-react";
import { Link } from "react-router-dom";
import type { StudyKnowledgePoint } from "../../chat/study/study-api";
import { useI18n } from "../../lib/i18n";
import { RequestCoordinator, type Loadable } from "../loadable";
import type { StudyLearnHome } from "../repository";
import { useStudyRepository } from "../repositoryContext";
import { studyPath } from "../routeModel";
import {
  resolveKnowledgeCore,
  selectKnowledgeCore,
  switchStudyMode,
} from "../studyLocation";

const DRAFT_PREFIX = "kabuqina.study.learn-draft.v1";

type LearnDraft = { version: 1; text: string; compared: boolean; updatedAt: string };

function retained(state: Loadable<StudyLearnHome>): StudyLearnHome | undefined {
  if (state.status === "ready") return state.data;
  if (state.status === "loading" || state.status === "error") return state.previous;
  return undefined;
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
  const [snapshot, setSnapshot] = useState<Loadable<StudyLearnHome>>({ status: "idle" });
  const [coreIndex, setCoreIndex] = useState<number | null>(null);
  const [draft, setDraft] = useState<LearnDraft | null>(null);
  const [saveFailed, setSaveFailed] = useState(false);
  const data = retained(snapshot);
  const points = useMemo(() => data?.knowledgePoints ?? [], [data?.knowledgePoints]);
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
        const resolved = resolveKnowledgeCore(spaceId, next.knowledgePoints);
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
    pageRegion.current?.focus();
    load();
    return () => coordinator.cancel();
  }, [load]);

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
      <p className="kq-study-core-source"><BookOpen aria-hidden /> 来自这门课中已确认的知识点</p>

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
          <span>知识核暂时无法读取；材料与课程数据没有被改动。</span>
          <button type="button" onClick={load}>{t("study.retry")}</button>
        </div>
      ) : null}
      {point ? coreCard(point) : data && !data.unavailable?.includes("knowledgePoints") ? (
        <div className="kq-study-page-empty">
          <h2>当前范围还没有知识核</h2>
          <p>先在计划页确认这一段要学什么，或请小娜基于已导入材料整理一份待审核草稿。</p>
          <Link className="kq-study-secondary-link" to={studyPath(spaceId, "plan")}>回到计划</Link>
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
