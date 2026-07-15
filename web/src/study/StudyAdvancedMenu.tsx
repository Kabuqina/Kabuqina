// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { invoke } from "@tauri-apps/api/core";
import { open, save } from "@tauri-apps/plugin-dialog";
import { Database, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import {
  cmdStudyDataDelete,
  cmdStudyDataExport,
  cmdStudyDataImport,
  cmdStudyDataImportFile,
  cmdStudyMigrationFailuresExport,
  cmdStudyMigrationStatus,
  type StudyLearningBundle,
  type StudyMigrationRecord,
} from "../chat/study/study-api";
import { useI18n } from "../lib/i18n";

const DELETE_PHRASE = "DELETE ALL LEARNING DATA";

function bundleSections(bundle: StudyLearningBundle): number {
  return [bundle.spaces, bundle.artifacts, bundle.items, bundle.activities, bundle.migrations]
    .filter((value) => Array.isArray(value) && value.length > 0).length;
}

async function saveJson(defaultPath: string, value: unknown, title: string): Promise<boolean> {
  const path = await save({ title, defaultPath, filters: [{ name: "JSON", extensions: ["json"] }] });
  if (!path) return false;
  await invoke("cmd_write_text_file", { pathStr: path, content: JSON.stringify(value, null, 2) });
  return true;
}

/** Owner-wide learning-data controls. It intentionally has no current-space prop. */
export function StudyAdvancedMenu({ onOwnerDataReset }: { onOwnerDataReset: () => void }) {
  const { t } = useI18n();
  const trigger = useRef<HTMLButtonElement>(null);
  const close = useRef<HTMLButtonElement>(null);
  const [visible, setVisible] = useState(false);
  const [bundle, setBundle] = useState<StudyLearningBundle | null>(null);
  const [migrations, setMigrations] = useState<StudyMigrationRecord[] | null>(null);
  const [deletePhrase, setDeletePhrase] = useState("");
  const [pending, setPending] = useState<"export" | "import" | "migrations" | "delete" | null>(null);
  const [failed, setFailed] = useState(false);

  const closeDialog = () => {
    setVisible(false);
    setBundle(null);
    setMigrations(null);
    setDeletePhrase("");
    setFailed(false);
    requestAnimationFrame(() => trigger.current?.focus());
  };
  useEffect(() => { if (visible) close.current?.focus(); }, [visible]);

  const action = (kind: NonNullable<typeof pending>, task: () => Promise<void>) => {
    setPending(kind);
    setFailed(false);
    void task().catch(() => setFailed(true)).finally(() => setPending(null));
  };
  const exportAll = () => action("export", async () => {
    const { bundle: next } = await cmdStudyDataExport();
    await saveJson("kabuqina-learning-backup.json", next, t("study.advancedExport"));
  });
  const pickImport = () => action("import", async () => {
    const path = await open({ title: t("study.advancedImport"), multiple: false, filters: [{ name: "JSON", extensions: ["json"] }] });
    if (!path || Array.isArray(path)) return;
    setBundle(await cmdStudyDataImportFile(path));
  });
  const confirmImport = () => action("import", async () => {
    if (!bundle) return;
    await cmdStudyDataImport(bundle);
    onOwnerDataReset();
    closeDialog();
  });
  const showMigrations = () => action("migrations", async () => {
    setMigrations((await cmdStudyMigrationStatus()).migrations);
  });
  const exportFailures = () => action("migrations", async () => {
    const failures = await cmdStudyMigrationFailuresExport();
    await saveJson("kabuqina-learning-migration-failures.json", failures, t("study.advancedMigrationFailures"));
  });
  const deleteAll = () => action("delete", async () => {
    if (deletePhrase !== DELETE_PHRASE) return;
    await cmdStudyDataDelete(DELETE_PHRASE);
    onOwnerDataReset();
    closeDialog();
  });

  return <>
    <button ref={trigger} type="button" className="kq-study-top-action" aria-haspopup="dialog" aria-expanded={visible} onClick={() => setVisible(true)}><Database aria-hidden /><span>{t("study.advancedData")}</span></button>
    {visible ? createPortal(<div className="kq-study-dialog-backdrop" role="presentation"><section className="kq-study-dialog kq-study-governance-dialog" role="dialog" aria-modal="true" aria-label={t("study.advancedData")}>
      <button ref={close} type="button" className="kq-study-dialog-close" onClick={closeDialog} aria-label={t("study.advancedCancel")}><X aria-hidden /></button>
      <header className="kq-study-card-title"><div><p>{t("study.advancedData")}</p><h2>{t("study.advancedData")}</h2></div></header>
      <p className="kq-study-muted">{t("study.advancedDataLead")}</p>
      {failed ? <p className="kq-study-page-error" role="alert">{t("study.advancedActionFailed")}</p> : null}
      <section className="kq-study-governance-section"><h3>{t("study.advancedExport")}</h3><p>{t("study.advancedExportHint")}</p><button type="button" disabled={pending !== null} onClick={exportAll}>{t("study.advancedExport")}</button></section>
      <section className="kq-study-governance-section"><h3>{t("study.advancedImport")}</h3><p>{t("study.advancedImportHint")}</p><button type="button" disabled={pending !== null} onClick={pickImport}>{t("study.advancedImport")}</button>{bundle ? <div><p role="status">{t("study.advancedImportReady", { count: bundleSections(bundle) })}</p><button type="button" disabled={pending !== null} onClick={confirmImport}>{t("study.advancedImportConfirm")}</button></div> : null}</section>
      <section className="kq-study-governance-section"><h3>{t("study.advancedMigrations")}</h3><div className="kq-study-inline-actions"><button type="button" disabled={pending !== null} onClick={showMigrations}>{t("study.advancedMigrations")}</button><button type="button" disabled={pending !== null} onClick={exportFailures}>{t("study.advancedMigrationFailures")}</button></div>{migrations ? (migrations.length ? <ul className="kq-study-migration-list">{migrations.map((migration) => <li key={migration.migration_key}><strong>{migration.migration_key}</strong><span>{migration.status} · {migration.created_at}</span></li>)}</ul> : <p className="kq-study-muted">{t("study.advancedMigrationEmpty")}</p>) : null}</section>
      <section className="kq-study-governance-section is-danger"><h3>{t("study.advancedDelete")}</h3><p>{t("study.advancedDeleteHint")}</p><label>{t("study.advancedDeletePhrase")}<input value={deletePhrase} onChange={(event) => setDeletePhrase(event.currentTarget.value)} autoComplete="off" /></label><button type="button" disabled={pending !== null || deletePhrase !== DELETE_PHRASE} onClick={deleteAll}>{t("study.advancedDeleteConfirm")}</button></section>
    </section></div>, document.body) : null}
  </>;
}
