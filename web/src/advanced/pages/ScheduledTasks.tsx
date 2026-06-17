// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useEffect, useState, useCallback } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import { confirm } from "../../lib/confirmDialog";
import { AppScaffold } from "../../components/AppScaffold";
import { BackButton } from "../../components/ui/BackButton";
import { Button } from "../../components/ui/Button";
import { Toggle } from "../../components/ui/Toggle";
import { formatCronDateTime, formatCronSchedule } from "../../lib/formatCronTime";
import { useI18n } from "../../lib/i18n";

interface CronJobEntry {
  id: string;
  name: string;
  schedule: string;
  prompt: string;
  deliver: string;
  paused: boolean;
  nextRunAt: string | null;
  lastRunAt: string | null;
  state: string;
  completedAt: string | null;
  lastStatus: string | null;
  lastDeliveryError: string | null;
}

function formatDeliverLabel(deliver: string, t: (key: string) => string): string {
  const raw = (deliver || "local").trim().toLowerCase();
  if (!raw || raw === "local" || raw === "desktop") {
    return t("cron.deliverDesktop");
  }
  return deliver || t("cron.deliverDesktop");
}

interface CronJobListResponse {
  jobs: CronJobEntry[];
  completed: CronJobEntry[];
  hasAny: boolean;
}

function cronBackTarget(state: unknown): string | null {
  if (typeof state !== "object" || state === null) return null;
  const raw = (state as { cronBackTo?: unknown }).cronBackTo;
  return typeof raw === "string" && raw ? raw : null;
}

