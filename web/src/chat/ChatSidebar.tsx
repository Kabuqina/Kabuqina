// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import {
  AlarmClock,
  Download,
  FileText,
  FolderKanban,
  FolderOpen,
  Image as ImageIcon,
  type LucideIcon,
  MessageCircle,
  PanelLeft,
  Plus,
  Trash2,
} from "lucide-react";
import { useI18n } from "../lib/i18n";
import type { SessionRow } from "./chat-api";
import { cn } from "../lib/cn";
import { REMINDER_SESSION_ID } from "./reminderSession";
import { deriveSessionPresentation, type SessionIcon } from "./sessionPresentation";

export interface ChatSidebarProps {
  sessions: SessionRow[];
  activeSessionId: string | null;
  loading?: boolean;
  collapsed?: boolean;
  onToggleCollapsed: () => void;
  onNewChat: () => void;
  onOpenScheduledTasks: () => void;
  onOpenWorkspace: () => void;
  onOrganizeDesktop: () => void;
  onExport: () => void;
  onSelectSession: (id: string) => void;
  onDeleteSession: (id: string, e: React.MouseEvent) => void;
}

function SidebarCommonActionButton({
  icon: Icon,
  iconClassName,
  label,
  collapsed,
  onClick,
}: {
  icon: LucideIcon;
  iconClassName: string;
  label: string;
  collapsed: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={label}
      aria-label={label}
      className={cn(
        "kq-sidebar-session group flex w-full min-w-0 items-center py-2.5 text-left transition hover:brightness-[1.03]",
        collapsed ? "justify-center px-0" : "gap-2 px-2.5",
      )}
    >
      <Icon className={cn("h-4 w-4 shrink-0", iconClassName)} strokeWidth={2.2} aria-hidden />
      {!collapsed && (
        <span className="kq-sidebar-session-label truncate text-[var(--kq-color-ink)]/78 group-hover:text-[var(--kq-color-ink)]">
          {label}
        </span>
      )}
    </button>
  );
}

function formatSessionTime(ts: number | undefined, locale: "zh" | "en"): string {
  if (!ts) return "";
  const d = new Date(ts > 1e12 ? ts : ts * 1000);
  const now = new Date();
  const isToday =
    d.getFullYear() === now.getFullYear() &&
    d.getMonth() === now.getMonth() &&
    d.getDate() === now.getDate();
  if (isToday) {
    return d.toLocaleTimeString(locale === "en" ? "en-US" : "zh-CN", {
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    });
  }
  const yesterday = new Date(now);
  yesterday.setDate(now.getDate() - 1);
  const isYesterday =
    d.getFullYear() === yesterday.getFullYear() &&
    d.getMonth() === yesterday.getMonth() &&
    d.getDate() === yesterday.getDate();
  if (isYesterday) return locale === "en" ? "Yest" : "昨天";
  const daysDiff = Math.floor((now.getTime() - d.getTime()) / 86400000);
  if (daysDiff < 7) {
    return d.toLocaleDateString(locale === "en" ? "en-US" : "zh-CN", { weekday: "short" });
  }
  return d.toLocaleDateString(locale === "en" ? "en-US" : "zh-CN", {
    month: "numeric",
    day: "numeric",
  });
}

