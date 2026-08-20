// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { open, save } from "@tauri-apps/plugin-dialog";
import { Database, History, Loader2 } from "lucide-react";
import {
  cmdStudyDataDelete,
  cmdStudyDataExport,
  cmdStudyDataImport,
  cmdStudyDataImportFile,
  cmdStudyMigrationFailuresExport,
  cmdStudyMigrationStatus,
  type StudyLearningBundle,
  type StudyMigrationRecord,
} from "../../chat/study/study-api";
import { Section } from "../../components/ui/Section";
import { Button } from "../../components/ui/Button";
import { useI18n } from "../../lib/i18n";
import { normalizeRepositoryError } from "../../study/repository";

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

type Pending = "export" | "import" | "delete" | null;

/**
 * 学习数据：备份、恢复、彻底删除。学习证据是学生自己的东西，所以取回和销毁的入口
 * 必须存在——但它不属于 Study 工作面。这里替代了原先常驻在 Study 顶栏的「学习数据」
 * 按钮（删除测试：删掉它学生照样能学，那它就不该占着顶栏）。
 *
 * 迁移记录不在这儿，见 `SettingsLearningMigrations`：`migration_key` 这类内部对象名
 * 只在高级模式之后出现。
 */
export function SettingsLearningData({ onDataReset }: { onDataReset?: () => void }) {
  const { t } = useI18n();
  const [bundle, setBundle] = useState<StudyLearningBundle | null>(null);
  const [ownerEmpty, setOwnerEmpty] = useState<boolean | null>(null);
  const [deletePhrase, setDeletePhrase] = useState("");
  const [pending, setPending] = useState<Pending>(null);
  const [failure, setFailure] = useState<"conflict" | "generic" | null>(null);
  const [done, setDone] = useState<"export" | "import" | "delete" | null>(null);

  const run = (kind: NonNullable<Pending>, task: () => Promise<void>) => {
    setPending(kind);
    setFailure(null);
    setDone(null);
    void task()
      .catch((error) => {
        setFailure(normalizeRepositoryError(error).code === "conflict" ? "conflict" : "generic");
      })
      .finally(() => setPending(null));
  };

  const exportAll = () => run("export", async () => {
    const { bundle: next } = await cmdStudyDataExport();
    if (await saveJson("kabuqina-learning-backup.json", next, t("study.advancedExport"))) {
      setDone("export");
    }
  });

  const pickImport = () => run("import", async () => {
    const path = await open({
      title: t("study.advancedImport"),
      multiple: false,
      filters: [{ name: "JSON", extensions: ["json"] }],
    });
    if (!path || Array.isArray(path)) return;
    const next = await cmdStudyDataImportFile(path);
    const empty = ownerBundleIsEmpty((await cmdStudyDataExport()).bundle);
    setBundle(next);
    setOwnerEmpty(empty);
    if (!empty) setFailure("conflict");
  });

  const confirmImport = () => run("import", async () => {
    if (!bundle || ownerEmpty !== true) return;
    await cmdStudyDataImport(bundle);
    setBundle(null);
    setOwnerEmpty(null);
    setDone("import");
    onDataReset?.();
  });

  const deleteAll = () => run("delete", async () => {
    if (deletePhrase !== DELETE_PHRASE) return;
    await cmdStudyDataDelete(DELETE_PHRASE);
    setDeletePhrase("");
    setDone("delete");
    onDataReset?.();
  });

  const busy = pending !== null;

  return (
    <Section icon={Database} title={t("study.advancedData")} desc={t("study.advancedDataLead")}>
      <div className="space-y-5">
        {failure ? (
          <p className="text-sm leading-relaxed text-[var(--danger)]" role="alert">
            {t(failure === "conflict" ? "study.advancedImportConflict" : "study.advancedActionFailed")}
          </p>
        ) : null}
        {done ? (
          <p className="text-sm leading-relaxed text-[var(--success)]" role="status">
            {t(
              done === "export"
                ? "study.advancedExportDone"
                : done === "import"
                  ? "study.advancedImportDone"
                  : "study.advancedDeleteDone",
            )}
          </p>
        ) : null}

        <div className="space-y-2">
          <p className="text-sm leading-relaxed text-[var(--kq-color-ink)]">{t("study.advancedExportHint")}</p>
          <Button type="button" disabled={busy} onClick={exportAll}>
            {pending === "export" ? <Loader2 className="size-4 animate-spin" aria-hidden /> : null}
            {t("study.advancedExport")}
          </Button>
        </div>

        <div className="space-y-2 border-t border-[var(--kq-color-border)] pt-4">
          <p className="text-sm leading-relaxed text-[var(--kq-color-ink)]">{t("study.advancedImportHint")}</p>
          <div className="flex flex-wrap items-center gap-2">
            <Button type="button" variant="secondary" disabled={busy} onClick={pickImport}>
              {pending === "import" ? <Loader2 className="size-4 animate-spin" aria-hidden /> : null}
              {t("study.advancedImport")}
            </Button>
            {bundle ? (
              <>
                <span className="text-sm text-[var(--kq-color-muted)]" role="status">
                  {t("study.advancedImportReady", { count: bundleSections(bundle) })}
                </span>
                {ownerEmpty ? (
                  <Button type="button" disabled={busy} onClick={confirmImport}>
                    {t("study.advancedImportConfirm")}
                  </Button>
                ) : null}
              </>
            ) : null}
          </div>
        </div>

        <div className="space-y-2 border-t border-[var(--kq-color-border)] pt-4">
          <h3 className="text-sm font-semibold text-[var(--kq-color-strong)]">{t("study.advancedDelete")}</h3>
          <p className="text-sm leading-relaxed text-[var(--kq-color-muted)]">{t("study.advancedDeleteHint")}</p>
          <label className="block space-y-1.5 text-sm text-[var(--kq-color-ink)]">
            <span>{t("study.advancedDeletePhrase")}</span>
            <input
              className="w-full max-w-md rounded-[var(--radius-shell-lg)] border border-[var(--kq-color-border)] bg-[var(--kq-input-surface)] px-3 py-2 font-mono text-xs text-[var(--kq-color-ink)] outline-none focus:border-[var(--kq-color-primary)]"
              value={deletePhrase}
              onChange={(event) => setDeletePhrase(event.currentTarget.value)}
              autoComplete="off"
              spellCheck={false}
            />
          </label>
          <Button
            type="button"
            variant="secondary"
            disabled={busy || deletePhrase !== DELETE_PHRASE}
            onClick={deleteAll}
            className="text-[var(--danger)] hover:opacity-80"
          >
            {pending === "delete" ? <Loader2 className="size-4 animate-spin" aria-hidden /> : null}
            {t("study.advancedDeleteConfirm")}
          </Button>
        </div>
      </div>
    </Section>
  );
}

