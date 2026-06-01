// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useCallback, useEffect, useState } from "react";
import { Download, Package, RefreshCw, Trash2 } from "lucide-react";
import { confirm } from "../../lib/confirmDialog";
import { useI18n } from "../../lib/i18n";
import { Section } from "../../components/ui/Section";
import { Button } from "../../components/ui/Button";
import { StatusBanner } from "../../components/ui/StatusBanner";
import {
  cmdLoadPackageDelete,
  cmdLoadPackageDownload,
  cmdLoadPackages,
  type LoadPackageStatus,
} from "../../chat/chat-api";

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}

function packageTitle(pkg: LoadPackageStatus, t: (path: string) => string): string {
  const key = `settings.loadPackage.${pkg.id}.title`;
  const value = t(key);
  return value === key ? pkg.title : value;
}

function packageDescription(pkg: LoadPackageStatus, t: (path: string) => string): string {
  const key = `settings.loadPackage.${pkg.id}.desc`;
  const value = t(key);
  return value === key ? pkg.description : value;
}

function loadPackageError(e: unknown, t: (path: string, vars?: Record<string, string>) => string): string {
  const msg = String(e);
  if (msg.includes("desktop_bridge_unavailable")) {
    return t("settings.loadPackagesDesktopOnly");
  }
  return msg;
}

export function SettingsLoadPackages() {
  const { t } = useI18n();
  const [packages, setPackages] = useState<LoadPackageStatus[]>([]);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const next = await cmdLoadPackages();
      setPackages(next.packages);
    } catch (e) {
      setError(loadPackageError(e, t));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const handleDownload = useCallback(async (pkg: LoadPackageStatus) => {
    setBusyId(pkg.id);
    setError(null);
    try {
      await cmdLoadPackageDownload(pkg.id);
      await refresh();
    } catch (e) {
      setError(t("settings.loadPackageDownloadFailed", { msg: loadPackageError(e, t) }));
    } finally {
      setBusyId(null);
    }
  }, [refresh, t]);

  const handleDelete = useCallback(async (pkg: LoadPackageStatus) => {
    const title = packageTitle(pkg, t);
    const ok = await confirm({
      title: t("settings.loadPackageDeleteTitle", { name: title }),
      message: t("settings.loadPackageDeleteAsk", { name: title }),
      confirmLabel: t("dialog.delete"),
      cancelLabel: t("dialog.cancel"),
      tone: "warning",
    });
    if (!ok) return;

    setBusyId(pkg.id);
    setError(null);
    try {
      await cmdLoadPackageDelete(pkg.id);
      await refresh();
    } catch (e) {
      setError(t("settings.loadPackageDeleteFailed", { msg: loadPackageError(e, t) }));
    } finally {
      setBusyId(null);
    }
  }, [refresh, t]);

  return (
    <Section
      icon={Package}
      title={t("settings.loadPackagesTitle")}
      desc={t("settings.loadPackagesDesc")}
    >
      <div className="space-y-3 text-sm text-[var(--kq-color-ink)] dark:text-zinc-300">
        {loading ? (
          <p className="text-[var(--kq-color-muted)] dark:text-zinc-400">{t("settings.loadPackagesChecking")}</p>
        ) : (
          <div className="space-y-3">
            {packages.map((pkg) => {
              const installed = pkg.downloaded;
              const busy = busyId === pkg.id;
              return (
                <div
                  key={pkg.id}
                  className="rounded-[var(--radius-shell-lg)] border border-[var(--kq-color-border)] bg-white/55 p-4 dark:border-zinc-800 dark:bg-zinc-900/45"
                >
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5">
                        <h3 className="text-sm font-semibold text-[var(--kq-color-strong)] dark:text-zinc-100">
                          {packageTitle(pkg, t)}
                        </h3>
                        <span className="inline-flex items-center gap-1.5 text-xs text-[var(--kq-color-muted)] dark:text-zinc-400">
                          <span
                            className={`inline-block h-2 w-2 rounded-full ${
                              installed ? "bg-emerald-500" : "bg-zinc-300 dark:bg-zinc-600"
                            }`}
                          />
                          {installed ? t("settings.loadPackageInstalled") : t("settings.loadPackageNotInstalled")}
                        </span>
                      </div>
                      <p className="mt-1 text-sm leading-relaxed text-[var(--kq-color-muted)] dark:text-zinc-400">
                        {packageDescription(pkg, t)}
                      </p>
                      <p className="mt-2 break-all text-xs text-[var(--kq-color-muted)] dark:text-zinc-500">
                        {installed
                          ? t("settings.loadPackageSize", { size: formatBytes(pkg.size) })
                          : t("settings.loadPackageExpectedSize", { size: String(pkg.sizeMb) })}
                      </p>
                    </div>

                    <div className="flex shrink-0 flex-wrap gap-2">
                      <Button size="sm" onClick={() => void handleDownload(pkg)} disabled={!!busyId}>
                        {installed ? <RefreshCw className="h-3.5 w-3.5" /> : <Download className="h-3.5 w-3.5" />}
                        {busy ? t("settings.loadPackageWorking") : installed ? t("settings.loadPackageRedownload") : t("settings.loadPackageDownload")}
                      </Button>
                      {installed ? (
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => void handleDelete(pkg)}
                          disabled={!!busyId}
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                          {t("settings.loadPackageDelete")}
                        </Button>
                      ) : null}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {error ? <StatusBanner variant="error" title={error} /> : null}
      </div>
    </Section>
  );
}