export function ChatSidebar({
  sessions,
  activeSessionId,
  loading = false,
  collapsed = false,
  onToggleCollapsed,
  onNewChat,
  onOpenScheduledTasks,
  onOpenWorkspace,
  onOrganizeDesktop,
  onExport,
  onSelectSession,
  onDeleteSession,
}: ChatSidebarProps) {
  const { t, locale } = useI18n();
  const grouped = sessions.reduce<Array<{ group: string; rows: Array<{ session: SessionRow; label: string; icon: SessionIcon }> }>>(
    (acc, session) => {
      const presentation = deriveSessionPresentation(session, locale);
      let bucket = acc.find((item) => item.group === presentation.group);
      if (!bucket) {
        bucket = { group: presentation.group, rows: [] };
        acc.push(bucket);
      }
      bucket.rows.push({ session, label: presentation.label, icon: presentation.icon });
      return acc;
    },
    [],
  );
  const iconFor = (icon: SessionIcon) =>
    icon === "alarm" ? AlarmClock : icon === "file" ? FileText : icon === "image" ? ImageIcon : MessageCircle;

  return (
    <aside
      className={cn(
        "kq-sidebar flex shrink-0 flex-col border-r transition-[width] duration-200 ease-out",
        collapsed ? "w-14" : "w-56",
      )}
    >
      <div className={cn(
        "flex items-center gap-2 border-b border-[var(--kq-glass-border)] p-2.5",
        collapsed && "justify-center",
      )}>
        {!collapsed && (
          <button
            type="button"
            onClick={() => onNewChat()}
            className="kq-new-chat inline-flex min-w-0 flex-1 items-center justify-start gap-2 px-3 py-2.5 text-[15px] font-bold leading-snug transition hover:brightness-[1.03] active:scale-[0.99]"
          >
            <span className="truncate">{t("chat.newChat")}</span>
            <Plus className="h-4 w-4 shrink-0 stroke-[2.75]" aria-hidden />
          </button>
        )}
        <button
          type="button"
          onClick={onToggleCollapsed}
          className="kq-soft-icon-btn inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg transition"
          aria-label={collapsed ? t("chat.leftRailExpand") : t("chat.leftRailCollapse")}
          title={collapsed ? t("chat.leftRailExpand") : t("chat.leftRailCollapse")}
        >
          <PanelLeft className="h-4 w-4" />
        </button>
      </div>
      <div className={cn("kq-sidebar-history-scroll min-h-0 flex-1 space-y-0.5 overflow-y-auto pb-4 pt-2", collapsed ? "px-2" : "px-3")}>
        {loading && (
          <p className={cn("kq-sidebar-meta px-1.5 py-2", collapsed && "text-center")}>
            {collapsed ? "..." : t("chat.loadingSessions")}
          </p>
        )}
        {!loading && sessions.length === 0 && (
          !collapsed ? (
            <p className="kq-sidebar-meta px-1.5 py-2 text-center">
              {t("chat.noSessions")}
            </p>
          ) : null
        )}
        {grouped.map((group, groupIndex) => (
          <div
            key={group.group}
            className={cn("kq-sidebar-group pt-1", groupIndex > 0 && "kq-sidebar-group-divided")}
          >
            {!collapsed && (
              <p className="kq-sidebar-group-label px-1.5 pb-1 pt-2">
                {group.group}
              </p>
            )}
            {group.rows.map(({ session: s, label, icon }) => {
              const active = s.id === activeSessionId;
              const Icon = iconFor(icon);
              const timeStr = !collapsed ? formatSessionTime(s.last_active ?? s.started_at, locale) : "";
              return (
                <div
                  key={s.id}
                  className={cn(
                    "kq-sidebar-session group relative flex items-stretch overflow-hidden",
                    active && "kq-sidebar-session-active",
                  )}
                >
                  {/* Active indicator bar */}
                  {active && (
                    <div
                      className="absolute left-0 top-1.5 bottom-1.5 w-[3px] rounded-full"
                      style={{ background: "linear-gradient(180deg, var(--kq-color-primary-dark), var(--kq-color-primary))" }}
                    />
                  )}
                  <button
                    type="button"
                    onClick={() => onSelectSession(s.id)}
                    title={label}
                    aria-label={label}
                    className={cn(
                      "flex min-w-0 flex-1 items-center gap-2.5 py-2 text-left",
                      collapsed ? "justify-center px-0" : "px-2.5",
                      active && "pl-3",
                    )}
                  >
                    <Icon
                      className={cn(
                        "h-[15px] w-[15px] shrink-0",
                        s.id === REMINDER_SESSION_ID
                          ? "kq-color-icon-alarm"
                          : active
                            ? "text-[var(--kq-color-strong)]"
                            : "text-[var(--kq-color-muted)]",
                      )}
                      strokeWidth={2}
                      aria-hidden
                    />
                    {!collapsed && (
                      <div
                        className={cn(
                          "kq-sidebar-session-label min-w-0 flex-1 truncate",
                          active
                            ? "font-semibold text-[var(--kq-color-strong)]"
                            : "text-[var(--kq-color-ink)]/85 group-hover:text-[var(--kq-color-ink)]",
                        )}
                        style={{ fontSize: "0.8125rem", lineHeight: 1.4, letterSpacing: "0.01em" }}
                      >
                        {label}
                      </div>
                    )}
                  </button>
                  {!collapsed && (
                    <div className="kq-sidebar-trailing-slot">
                      <span className="kq-sidebar-session-time group-hover:opacity-0">
                        {timeStr}
                      </span>
                      <div className="kq-sidebar-delete-overlay group-hover:opacity-100">
                        <button
                          type="button"
                          title={t("chat.delete")}
                          onClick={(e) => onDeleteSession(s.id, e)}
                          className="kq-sidebar-delete rounded-md p-1 transition hover:bg-red-500/10"
                        >
                          <Trash2 className="h-3 w-3" strokeWidth={2.5} />
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        ))}
      </div>
      <div className={cn("kq-sidebar-common-actions shrink-0 border-t border-[var(--kq-glass-border)] py-1.5", collapsed ? "px-2" : "px-2")}>
        <SidebarCommonActionButton
          onClick={onOpenWorkspace}
          icon={FolderOpen}
          iconClassName="kq-color-icon-folder"
          label={t("chat.workspaceOpenWorkspace")}
          collapsed={collapsed}
        />
        <SidebarCommonActionButton
          onClick={onOpenScheduledTasks}
          icon={AlarmClock}
          iconClassName="kq-color-icon-alarm"
          label={t("cron.title")}
          collapsed={collapsed}
        />
        <SidebarCommonActionButton
          onClick={onOrganizeDesktop}
          icon={FolderKanban}
          iconClassName="kq-color-icon-pen"
          label={t("chat.workspaceOrganizeDesktop")}
          collapsed={collapsed}
        />
        <SidebarCommonActionButton
          onClick={onExport}
          icon={Download}
          iconClassName="kq-color-icon-download"
          label={t("chat.exportButton")}
          collapsed={collapsed}
        />
      </div>
    </aside>
  );
}
