// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useState } from "react";
import { useI18n } from "../lib/i18n";
import type { StudyArtifactDetail } from "./repository";
import { useStudyRepository } from "./repositoryContext";

/** Explicit, per-artifact governance surface. It never loads audit data itself. */
export function ArtifactAdvancedPanel({ spaceId, detail }: { spaceId: string; detail: StudyArtifactDetail }) {
  const { t } = useI18n();
  const repository = useStudyRepository();
  const [open, setOpen] = useState(false);
  const [raw, setRaw] = useState(false);
  const [audit, setAudit] = useState<"idle" | "loading" | "ready" | "error">("idle");
  const [refs, setRefs] = useState<Array<Record<string, string>>>([]);

  const showAudit = () => {
    setAudit("loading");
    const controller = new AbortController();
    void repository.loadSourceAudit(spaceId, detail.artifactId, controller.signal).then(
      (next) => { setRefs(next); setAudit("ready"); },
      () => setAudit("error"),
    );
  };

  return <section className="kq-study-artifact-advanced">
    <button type="button" className="kq-study-secondary-button" aria-expanded={open} onClick={() => setOpen((value) => !value)}>{t("study.advancedArtifact")}</button>
    {open ? <div className="kq-study-artifact-advanced-panel">
      <button type="button" onClick={showAudit} disabled={audit === "loading"}>{audit === "loading" ? t("study.advancedLoadingAudit") : t("study.advancedSourceAudit")}</button>
      {audit === "error" ? <p className="kq-study-page-error" role="alert">{t("study.advancedAuditFailed")}</p> : null}
      {audit === "ready" ? (refs.length ? <ul className="kq-study-source-audit">{refs.map((ref, index) => <li key={index}>{Object.entries(ref).map(([key, value]) => <span key={key}><b>{key}</b>{value}</span>)}</li>)}</ul> : <p className="kq-study-muted">{t("study.advancedNoSources")}</p>) : null}
      <button type="button" onClick={() => setRaw((value) => !value)} aria-expanded={raw}>{t("study.advancedRawJson")}</button>
      {raw ? <pre className="kq-study-raw-json">{JSON.stringify(detail.envelope, null, 2)}</pre> : null}
    </div> : null}
  </section>;
}
