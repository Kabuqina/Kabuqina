// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { invoke } from "@tauri-apps/api/core";
import { open, save } from "@tauri-apps/plugin-dialog";
import { Database, X } from "lucide-react";
import { useEffect, useRef, useState, type KeyboardEvent as ReactKeyboardEvent } from "react";
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
import { normalizeRepositoryError } from "./repository";

const DELETE_PHRASE = "DELETE ALL LEARNING DATA";

function bundleSections(bundle: StudyLearningBundle): number {
  return [bundle.spaces, bundle.artifacts, bundle.items, bundle.activities, bundle.migrations]
    .filter((value) => Array.isArray(value) && value.length > 0).length;
}

function ownerBundleIsEmpty(bundle: StudyLearningBundle): boolean {
  return [bundle.spaces, bundle.artifacts, bundle.items, bundle.activities, bundle.migrations]
    .every((value) => !Array.isArray(value) || value.length === 0);
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
  const dialog = useRef<HTMLElement>(null);
  const close = useRef<HTMLButtonElement>(null);
  const [visible, setVisible] = useState(false);
  const [bundle, setBundle] = useState<StudyLearningBundle | null>(null);
  const [ownerEmpty, setOwnerEmpty] = useState<boolean | null>(null);
  const [migrations, setMigrations] = useState<StudyMigrationRecord[] | null>(null);
  const [deletePhrase, setDeletePhrase] = useState("");
  const [pending, setPending] = useState<"export" | "import" | "migrations" | "delete" | null>(null);
  const [failure, setFailure] = useState<"conflict" | "generic" | null>(null);

  const closeDialog = () => {
    setVisible(false);
    setBundle(null);
    setOwnerEmpty(null);
    setMigrations(null);
    setDeletePhrase("");
    setFailure(null);
    requestAnimationFrame(() => trigger.current?.focus());
  };
  useEffect(() => { if (visible) close.current?.focus(); }, [visible]);

  const action = (kind: NonNullable<typeof pending>, task: () => Promise<void>) => {
    setPending(kind);
    setFailure(null);
    void task().catch((error) => {
      setFailure(normalizeRepositoryError(error).code === "conflict" ? "conflict" : "generic");
    }).finally(() => setPending(null));
  };
  const exportAll = () => action("export", async () => {
    const { bundle: next } = await cmdStudyDataExport();
    await saveJson("kabuqina-learning-backup.json", next, t("study.advancedExport"));
  });
  const pickImport = () => action("import", async () => {
    const path = await open({ title: t("study.advancedImport"), multiple: false, filters: [{ name: "JSON", extensions: ["json"] }] });
    if (!path || Array.isArray(path)) return;
    const next = await cmdStudyDataImportFile(path);
    const current = (await cmdStudyDataExport()).bundle;
    const empty = ownerBundleIsEmpty(current);
    setBundle(next);
    setOwnerEmpty(empty);
    if (!empty) setFailure("conflict");
  });
  const confirmImport = () => action("import", async () => {
    if (!bundle || ownerEmpty !== true) return;
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

  const onKeyDown = (event: ReactKeyboardEvent<HTMLElement>) => {
    if (event.key === "Escape") {
      event.preventDefault();
      closeDialog();
      return;
    }
    if (event.key !== "Tab") return;
    const focusable = [...(dialog.current?.querySelectorAll<HTMLElement>(
      "button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), a[href]",
    ) ?? [])].filter((element) => element.tabIndex !== -1);
    if (!focusable.length) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
    if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
  };

  return <>
    <button ref={trigger} type="button" className="kq-study-top-action" aria-haspopup="dialog" aria-expanded={visible} onClick={() => setVisible(true)}><Database aria-hidden /><span>{t("study.advancedData")}</span></button>
    {visible ? createPortal(<div className="kq-study-dialog-backdrop" role="presentation"><section ref={dialog} className="kq-study-dialog kq-study-governance-dialog" role="dialog" aria-modal="true" aria-label={t("study.advancedData")} onKeyDown={onKeyDown}>
      <button ref={close} type="button" className="kq-study-dialog-close" onClick={closeDialog} aria-label={t("study.advancedCancel")}><X aria-hidden /></button>
      <header className="kq-study-card-title"><div><p>{t("study.advancedData")}</p><h2>{t("study.advancedData")}</h2></div></header>
      <p className="kq-study-muted">{t("study.advancedDataLead")}</p>
      {failure ? <p className="kq-study-page-error" role="alert">{t(failure === "conflict" ? "study.advancedImportConflict" : "study.advancedActionFailed")}</p> : null}
      <section className="kq-study-governance-section"><h3>{t("study.advancedExport")}</h3><p>{t("study.advancedExportHint")}</p><button type="button" disabled={pending !== null} onClick={exportAll}>{t("study.advancedExport")}</button></section>
      <section className="kq-study-governance-section"><h3>{t("study.advancedImport")}</h3><p>{t("study.advancedImportHint")}</p><button type="button" disabled={pending !== null} onClick={pickImport}>{t("study.advancedImport")}</button>{bundle ? <div><p role="status">{t("study.advancedImportReady", { count: bundleSections(bundle) })}</p>{ownerEmpty ? <button type="button" disabled={pending !== null} onClick={confirmImport}>{t("study.advancedImportConfirm")}</button> : null}</div> : null}</section>
      <section className="kq-study-governance-section"><h3>{t("study.advancedMigrations")}</h3><div className="kq-study-inline-actions"><button type="button" disabled={pending !== null} onClick={showMigrations}>{t("study.advancedMigrations")}</button><button type="button" disabled={pending !== null} onClick={exportFailures}>{t("study.advancedMigrationFailures")}</button></div>{migrations ? (migrations.length ? <ul className="kq-study-migration-list">{migrations.map((migration) => <li key={migration.migration_key}><strong>{migration.migration_key}</strong><span>{migration.status} · {migration.created_at}</span></li>)}</ul> : <p className="kq-study-muted">{t("study.advancedMigrationEmpty")}</p>) : null}</section>
      <section className="kq-study-governance-section is-danger"><h3>{t("study.advancedDelete")}</h3><p>{t("study.advancedDeleteHint")}</p><label>{t("study.advancedDeletePhrase")}<input value={deletePhrase} onChange={(event) => setDeletePhrase(event.currentTarget.value)} autoComplete="off" /></label><button type="button" disabled={pending !== null || deletePhrase !== DELETE_PHRASE} onClick={deleteAll}>{t("study.advancedDeleteConfirm")}</button></section>
    </section></div>, document.body) : null}
  </>;
}
