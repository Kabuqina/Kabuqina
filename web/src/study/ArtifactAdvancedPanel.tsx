// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useEffect, useRef, useState } from "react";
import type { StudySourceRef } from "../chat/study/study-api";
import { useI18n } from "../lib/i18n";
import { normalizeRepositoryError, type StudyArtifactDetail } from "./repository";
import { useStudyRepository } from "./repositoryContext";

/** Explicit, per-artifact governance surface. It never loads audit data itself. */
export function ArtifactAdvancedPanel({ spaceId, detail, onArtifactStale }: { spaceId: string; detail: StudyArtifactDetail; onArtifactStale?: () => void }) {
  const { t } = useI18n();
  const repository = useStudyRepository();
  const contextKey = `${spaceId}\u0000${detail.artifactId}`;
  const request = useRef<{ key: string; controller: AbortController } | null>(null);
  const [state, setState] = useState<{
    key: string;
    open: boolean;
    raw: boolean;
    audit: "idle" | "loading" | "ready" | "error";
    refs: StudySourceRef[];
  }>({ key: contextKey, open: false, raw: false, audit: "idle", refs: [] });
  const current = state.key === contextKey
    ? state
    : { key: contextKey, open: false, raw: false, audit: "idle" as const, refs: [] };

  useEffect(() => {
    request.current?.controller.abort();
    request.current = null;
    setState({ key: contextKey, open: false, raw: false, audit: "idle", refs: [] });
    return () => request.current?.controller.abort();
  }, [contextKey]);

  const showAudit = () => {
    const controller = new AbortController();
    request.current?.controller.abort();
    request.current = { key: contextKey, controller };
    setState((previous) => ({ ...(previous.key === contextKey ? previous : current), audit: "loading" }));
    void repository.loadSourceAudit(spaceId, detail.artifactId, controller.signal).then(
      (next) => {
        if (controller.signal.aborted || request.current?.key !== contextKey) return;
        setState((previous) => previous.key === contextKey
          ? { ...previous, refs: next, audit: "ready" }
          : previous);
      },
      (error) => {
        if (controller.signal.aborted || request.current?.key !== contextKey) return;
        if (normalizeRepositoryError(error).code === "not-found") {
          request.current = null;
          setState({ key: contextKey, open: false, raw: false, audit: "idle", refs: [] });
          onArtifactStale?.();
          return;
        }
        setState((previous) => previous.key === contextKey
          ? { ...previous, audit: "error" }
          : previous);
      },
    );
  };

  const renderRef = (ref: StudySourceRef, index: number) => {
    if (typeof ref === "string") return <li key={index}><span>{ref}</span></li>;
    return <li key={index}>{Object.entries(ref).map(([key, value]) => <span key={key}><b>{key}</b>{value === null ? "null" : String(value)}</span>)}</li>;
  };

  return <section className="kq-study-artifact-advanced">
    <button type="button" className="kq-study-secondary-button" aria-expanded={current.open} onClick={() => setState((previous) => ({ ...(previous.key === contextKey ? previous : current), open: !current.open }))}>{t("study.advancedArtifact")}</button>
    {current.open ? <div className="kq-study-artifact-advanced-panel">
      <button type="button" onClick={showAudit} disabled={current.audit === "loading"}>{current.audit === "loading" ? t("study.advancedLoadingAudit") : t("study.advancedSourceAudit")}</button>
      {current.audit === "error" ? <p className="kq-study-page-error" role="alert">{t("study.advancedAuditFailed")}</p> : null}
      {current.audit === "ready" ? (current.refs.length ? <ul className="kq-study-source-audit">{current.refs.map(renderRef)}</ul> : <p className="kq-study-muted">{t("study.advancedNoSources")}</p>) : null}
      <button type="button" onClick={() => setState((previous) => ({ ...(previous.key === contextKey ? previous : current), raw: !current.raw }))} aria-expanded={current.raw}>{t("study.advancedRawJson")}</button>
      {current.raw ? <pre className="kq-study-raw-json">{JSON.stringify(detail.envelope, null, 2)}</pre> : null}
    </div> : null}
  </section>;
}
