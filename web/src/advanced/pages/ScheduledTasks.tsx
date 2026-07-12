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
  mode: string | null;
  goalStatus: string | null;
  goalIteration: number | null;
  goalCostUsd: string | null;
  goalCostAccounting: string | null;
  goalPauseReason: string | null;
  goalUpdatedAt: string | null;
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

type GoalNotice = { tone: "success" | "error"; message: string };

function goalPauseReasonLabel(reason: string, t: (key: string) => string): string {
  const keys: Record<string, string> = {
    user_paused: "cron.goalPauseReasonUser",
    feature_disabled: "cron.goalPauseReasonFeatureDisabled",
    cost_unknown: "cron.goalPauseReasonCostUnknown",
    max_runs: "cron.goalPauseReasonMaxRuns",
    max_cost_usd: "cron.goalPauseReasonMaxCost",
    max_wall_seconds: "cron.goalPauseReasonMaxWall",
    deadline: "cron.goalPauseReasonDeadline",
    no_progress: "cron.goalPauseReasonNoProgress",
    ambiguous_external_effect: "cron.goalPauseReasonAmbiguousEffect",
    worker_blocked: "cron.goalPauseReasonWorkerBlocked",
    verifier_error: "cron.goalPauseReasonVerifierError",
    invalid_artifact: "cron.goalPauseReasonInvalidArtifact",
    missing_report: "cron.goalPauseReasonMissingReport",
    recovery_review: "cron.goalPauseReasonRecoveryReview",
  };
  return t(keys[reason] ?? "cron.goalPauseReasonOther");
}

function goalErrorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
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
  const [workspace, setWorkspace] = useState<string | null>(null);
  const [goalBusy, setGoalBusy] = useState(false);
  const [goalNotice, setGoalNotice] = useState<GoalNotice | null>(null);

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

  useEffect(() => {
    void invoke<string>("cmd_workspace_path")
      .then(setWorkspace)
      .catch(() => setWorkspace(null));
  }, []);

  const handleCreateGoalPilot = async () => {
    if (!workspace) {
      setGoalNotice({ tone: "error", message: t("cron.goalWorkspaceUnavailable") });
      return;
    }
    const ok = await confirm({
      title: t("cron.goalCreateTitle"),
      message: t("cron.goalCreateAsk", { workspace }),
      confirmLabel: t("cron.goalCreate"),
      cancelLabel: t("dialog.cancel"),
      tone: "warning",
    });
    if (!ok) return;
    setGoalBusy(true);
    setGoalNotice(null);
    try {
      await invoke("cmd_goal_create");
      setGoalNotice({ tone: "success", message: t("cron.goalCreateSuccess") });
      await fetchJobs();
    } catch (e) {
      setGoalNotice({
        tone: "error",
        message: t("cron.goalControlError", { message: goalErrorMessage(e) }),
      });
    } finally {
      setGoalBusy(false);
    }
  };

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

  // Goal Task controls route to the dedicated cmd_goal_* commands, which proxy
  // to the crash-safe core control service. Legacy cmd_cron_toggle/delete
  // reject goal jobs, so they are never used here.
  const handleGoalControl = async (
    job: CronJobEntry,
    action: "pause" | "resume" | "cancel" | "delete",
  ) => {
    if (action === "pause") {
      const ok = await confirm({
        title: t("cron.goalPauseTitle"),
        message: t("cron.goalPauseAsk", { name: job.name || job.id }),
        confirmLabel: t("cron.goalPause"),
        cancelLabel: t("dialog.cancel"),
        tone: "warning",
      });
      if (!ok) return;
    } else if (action === "resume") {
      const ok = await confirm({
        title: t("cron.goalResumeTitle"),
        message: t("cron.goalResumeAsk", { name: job.name || job.id }),
        confirmLabel: t("cron.goalResume"),
        cancelLabel: t("dialog.cancel"),
        tone: "warning",
      });
      if (!ok) return;
    } else if (action === "cancel") {
      const ok = await confirm({
        title: t("cron.goalCancelTitle"),
        message: t("cron.goalCancelAsk", { name: job.name || job.id }),
        confirmLabel: t("cron.goalCancel"),
        cancelLabel: t("dialog.cancel"),
        tone: "danger",
      });
      if (!ok) return;
    } else if (action === "delete") {
      const ok = await confirm({
        title: t("cron.goalDeleteTitle"),
        message: t("cron.goalDeleteAsk", { name: job.name || job.id }),
        confirmLabel: t("dialog.delete"),
        cancelLabel: t("dialog.cancel"),
        tone: "danger",
      });
      if (!ok) return;
    }
    setGoalBusy(true);
    setGoalNotice(null);
    try {
      await invoke(`cmd_goal_${action}`, { jobId: job.id });
      setGoalNotice({ tone: "success", message: t("cron.goalControlSuccess") });
      await fetchJobs();
    } catch (e) {
      console.error(`cmd_goal_${action} failed:`, e);
      setGoalNotice({
        tone: "error",
        message: t("cron.goalControlError", { message: goalErrorMessage(e) }),
      });
    } finally {
      setGoalBusy(false);
    }
  };

  const renderGoalCard = (job: CronJobEntry) => {
    const cost = job.goalCostAccounting === "incomplete"
      ? t("cron.goalCostUnknown")
      : job.goalCostUsd
        ? `$${job.goalCostUsd}`
        : t("cron.goalCostUnavailable");
    return (
      <div
        key={job.id}
        className="hd-glass-subtle px-5 py-4 dark:border-[var(--kq-color-border)] dark:bg-[var(--kq-glass-bg)]"
      >
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-sm font-semibold text-[var(--kq-color-strong)] truncate">
              {job.name || job.id.slice(0, 8)}
            </h3>
            <span className="rounded-full bg-violet-100 px-2 py-0.5 text-[11px] font-medium text-violet-700 dark:bg-violet-900/30 dark:text-violet-300">
              {t("cron.goalBadge")}
            </span>
            <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-700 dark:bg-slate-800 dark:text-slate-300">
              {job.goalStatus || t("cron.goalStateError")}
            </span>
          </div>
          <div className="mt-2 grid gap-1 text-xs text-[var(--kq-color-muted)] sm:grid-cols-2">
            <p>
              <span className="font-medium">{t("cron.goalIteration")}:</span>{" "}
              {job.goalIteration ?? "—"}
            </p>
            <p>
              <span className="font-medium">{t("cron.goalCost")}:</span>{" "}
              {cost}
            </p>
            {job.goalUpdatedAt && (
              <p>
                <span className="font-medium">{t("cron.goalUpdatedAt")}:</span>{" "}
                {formatCronDateTime(job.goalUpdatedAt, locale)}
              </p>
            )}
            {job.goalPauseReason && (
              <p>
                <span className="font-medium">{t("cron.goalPauseReason")}:</span>{" "}
                {goalPauseReasonLabel(job.goalPauseReason, t)}
              </p>
            )}
          </div>
          {(() => {
            const status = job.goalStatus || "";
            const isActive = ["scheduled", "running", "verifying"].includes(status);
            const isPaused = status === "paused";
            const isTerminal = ["completed", "failed", "cancelled"].includes(status);
            if (!isActive && !isPaused && !isTerminal) return null;
            return (
              <div className="mt-3 flex flex-wrap gap-2">
                {isActive && (
                  <Button variant="ghost" size="sm" disabled={goalBusy} onClick={() => handleGoalControl(job, "pause")}>
                    {t("cron.goalPause")}
                  </Button>
                )}
                {isPaused && (
                  <Button variant="ghost" size="sm" disabled={goalBusy} onClick={() => handleGoalControl(job, "resume")}>
                    {t("cron.goalResume")}
                  </Button>
                )}
                {(isActive || isPaused) && (
                  <Button variant="ghost" size="sm" disabled={goalBusy} onClick={() => handleGoalControl(job, "cancel")}>
                    {t("cron.goalCancel")}
                  </Button>
                )}
                {isTerminal && (
                  <Button variant="ghost" size="sm" disabled={goalBusy} onClick={() => handleGoalControl(job, "delete")}>
                    {t("cron.delete")}
                  </Button>
                )}
              </div>
            );
          })()}
        </div>
      </div>
    );
  };

  const renderActiveCard = (job: CronJobEntry) => {
    if (job.mode === "goal") return renderGoalCard(job);
    return (
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
  };

  const renderCompletedCard = (job: CronJobEntry) => {
    if (job.mode === "goal") return renderGoalCard(job);
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

        <section className="hd-setting-card space-y-3 px-5 py-4" aria-labelledby="goal-pilot-title">
          <div>
            <h2 id="goal-pilot-title" className="text-sm font-semibold text-[var(--kq-color-strong)]">
              {t("cron.goalPilotTitle")}
            </h2>
            <p className="mt-1 text-xs leading-relaxed text-[var(--kq-color-muted)]">
              {t("cron.goalPilotLead")}
            </p>
          </div>
          <dl className="grid gap-2 text-xs text-[var(--kq-color-muted)] sm:grid-cols-2">
            <div>
              <dt className="font-medium text-[var(--kq-color-strong)]">{t("cron.goalWorkspace")}</dt>
              <dd className="mt-0.5 break-all">{workspace || t("cron.goalWorkspaceLoading")}</dd>
            </div>
            <div>
              <dt className="font-medium text-[var(--kq-color-strong)]">{t("cron.goalCadence")}</dt>
              <dd className="mt-0.5">{t("cron.goalCadenceValue")}</dd>
            </div>
            <div>
              <dt className="font-medium text-[var(--kq-color-strong)]">{t("cron.goalBoundary")}</dt>
              <dd className="mt-0.5">{t("cron.goalBoundaryValue")}</dd>
            </div>
            <div>
              <dt className="font-medium text-[var(--kq-color-strong)]">{t("cron.goalLimits")}</dt>
              <dd className="mt-0.5">{t("cron.goalLimitsValue")}</dd>
            </div>
          </dl>
          <p className="text-xs leading-relaxed text-[var(--kq-color-muted)]">{t("cron.goalHostOnly")}</p>
          <Button size="sm" disabled={!workspace || goalBusy} onClick={() => void handleCreateGoalPilot()}>
            {goalBusy ? t("cron.goalWorking") : t("cron.goalCreate")}
          </Button>
        </section>

        {goalNotice && (
          <p
            role={goalNotice.tone === "error" ? "alert" : "status"}
            className={`rounded-[var(--radius-shell-lg)] border px-3.5 py-2.5 text-xs leading-relaxed ${
              goalNotice.tone === "error"
                ? "border-rose-300 bg-rose-50 text-rose-800 dark:border-rose-900/70 dark:bg-rose-950/30 dark:text-rose-200"
                : "border-emerald-300 bg-emerald-50 text-emerald-800 dark:border-emerald-900/70 dark:bg-emerald-950/30 dark:text-emerald-200"
            }`}
          >
            {goalNotice.message}
          </p>
        )}

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
