// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useCallback, useEffect, useRef, useState } from "react";
import { BookOpen, RotateCw, X } from "lucide-react";
import {
  cmdActivityRecords,
  type GlobalActivityRecord,
  type GlobalActivityResponse,
} from "./activityApi";

type ActivityPanelProps = {
  open: boolean;
  onClose: () => void;
  onReturn: (target: string) => void;
  load?: typeof cmdActivityRecords;
};

const labels: Record<GlobalActivityRecord["status"], string> = {
  running: "正在进行",
  waiting: "等你继续",
  interrupted: "上次中断",
  failed: "没有完成",
  completed: "最近完成",
  recoverable: "可回到现场",
};

function safeTarget(record: GlobalActivityRecord): string {
  const target = record.targetAvailable ? record.returnTarget : record.fallbackTarget;
  if (!target.startsWith("/") || target.startsWith("//")) return "/study";
  if (
    record.kind === "knowledge_core_compilation"
    && record.sourceStatus === "draft_ready"
    && record.draftArtifactId
  ) {
    const separator = target.includes("?") ? "&" : "?";
    return `${target}${separator}draft=${encodeURIComponent(record.draftArtifactId)}`;
  }
  return target;
}

function activityLabel(record: GlobalActivityRecord): string {
  if (record.kind !== "knowledge_core_compilation") return labels[record.status];
  switch (record.sourceStatus) {
    case "queued":
    case "reading":
    case "generating":
    case "validating":
      return "正在整理知识核";
    case "draft_ready":
      return "知识核待采用";
    case "needs_source":
      return "等待知识源";
    case "failed":
      return "整理未完成";
    case "cancelled":
      return "已取消";
    default:
      return labels[record.status];
  }
}

function activityAction(record: GlobalActivityRecord): string {
  if (record.kind !== "knowledge_core_compilation") {
    return record.canResume ? "继续" : "回到现场";
  }
  if (record.sourceStatus === "draft_ready") return "查看草稿";
  if (record.sourceStatus === "needs_source" || record.sourceStatus === "failed") return "处理";
  return "查看";
}

export function ActivityPanel({ open, onClose, onReturn, load = cmdActivityRecords }: ActivityPanelProps) {
  const [state, setState] = useState<
    | { status: "idle" | "loading" }
    | { status: "ready"; data: GlobalActivityResponse }
    | { status: "error" }
  >({ status: "idle" });
  const closeButton = useRef<HTMLButtonElement>(null);

  const refresh = useCallback(() => {
    const controller = new AbortController();
    setState({ status: "loading" });
    void load(undefined, 100).then(
      (data) => {
        if (!controller.signal.aborted) setState({ status: "ready", data });
      },
      () => {
        if (!controller.signal.aborted) setState({ status: "error" });
      },
    );
    return () => controller.abort();
  }, [load]);

  useEffect(() => {
    if (!open) return;
    const cancel = refresh();
    closeButton.current?.focus();
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => {
      cancel();
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [onClose, open, refresh]);

  if (!open) return null;
  // v0.5.0 is Study-first. The backend deliberately retains cross-domain
  // projection data for v0.6, but the current product surface must not expose
  // dormant Studio scenes as something the learner can resume.
  const items = state.status === "ready"
    ? state.data.items.filter((item) => item.domain === "study")
    : [];

  return (
    <div className="kq-activity-scrim" role="presentation" onMouseDown={(event) => {
      if (event.target === event.currentTarget) onClose();
    }}>
      <aside id="kq-global-activity" className="kq-activity-panel" role="dialog" aria-modal="true" aria-labelledby="kq-activity-heading">
        <header>
          <div>
            <p>学习现场</p>
            <h2 id="kq-activity-heading">进行中</h2>
          </div>
          <button ref={closeButton} type="button" aria-label="关闭进行中" onClick={onClose}>
            <X aria-hidden />
          </button>
        </header>

        {state.status === "loading" || state.status === "idle" ? <p role="status">正在整理现场…</p> : null}
        {state.status === "error" ? (
          <div className="kq-activity-error" role="alert">
            <span>暂时没有读到进行中的现场。</span>
            <button type="button" onClick={refresh}><RotateCw aria-hidden />再试一次</button>
          </div>
        ) : null}
        {state.status === "ready" && !items.length ? (
          <div className="kq-activity-empty">
            <p>现在没有需要接续的现场。</p>
            <span>开始一本学习本后，需要接续的内容会出现在这里。</span>
          </div>
        ) : null}
        {items.length ? (
          <ol className="kq-global-activity-list">
            {items.map((item) => {
              return (
                <li key={item.id} data-status={item.status}>
                  <span className="kq-global-activity-domain"><BookOpen aria-hidden />学习</span>
                  <div>
                    <span className="kq-global-activity-status">{activityLabel(item)}</span>
                    <strong>{item.title}</strong>
                    {item.updatedAt ? <time dateTime={item.updatedAt}>{new Date(item.updatedAt).toLocaleString()}</time> : null}
                  </div>
                  <button type="button" onClick={() => onReturn(safeTarget(item))}>
                    {activityAction(item)}
                  </button>
                </li>
              );
            })}
          </ol>
        ) : null}
      </aside>
    </div>
  );
}
