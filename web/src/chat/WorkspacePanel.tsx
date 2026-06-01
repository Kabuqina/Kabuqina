// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { AlarmClock, CheckCircle2, Download, FileText, FolderKanban, PanelRightClose, Wrench } from "lucide-react";
import type { ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { useI18n } from "../lib/i18n";
import { cn } from "../lib/cn";

export type WorkspaceItem = {
  id: string;
  label: string;
  detail?: string;
};

export type WorkspaceActivity = {
  id: string;
  label: string;
  detail?: string;
  running?: boolean;
};

type WorkspacePanelProps = {
  className?: string;
  onCollapse: () => void;
  onOrganizeDesktop?: () => void;
  goal?: string | null;
  materials: WorkspaceItem[];
  outputs: WorkspaceItem[];
  activeTool?: string | null;
  activity: WorkspaceActivity[];
};

function WorkspaceSectionHeading({ children }: { children: ReactNode }) {
  return (
    <h3 className="workspace-section-heading kq-section-heading inline-flex px-3 py-1.5 text-sm font-semibold leading-snug tracking-normal dark:border-l-[#9b87b8] dark:bg-zinc-800/40 dark:text-zinc-200">
      {children}
    </h3>
  );
}

function WorkspaceSection({
  sectionId,
  title,
  body,
  children,
}: {
  sectionId: string;
  title: string;
  body: string;
  children?: ReactNode;
}) {
  return (
    <section
      data-workspace-section={sectionId}
      className="kq-workspace-card dark:border-zinc-800 dark:bg-zinc-900/60"
    >
      <WorkspaceSectionHeading>{title}</WorkspaceSectionHeading>
      {children ?? (
        <p className="kq-workspace-body mt-3 dark:text-zinc-300">
          {body}
        </p>
      )}
    </section>
  );
}

function WorkspaceItemList({
  items,
  icon,
}: {
  items: WorkspaceItem[];
  icon: "file" | "output";
}) {
  const Icon = icon === "output" ? CheckCircle2 : FileText;
  return (
    <ul className="mt-3 space-y-2">
      {items.map((item) => (
        <li key={item.id} className="min-w-0">
          <div className="flex min-w-0 items-start gap-2">
            <Icon className="mt-0.5 h-4 w-4 shrink-0 text-zinc-500 dark:text-zinc-400" aria-hidden />
            <div className="min-w-0">
              <div className="truncate text-sm font-medium text-zinc-800 dark:text-zinc-100" title={item.label}>
                {item.label}
              </div>
              {item.detail ? (
                <div className="mt-0.5 truncate text-[13px] leading-snug text-zinc-600 dark:text-zinc-400" title={item.detail}>
                  {item.detail}
                </div>
              ) : null}
            </div>
          </div>
        </li>
      ))}
    </ul>
  );
}

export function WorkspacePanel({
  className,
  onCollapse,
  onOrganizeDesktop,
  goal,
  materials,
  outputs,
  activeTool,
  activity,
}: WorkspacePanelProps) {
  const { t } = useI18n();
  const nav = useNavigate();

  return (
    <aside
      className={cn(
        "kq-workspace-panel flex w-64 shrink-0 flex-col border-l dark:border-zinc-700 dark:bg-zinc-950/40",
        className,
      )}
    >
      <div className="flex h-14 items-center justify-between border-b border-[#e8e0ed]/80 px-4 dark:border-zinc-800">
        <h2 className="text-base font-semibold tracking-normal text-[var(--kq-color-strong)] dark:text-zinc-100">
          {t("chat.workspaceTitle")}
        </h2>
        <button
          type="button"
          onClick={onCollapse}
          className="kq-soft-icon-btn inline-flex h-8 w-8 items-center justify-center rounded-md transition dark:hover:bg-zinc-800 dark:hover:text-zinc-100"
          aria-label={t("chat.workspaceCollapse")}
          title={t("chat.workspaceCollapse")}
        >
          <PanelRightClose className="h-4 w-4" aria-hidden />
        </button>
      </div>

      <div className="min-h-0 flex-1 space-y-4 overflow-y-auto px-4 py-4">
        <section data-workspace-section="workspace.quickActions">
          <WorkspaceSectionHeading>{t("chat.workspaceQuickActions")}</WorkspaceSectionHeading>
          <div className="mt-3 grid gap-2">
            <button
              type="button"
              onClick={() => nav("/settings/cron", { state: { cronBackTo: "/chat" } })}
              className="kq-quick-action justify-start rounded-lg px-3 py-2.5 text-left text-[15px] leading-snug transition"
            >
              <AlarmClock className="kq-color-icon-alarm mr-2 inline h-4 w-4" aria-hidden />
              {t("cron.title")}
            </button>
            <button
              type="button"
              onClick={onOrganizeDesktop}
              className="kq-quick-action justify-start rounded-lg px-3 py-2.5 text-left text-[15px] leading-snug transition"
            >
              <FolderKanban className="kq-color-icon-folder mr-2 inline h-4 w-4" aria-hidden />
              {t("chat.workspaceOrganizeDesktop")}
            </button>
            <button
              type="button"
              onClick={() => nav("/export")}
              className="kq-quick-action justify-start rounded-lg px-3 py-2.5 text-left text-[15px] leading-snug transition"
            >
              <Download className="kq-color-icon-download mr-2 inline h-4 w-4" aria-hidden />
              {t("chat.exportButton")}
            </button>
          </div>
        </section>

        <WorkspaceSection
          sectionId="workspace.currentGoal"
          title={t("chat.workspaceCurrentGoal")}
          body={t("chat.workspaceGoalEmpty")}
        >
          {goal || activeTool || activity.length ? (
            <div className="mt-3 space-y-3">
              {goal ? (
                <p className="kq-workspace-body dark:text-zinc-200">{goal}</p>
              ) : null}
              {activeTool ? (
                <div className="flex min-w-0 items-center gap-2 text-[13px] leading-snug text-zinc-700 dark:text-zinc-300">
                  <Wrench className="h-3.5 w-3.5 shrink-0 text-sky-600 dark:text-sky-400" aria-hidden />
                  <span className="truncate">{activeTool.replace(/_/g, " ")}</span>
                </div>
              ) : null}
              {activity.length ? (
                <ul className="space-y-1.5">
                  {activity.map((item) => (
                    <li key={item.id} className="min-w-0 text-[13px] leading-snug text-zinc-600 dark:text-zinc-400">
                      <span
                        className={cn(
                          "mr-1 inline-block h-1.5 w-1.5 rounded-full align-middle",
                          item.running ? "bg-amber-500 dark:bg-amber-300" : "bg-emerald-500 dark:bg-emerald-400",
                        )}
                        aria-hidden
                      />
                      <span className="font-medium text-zinc-600 dark:text-zinc-300">{item.label.replace(/_/g, " ")}</span>
                      {item.detail ? <span className="ml-1">{item.detail}</span> : null}
                    </li>
                  ))}
                </ul>
              ) : null}
            </div>
          ) : undefined}
        </WorkspaceSection>
        <WorkspaceSection
          sectionId="workspace.materials"
          title={t("chat.workspaceMaterials")}
          body={t("chat.workspaceMaterialsEmpty")}
        >
          {materials.length ? <WorkspaceItemList items={materials} icon="file" /> : undefined}
        </WorkspaceSection>
        <WorkspaceSection
          sectionId="workspace.outputs"
          title={t("chat.workspaceOutputs")}
          body={t("chat.workspaceOutputsEmpty")}
        >
          {outputs.length ? <WorkspaceItemList items={outputs} icon="output" /> : undefined}
        </WorkspaceSection>
      </div>
    </aside>
  );
}
