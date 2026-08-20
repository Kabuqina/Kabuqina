// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useCallback, useEffect, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { ArchiveRestore, RefreshCw, ShieldAlert, Trash2 } from "lucide-react";
import { Button } from "../../components/ui/Button";
import { Section } from "../../components/ui/Section";
import { confirm } from "../../lib/confirmDialog";
import { useI18n } from "../../lib/i18n";

type LegacyJobSummary = { id: string; name: string; deliver: string };

type LegacyInventory = {
  contractVersion: string;
  sourceHomePath: string;
  canonicalHomePresent: boolean;
  legacyHomePresent: boolean;
  removedEnvKeys: string[];
  qqLegacyHomeKeys: string[];
  exactFilePaths: string[];
  protectedDirectoryPaths: string[];
  removedConfigPlatforms: string[];
  removedChannelPlatforms: string[];
  legacyJobs: LegacyJobSummary[];
  legacySessionOrigins: number;
  totalCleanupItems: number;
};

type LegacyExport = {
  exportId: string;
  path: string;
  exportedFiles: number;
  skippedOversizeFiles: string[];
};

type LegacyCleanup = {
  removedEnvKeys: number;
  migratedQqHomeKeys: number;
  removedFiles: number;
  removedConfigPlatforms: number;
  removedChannelPlatforms: number;
  retainedLegacyJobs: number;
  retainedLegacySessionOrigins: number;
  remainingCleanupItems: number;
};

