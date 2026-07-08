// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Download, RefreshCw, Trash2 } from "lucide-react";
import { AppScaffold } from "../../components/AppScaffold";
import { BackButton } from "../../components/ui/BackButton";
import { Button } from "../../components/ui/Button";
import { StatusBanner } from "../../components/ui/StatusBanner";
import { confirm } from "../../lib/confirmDialog";
import { useI18n } from "../../lib/i18n";
import {
  cmdLoadPackageDelete,
  cmdLoadPackageDownload,
  cmdLoadPackages,
  type LoadPackageStatus,
} from "../../chat/chat-api";
import {
  activeLoadPackageDownloads,
  formatBytes,
  loadPackageError,
  packageDescription,
  packageTitle,
} from "../settings/loadPackageUi";

function phaseLabel(phase: string | undefined, t: (path: string) => string): string {
  if (!phase) return "";
  const key = `settings.loadPackagePhase.${phase}`;
  const value = t(key);
  return value === key ? phase : value;
}

function ProgressBar({ pkg }: { pkg: LoadPackageStatus }) {
  const { t } = useI18n();
  const job = pkg.job;
  if (!job) return null;
  if (job.status !== "running" && job.status !== "error") return null;
  const total = job.totalBytes || pkg.sizeMb * 1024 * 1024;
  const downloaded = job.downloadedBytes || 0;
  const percent = job.percent ?? (total ? Math.floor(downloaded * 100 / total) : 0);
  return (
    <div className="mt-3 space-y-1.5">
      <div className="h-2 overflow-hidden rounded-full bg-[var(--kq-hover-bg-strong)]">
        <div
          className="h-full rounded-full bg-[var(--kq-color-primary)] transition-[width]"
          style={{ width: `${Math.max(4, Math.min(100, percent))}%` }}
        />
      </div>
      <div className="flex flex-wrap justify-between gap-2 text-xs text-[var(--kq-color-muted)] dark:text-[var(--kq-color-muted)]">
        <span>
          {t("settings.loadPackageProgress", {
            phase: phaseLabel(job.phase, t),
            percent: String(percent),
          })}
        </span>
        <span>
          {formatBytes(downloaded)} / {formatBytes(total)}
        </span>
      </div>
      {job.source ? (
        <p className="text-xs text-[var(--kq-color-muted)] dark:text-[var(--kq-color-muted)]">
          {t("settings.loadPackageSource", { source: job.source })}
        </p>
      ) : null}
      {job.status === "error" && job.error ? <StatusBanner variant="error" title={job.error} /> : null}
    </div>
  );
}
export function LoadPackagesPage() {
  const { t } = useI18n();
  const nav = useNavigate();
  const [packages, setPackages] = useState<LoadPackageStatus[]>([]);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async (options: { quiet?: boolean } = {}) => {
    if (!options.quiet) setLoading(true);
    try {
      const next = await cmdLoadPackages();
      setPackages(next.packages);
      setError(null);
    } catch (e) {
      setError(loadPackageError(e, t));
    } finally {
      if (!options.quiet) setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const running = useMemo(() => activeLoadPackageDownloads(packages), [packages]);
  useEffect(() => {
    if (running.length === 0) return;
    const timer = window.setInterval(() => {
      void refresh({ quiet: true });
    }, 1000);
    return () => window.clearInterval(timer);
  }, [refresh, running.length]);

  const handleDownload = useCallback(async (pkg: LoadPackageStatus) => {
    setBusyId(pkg.id);
    setError(null);
    try {
      const updated = await cmdLoadPackageDownload(pkg.id);
      setPackages((prev) => prev.map((item) => (item.id === updated.id ? updated : item)));
      void refresh({ quiet: true });
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
      await refresh({ quiet: true });
    } catch (e) {
      setError(t("settings.loadPackageDeleteFailed", { msg: loadPackageError(e, t) }));
    } finally {
      setBusyId(null);
    }
  }, [refresh, t]);

  return (
    <AppScaffold surface="chat" className="flex h-full min-h-0 flex-col">
      <div className="hd-topbar sticky top-0 z-20 flex h-12 shrink-0 items-center gap-2 border-b px-2 sm:px-3">
        <BackButton onClick={() => nav("/settings")} className="-ml-1">{t("settings.back")}</BackButton>
        <span className="text-sm font-semibold text-[var(--kq-color-strong)]">{t("settings.loadPackagesTitle")}</span>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto">
      <div className="mx-auto max-w-3xl space-y-5 px-[var(--hd-page-pad-x)] py-7 sm:py-9">
        <p className="max-w-2xl text-sm leading-relaxed text-[var(--kq-color-muted)]">
          {t("settings.loadPackagesPageLead")}
        </p>

        {loading ? (
          <p className="text-sm text-[var(--kq-color-muted)] dark:text-[var(--kq-color-muted)]">{t("settings.loadPackagesChecking")}</p>
        ) : (
          <div className="space-y-3">
            {packages.map((pkg) => {
              const installed = pkg.downloaded;
              const busy = busyId === pkg.id;
              const runningJob = pkg.job?.status === "running";
              return (
                <div
                  key={pkg.id}
                  className="hd-setting-card p-4"
                >
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5">
                        <h2 className="text-sm font-semibold text-[var(--kq-color-strong)] dark:text-[var(--kq-color-strong)]">
                          {packageTitle(pkg, t)}
                        </h2>
                        <span className="inline-flex items-center gap-1.5 text-xs text-[var(--kq-color-muted)] dark:text-[var(--kq-color-muted)]">
                          <span className={`inline-block h-2 w-2 rounded-full ${installed ? "bg-emerald-500" : runningJob ? "bg-sky-500" : "bg-[var(--kq-color-primary)]/35"}`} />
                          {runningJob ? phaseLabel(pkg.job?.phase, t) : installed ? t("settings.loadPackageInstalled") : t("settings.loadPackageNotInstalled")}
                        </span>
                      </div>
                      <p className="mt-1 text-sm leading-relaxed text-[var(--kq-color-muted)] dark:text-[var(--kq-color-muted)]">
                        {packageDescription(pkg, t)}
                      </p>
                      <p className="mt-2 break-all text-xs text-[var(--kq-color-muted)] dark:text-[var(--kq-color-muted)]">
                        {installed
                          ? t("settings.loadPackageSize", { size: formatBytes(pkg.size) })
                          : t("settings.loadPackageExpectedSize", { size: String(pkg.sizeMb) })}
                      </p>
                      {pkg.usedByCapabilities?.length ? (
                        <p className="mt-1 text-xs text-[var(--kq-color-muted)] dark:text-[var(--kq-color-muted)]">
                          {t("settings.loadPackageUsedBy", {
                            names: pkg.usedByCapabilities.map((item) => item.title || item.id).join("、"),
                          })}
                        </p>
                      ) : null}
                    </div>

                    <div className="flex shrink-0 flex-wrap gap-2">
                      <Button size="sm" onClick={() => void handleDownload(pkg)} disabled={!!busyId || runningJob}>
                        {installed ? <RefreshCw className="h-3.5 w-3.5" /> : <Download className="h-3.5 w-3.5" />}
                        {busy || runningJob
                          ? t("settings.loadPackageWorking")
                          : installed
                            ? t("settings.loadPackageRedownload")
                            : t("settings.loadPackageDownload")}
                      </Button>
                      {installed ? (
                        <Button size="sm" variant="ghost" onClick={() => void handleDelete(pkg)} disabled={!!busyId || runningJob}>
                          <Trash2 className="h-3.5 w-3.5" />
                          {t("settings.loadPackageDelete")}
                        </Button>
                      ) : null}
                    </div>
                  </div>
                  <ProgressBar pkg={pkg} />
                </div>
              );
            })}
          </div>
        )}

        {error ? <StatusBanner variant="error" title={error} /> : null}
      </div>
      </div>
    </AppScaffold>
  );
}