/**
 * 迁移记录。`migration_key` 是内部对象名，不该铺在学生面前——因此只在高级模式后出现。
 */
export function SettingsLearningMigrations() {
  const { t } = useI18n();
  const [migrations, setMigrations] = useState<StudyMigrationRecord[] | null>(null);
  const [pending, setPending] = useState(false);
  const [failed, setFailed] = useState(false);

  const run = (task: () => Promise<void>) => {
    setPending(true);
    setFailed(false);
    void task().catch(() => setFailed(true)).finally(() => setPending(false));
  };

  return (
    <Section icon={History} title={t("study.advancedMigrations")} desc={t("settings.migrationsDesc")}>
      <div className="space-y-3">
        {failed ? (
          <p className="text-sm leading-relaxed text-[var(--danger)]" role="alert">
            {t("study.advancedActionFailed")}
          </p>
        ) : null}
        <div className="flex flex-wrap gap-2">
          <Button
            type="button"
            variant="secondary"
            disabled={pending}
            onClick={() => run(async () => setMigrations((await cmdStudyMigrationStatus()).migrations))}
          >
            {t("study.advancedMigrations")}
          </Button>
          <Button
            type="button"
            variant="secondary"
            disabled={pending}
            onClick={() => run(async () => {
              const failures = await cmdStudyMigrationFailuresExport();
              await saveJson(
                "kabuqina-learning-migration-failures.json",
                failures,
                t("study.advancedMigrationFailures"),
              );
            })}
          >
            {t("study.advancedMigrationFailures")}
          </Button>
        </div>
        {migrations ? (
          migrations.length ? (
            <ul className="space-y-1.5">
              {migrations.map((migration) => (
                <li key={migration.migration_key} className="flex flex-wrap items-baseline gap-x-2 text-xs">
                  <strong className="font-mono text-[var(--kq-color-strong)]">{migration.migration_key}</strong>
                  <span className="text-[var(--kq-color-muted)]">
                    {migration.status} · {migration.created_at}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-[var(--kq-color-muted)]">{t("study.advancedMigrationEmpty")}</p>
          )
        ) : null}
      </div>
    </Section>
  );
}