export function ScheduledTasksPage() {
  const nav = useNavigate();
  const location = useLocation();
  const { t, locale } = useI18n();
  const cronBackTo = cronBackTarget(location.state);
  const backPath = cronBackTo === "/chat" ? "/chat" : "/settings";
  const backLabel = cronBackTo === "/chat" ? t("onboarding.backToChat") : t("settings.backToSettings");
  const [jobs, setJobs] = useState<CronJobEntry[]>([]);
  const [completed, setCompleted] = useState<CronJobEntry[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchJobs = useCallback(async () => {
    try {
      const res = await invoke<CronJobListResponse>("cmd_cron_list");
      setJobs(res.jobs || []);
      setCompleted(res.completed || []);
    } catch (e) {
      console.error("cmd_cron_list failed:", e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchJobs();
    const refresh = window.setInterval(() => {
      void fetchJobs();
    }, 5000);
    const unlisten = listen("desktop-delivery", () => {
      void fetchJobs();
    });
    return () => {
      window.clearInterval(refresh);
      unlisten.then((fn) => fn());
    };
  }, [fetchJobs]);

  const handleToggle = async (jobId: string, currentPaused: boolean) => {
    try {
      await invoke("cmd_cron_toggle", { jobId });
      setJobs((prev) =>
        prev.map((j) =>
          j.id === jobId ? { ...j, paused: !currentPaused } : j,
        ),
      );
    } catch (e) {
      console.error("cmd_cron_toggle failed:", e);
    }
  };

  const handleDelete = async (jobId: string, jobName: string, fromCompleted: boolean) => {
    const ok = await confirm({
      title: t("cron.deleteTitle"),
      message: t("cron.deleteAsk", { name: jobName }),
      confirmLabel: t("dialog.delete"),
      cancelLabel: t("dialog.cancel"),
      tone: "danger",
    });
    if (!ok) return;
    try {
      await invoke("cmd_cron_delete", { jobId });
      if (fromCompleted) {
        setCompleted((prev) => prev.filter((j) => j.id !== jobId));
      } else {
        setJobs((prev) => prev.filter((j) => j.id !== jobId));
      }
    } catch (e) {
      console.error("cmd_cron_delete failed:", e);
    }
  };

  const renderActiveCard = (job: CronJobEntry) => (
    <div
      key={job.id}
      className="hd-glass-subtle px-5 py-4 dark:border-[var(--kq-color-border)] dark:bg-[var(--kq-glass-bg)]"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-semibold text-[var(--kq-color-strong)] truncate">
              {job.name || job.id.slice(0, 8)}
            </h3>
            {job.paused && (
              <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[11px] font-medium text-amber-700 dark:bg-amber-900/30 dark:text-amber-400">
                {t("cron.paused")}
              </span>
            )}
          </div>
          <p className="mt-1 text-xs text-[var(--kq-color-muted)]">
            <span className="font-medium">{t("cron.schedule")}:</span>{" "}
            {formatCronSchedule(job.schedule, locale)}
          </p>
          {job.prompt && (
            <p className="mt-0.5 text-xs text-[var(--kq-color-muted)] truncate">
              {job.prompt.slice(0, 120)}
            </p>
          )}
          <p className="mt-0.5 text-xs text-[var(--kq-color-muted)]">
            <span className="font-medium">{t("cron.deliver")}:</span>{" "}
            {formatDeliverLabel(job.deliver, t)}
          </p>
          {job.lastDeliveryError && (
            <p className="mt-0.5 text-xs text-rose-600 dark:text-rose-400">
              <span className="font-medium">{t("cron.deliveryError")}:</span>{" "}
              {job.lastDeliveryError}
            </p>
          )}
          {job.nextRunAt && (
            <p className="mt-0.5 text-xs text-[var(--kq-color-muted)]">
              <span className="font-medium">{t("cron.nextRun")}:</span>{" "}
              {formatCronDateTime(job.nextRunAt, locale)}
            </p>
          )}
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <Toggle
            value={!job.paused}
            onChange={() => handleToggle(job.id, job.paused)}
            aria-label={t("cron.toggleLabel")}
          />
          <Button
            variant="ghost"
            size="sm"
            onClick={() => handleDelete(job.id, job.name || job.id, false)}
          >
            {t("cron.delete")}
          </Button>
        </div>
      </div>
    </div>
  );

  const renderCompletedCard = (job: CronJobEntry) => {
    const failed = job.lastStatus === "error";
    return (
      <div
        key={job.id}
        className="hd-glass-subtle px-5 py-4 dark:border-[var(--kq-color-border)] dark:bg-[var(--kq-glass-bg)]"
      >
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <h3 className="text-sm font-semibold text-[var(--kq-color-ink)] truncate">
                {job.name || job.id.slice(0, 8)}
              </h3>
              {failed && (
                <span className="rounded-full bg-rose-100 px-2 py-0.5 text-[11px] font-medium text-rose-700 dark:bg-rose-900/30 dark:text-rose-400">
                  {t("cron.completedFailed")}
                </span>
              )}
            </div>
            {job.prompt && (
              <p className="mt-1 text-xs text-[var(--kq-color-muted)] truncate">
                {job.prompt.slice(0, 120)}
              </p>
            )}
            {job.completedAt && (
              <p className="mt-0.5 text-xs text-[var(--kq-color-muted)]">
                <span className="font-medium">{t("cron.completedAt")}:</span>{" "}
                {formatCronDateTime(job.completedAt, locale)}
              </p>
            )}
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => handleDelete(job.id, job.name || job.id, true)}
          >
            {t("cron.delete")}
          </Button>
        </div>
      </div>
    );
  };

  return (
    <AppScaffold surface="chat" className="flex h-full min-h-0 flex-col">
      <div className="hd-topbar sticky top-0 z-20 flex h-12 shrink-0 items-center gap-2 border-b px-2 sm:px-3">
        <BackButton onClick={() => nav(backPath)} className="-ml-1">{backLabel}</BackButton>
        <span className="text-sm font-semibold text-[var(--kq-color-strong)]">{t("cron.title")}</span>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto">
      <div className="mx-auto max-w-2xl space-y-5 px-[var(--hd-page-pad-x)] py-7 sm:py-9">
        <div>
          <p className="max-w-xl text-sm leading-relaxed text-[var(--kq-color-muted)]">
            {t("cron.lead")}
          </p>
          <p className="mt-3 max-w-xl rounded-[var(--radius-shell-lg)] border border-[var(--kq-color-border)] bg-[var(--kq-color-primary-pale)]/40 px-3.5 py-2.5 text-xs leading-relaxed text-[var(--kq-color-ink)]">
            <span className="font-medium text-[var(--kq-color-strong)]">{t("cron.tipLabel")}</span>
            <span className="mx-1 text-[var(--kq-color-muted)]" aria-hidden>
              ·
            </span>
            {t("cron.createTip")}
          </p>
        </div>

        {loading ? (
          <p className="text-sm text-[var(--kq-color-muted)]">{t("cron.loading")}</p>
        ) : jobs.length === 0 && completed.length === 0 ? (
          <div className="hd-setting-card px-5 py-8 text-center">
            <p className="text-sm text-[var(--kq-color-muted)]">{t("cron.empty")}</p>
            <p className="mt-1 text-xs text-[var(--kq-color-muted)]">{t("cron.emptyHint")}</p>
          </div>
        ) : (
          <>
            {jobs.length > 0 && (
              <div>
                <h2 className="mb-2 text-xs font-medium uppercase tracking-wide text-[var(--kq-color-muted)]">
                  {t("cron.activeSection")}
                </h2>
                <div className="space-y-3">{jobs.map(renderActiveCard)}</div>
              </div>
            )}
            {completed.length > 0 && (
              <div>
                <h2 className="mb-2 text-xs font-medium uppercase tracking-wide text-[var(--kq-color-muted)]">
                  {t("cron.completedSection")}
                </h2>
                <p className="mb-2 text-xs text-[var(--kq-color-muted)]">{t("cron.completedHint")}</p>
                <div className="space-y-3">{completed.map(renderCompletedCard)}</div>
              </div>
            )}
          </>
        )}
      </div>
      </div>
    </AppScaffold>
  );
}