export function SettingsLegacyChannels() {
  const { t } = useI18n();
  const [inventory, setInventory] = useState<LegacyInventory | null>(null);
  const [exported, setExported] = useState<LegacyExport | null>(null);
  const [cleanup, setCleanup] = useState<LegacyCleanup | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    const next = await invoke<LegacyInventory>("cmd_legacy_channel_inventory");
    setInventory(next);
  }, []);

  useEffect(() => {
    void refresh().catch((cause) => setError(String(cause)));
  }, [refresh]);

  const exportLegacy = async () => {
    setBusy(true);
    setError(null);
    try {
      const result = await invoke<LegacyExport>("cmd_legacy_channel_export");
      setExported(result);
      setCleanup(null);
    } catch (cause) {
      setError(String(cause));
      setExported(null);
    } finally {
      setBusy(false);
    }
  };

  const cleanupLegacy = async () => {
    if (!exported) return;
    const ok = await confirm({
      title: t("settings.legacyCleanupConfirmTitle"),
      message: t("settings.legacyCleanupConfirmBody", { path: exported.path }),
      confirmLabel: t("settings.legacyCleanupAction"),
      cancelLabel: t("dialog.cancel"),
      tone: "danger",
    });
    if (!ok) return;
    setBusy(true);
    setError(null);
    try {
      const result = await invoke<LegacyCleanup>("cmd_legacy_channel_cleanup", {
        exportId: exported.exportId,
        confirmation: "REMOVE_LEGACY_CHANNEL_DATA",
      });
      setCleanup(result);
      setExported(null);
      await refresh();
    } catch (cause) {
      setError(String(cause));
      // Cleanup is bound to one verified filesystem snapshot. Any backend
      // rejection invalidates that authorization; require a fresh export
      // instead of letting the user retry a potentially stale snapshot.
      setExported(null);
    } finally {
      setBusy(false);
    }
  };

  const hasHistory = Boolean(inventory && (
    inventory.totalCleanupItems > 0 ||
    inventory.legacyJobs.length > 0 ||
    inventory.legacySessionOrigins > 0 ||
    inventory.protectedDirectoryPaths.length > 0 ||
    inventory.legacyHomePresent
  ));

  return (
    <Section icon={ShieldAlert} title={t("settings.legacyChannelsTitle")} desc={t("settings.legacyChannelsLead")}>
      <div className="w-full min-w-0 space-y-3 text-xs">
        {!inventory ? (
          <p className="text-[var(--kq-color-muted)]">{t("settings.legacyChannelsScanning")}</p>
        ) : !hasHistory ? (
          <p className="text-[var(--success)]">{t("settings.legacyChannelsClean")}</p>
        ) : (
          <>
            <dl className="grid gap-2 sm:grid-cols-2">
              <div><dt className="font-medium text-[var(--kq-color-strong)]">{t("settings.legacyCleanupItems")}</dt><dd>{inventory.totalCleanupItems}</dd></div>
              <div><dt className="font-medium text-[var(--kq-color-strong)]">{t("settings.legacyOpaqueRecords")}</dt><dd>{inventory.legacyJobs.length + inventory.legacySessionOrigins}</dd></div>
            </dl>
            <p className="break-all text-[var(--kq-color-muted)]">{inventory.sourceHomePath}</p>
            {inventory.legacyHomePresent ? (
              <p className="text-[var(--kq-color-muted)]">
                {inventory.canonicalHomePresent
                  ? t("settings.legacyHomeBothPresent")
                  : t("settings.legacyHomeActive")}
              </p>
            ) : null}
            {inventory.legacyJobs.length > 0 ? (
              <p className="text-[var(--warning)]">
                {t("settings.legacyJobsRetained", { count: inventory.legacyJobs.length })}
              </p>
            ) : null}
            {inventory.legacySessionOrigins > 0 ? (
              <p className="text-[var(--warning)]">
                {t("settings.legacySessionsRetained", { count: inventory.legacySessionOrigins })}
              </p>
            ) : null}
            {inventory.protectedDirectoryPaths.length > 0 ? (
              <p className="text-[var(--kq-color-muted)]">
                {t("settings.legacyDirectoriesRetained", { count: inventory.protectedDirectoryPaths.length })}
              </p>
            ) : null}
          </>
        )}

        {exported ? (
          <div className="kq-banner kq-banner--success rounded-[var(--radius-shell-lg)] p-3">
            <p>{t("settings.legacyExportReady", { count: exported.exportedFiles })}</p>
            <p className="mt-1 break-all font-mono text-[0.7rem]">{exported.path}</p>
            {exported.skippedOversizeFiles.length > 0 ? (
              <p className="mt-1 text-rose-700 dark:text-rose-300">
                {t("settings.legacyExportSkipped", { count: exported.skippedOversizeFiles.length })}
              </p>
            ) : null}
          </div>
        ) : null}
        {cleanup ? (
          <p role="status" className="text-[var(--success)]">
            {t("settings.legacyCleanupDone", {
              count: cleanup.removedEnvKeys + cleanup.removedFiles + cleanup.removedConfigPlatforms + cleanup.removedChannelPlatforms,
            })}
          </p>
        ) : null}
        {error ? <p role="alert" className="text-rose-700 dark:text-rose-400">{error}</p> : null}

        <div className="flex flex-wrap gap-2">
          <Button type="button" size="sm" variant="secondary" disabled={busy} onClick={() => void refresh()}>
            <RefreshCw className="mr-1 size-3.5" />{t("settings.legacyRefresh")}
          </Button>
          <Button type="button" size="sm" variant="secondary" disabled={busy || !hasHistory} onClick={() => void exportLegacy()}>
            <ArchiveRestore className="mr-1 size-3.5" />{t("settings.legacyExportAction")}
          </Button>
          <Button
            type="button"
            size="sm"
            variant="ghost"
            disabled={busy || !exported || exported.skippedOversizeFiles.length > 0 || !inventory?.totalCleanupItems}
            onClick={() => void cleanupLegacy()}
          >
            <Trash2 className="mr-1 size-3.5" />{t("settings.legacyCleanupAction")}
          </Button>
        </div>
        <p className="leading-relaxed text-[var(--kq-color-muted)]">{t("settings.legacyCleanupBoundary")}</p>
      </div>
    </Section>
  );
}
