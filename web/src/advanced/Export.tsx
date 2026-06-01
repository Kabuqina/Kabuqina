// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { invoke } from "@tauri-apps/api/core";
import { save } from "@tauri-apps/plugin-dialog";
import { ArrowDown, ArrowUp } from "lucide-react";
import { AppScaffold } from "../components/AppScaffold";
import { BackButton } from "../components/ui/BackButton";
import { useI18n } from "../lib/i18n";
import {
  cmdGetSessionMessages,
  cmdGetSessions,
  type MessageRow,
  type SessionRow,
} from "../chat/chat-api";

type ExportFormat = "json" | "markdown";

function contentToText(content: unknown): string {
  if (content == null) return "";
  if (typeof content === "string") return content;
  if (Array.isArray(content)) {
    return content
      .map((c) => {
        if (typeof c === "string") return c;
        if (c && typeof c === "object" && "text" in c)
          return String((c as { text?: unknown }).text ?? "");
        return "";
      })
      .filter(Boolean)
      .join("\n");
  }
  if (typeof content === "object" && "text" in (content as object)) {
    return String((content as { text?: unknown }).text);
  }
  try {
    return JSON.stringify(content);
  } catch {
    return String(content);
  }
}

function tsToLocale(ts?: number): string {
  if (ts == null) return "";
  const ms = ts > 1e12 ? ts : ts * 1000;
  return new Date(ms).toLocaleString();
}

/** Format a single session's messages as a timeline-style Markdown document. */
function sessionToMarkdown(session: SessionRow, messages: MessageRow[]): string {
  const title = session.title || session.id.slice(0, 8);
  const lines: string[] = [];
  lines.push(`# 💬 ${title}`);
  lines.push("");
  lines.push(
    `> **Session:** \`${session.id}\`  ` +
    `| **Model:** ${session.model || "—"}  ` +
    `| **Messages:** ${messages.length}`,
  );
  lines.push("");

  for (const m of messages) {
    const role = m.role;
    if (role === "session_meta" || role === "tool") continue;
    if (role !== "user" && role !== "assistant" && role !== "system") continue;

    const text = contentToText(m.content).trim();
    if (!text) continue;

    const timeLabel = tsToLocale(m.timestamp);
    const tsStr = timeLabel ? ` · ${timeLabel}` : "";

    if (role === "user") {
      // User messages: compact blockquote style with a timestamp marker
      lines.push(`> 🧑 ${tsStr}`);
      lines.push(">");
      for (const line of text.split("\n")) {
        lines.push(`> ${line}`);
      }
      lines.push(">");
      lines.push("");
    } else {
      // Assistant messages: heading style with full text
      const badge = role === "system" ? "⚙️ System" : "🤖 Hermes";
      lines.push(`### ${badge} ${tsStr}`);
      lines.push("");
      lines.push(text);
      lines.push("");
    }
  }

  lines.push("---");
  lines.push("");
  return lines.join("\n");
}

/**
 * Build the full Markdown document containing all selected sessions.
 * Sessions are separated by a page-break marker.
 */
function buildMarkdown(sessions: SessionRow[], messagesBySession: Map<string, MessageRow[]>): string {
  const parts: string[] = [];
  for (const s of sessions) {
    const msgs = messagesBySession.get(s.id) ?? [];
    if (msgs.length === 0) continue;
    parts.push(sessionToMarkdown(s, msgs));
  }
  return parts.join("\n\n<div style=\"page-break-after: always;\"></div>\n\n");
}

export function Export() {
  const { t } = useI18n();
  const nav = useNavigate();
  const scrollRef = useRef<HTMLDivElement>(null);

  const [sessions, setSessions] = useState<SessionRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [format, setFormat] = useState<ExportFormat>("json");
  const [exporting, setExporting] = useState(false);
  const fetchedRef = useRef(false);

  useEffect(() => {
    if (fetchedRef.current) return;
    fetchedRef.current = true;
    (async () => {
      try {
        const r = await cmdGetSessions(500, 0, "hermesdesk");
        setSessions(r.sessions ?? []);
      } catch (e) {
        console.error(e);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const toggleSession = useCallback((id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }, []);

  const selectAll = useCallback(() => {
    setSelected(new Set(sessions.map((s) => s.id)));
  }, [sessions]);

  const deselectAll = useCallback(() => {
    setSelected(new Set());
  }, []);

  const handleExport = useCallback(async () => {
    if (selected.size === 0) return;
    setExporting(true);

    try {
      const selectedIds = [...selected];
      const sortedSessions = sessions.filter((s) => selectedIds.includes(s.id));

      // Fetch all selected session messages in parallel
      const entries = await Promise.all(
        selectedIds.map(async (id) => {
          try {
            const r = await cmdGetSessionMessages(id);
            return { session_id: id, messages: r.messages ?? [] as MessageRow[] };
          } catch {
            return { session_id: id, messages: [] as MessageRow[] };
          }
        }),
      );

      // Build file content
      let content: string;
      let defaultName: string;
      let filters: { name: string; extensions: string[] }[];

      if (format === "json") {
        content = JSON.stringify(entries, null, 2);
        defaultName = `hermesdesk-export.json`;
        filters = [{ name: "JSON", extensions: ["json"] }];
      } else {
        const msgsBySession = new Map(entries.map((e) => [e.session_id, e.messages]));
        content = buildMarkdown(sortedSessions, msgsBySession);
        defaultName = `hermesdesk-export.md`;
        filters = [{ name: "Markdown", extensions: ["md"] }];
      }

      // Use the native save dialog
      const filePath = await save({
        title: t("export.exportBtn"),
        defaultPath: defaultName,
        filters,
      });
      if (!filePath) {
        setExporting(false);
        return; // user cancelled
      }

      await invoke("cmd_write_text_file", {
        pathStr: filePath,
        content,
      });
    } catch (e) {
      console.error(e);
    } finally {
      setExporting(false);
    }
  }, [selected, format, sessions, t]);

  return (
    <AppScaffold className="h-full overflow-y-auto" ref={scrollRef}>
      <div className="mx-auto max-w-2xl space-y-5 px-[var(--hd-page-pad-x)] py-8 sm:py-10">
        <div>
          <BackButton onClick={() => nav("/chat")}>
            {t("export.back")}
          </BackButton>
          <h1 className="hd-page-title">{t("export.title")}</h1>
          <p className="mt-1.5 max-w-xl text-sm leading-relaxed text-zinc-500 dark:text-zinc-400">
            {t("export.lead")}
          </p>
        </div>

        {/* Format selector */}
        <div className="rounded-[var(--radius-shell-lg)] border border-zinc-200/90 bg-white/70 p-4 dark:border-zinc-700 dark:bg-zinc-800/60">
          <label className="block text-sm font-medium text-zinc-800 dark:text-zinc-200">
            {t("export.formatLabel")}
          </label>
          <div className="mt-2 flex gap-3">
            {(["json", "markdown"] as ExportFormat[]).map((f) => (
              <label
                key={f}
                className="inline-flex items-center gap-2 text-sm cursor-pointer"
              >
                <input
                  type="radio"
                  name="exportFormat"
                  value={f}
                  checked={format === f}
                  onChange={() => setFormat(f)}
                  className="accent-[var(--kq-color-primary)]"
                />
                <span className="text-zinc-700 dark:text-zinc-300">
                  {f === "json" ? "JSON" : "Markdown"}
                </span>
              </label>
            ))}
          </div>
        </div>

        {/* Select controls */}
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={selectAll}
            className="text-sm text-[var(--kq-color-strong)] hover:text-[var(--kq-color-ink)] dark:text-[#D4C5E2] dark:hover:text-[#D4C5E2]"
          >
            {t("export.selectAll")}
          </button>
          <button
            type="button"
            onClick={deselectAll}
            className="text-sm text-zinc-500 hover:text-zinc-700 dark:text-zinc-400 dark:hover:text-zinc-300"
          >
            {t("export.deselectAll")}
          </button>
          <span className="ml-auto text-xs text-zinc-400 dark:text-zinc-500">
            {t("export.selected", { count: selected.size })}
          </span>
        </div>

        {/* Session list */}
        {loading && (
          <p className="text-sm text-zinc-400 dark:text-zinc-500 py-8 text-center">
            {t("export.loading")}
          </p>
        )}

        {!loading && sessions.length === 0 && (
          <p className="text-sm text-zinc-400 dark:text-zinc-500 py-8 text-center">
            {t("export.noSessions")}
          </p>
        )}

        {!loading && sessions.length > 0 && (
          <div className="space-y-1">
            {sessions.map((s) => {
              const label =
                (s.title && s.title.trim()) || s.preview || s.id.slice(0, 8);
              const checked = selected.has(s.id);
              return (
                <label
                  key={s.id}
                  className="flex items-center gap-3 rounded-lg px-3 py-2.5 cursor-pointer transition hover:bg-zinc-100/70 dark:hover:bg-zinc-800/70"
                >
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={() => toggleSession(s.id)}
                    className="accent-[var(--kq-color-primary)] shrink-0"
                  />
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-sm text-zinc-800 dark:text-zinc-200">
                      {label}
                    </div>
                    <div className="mt-0.5 flex gap-3 text-xs text-zinc-400 dark:text-zinc-500">
                      <span>{s.id.slice(0, 12)}</span>
                      {s.model && <span>{s.model}</span>}
                      {s.message_count != null && (
                        <span>{s.message_count} msgs</span>
                      )}
                    </div>
                  </div>
                </label>
              );
            })}
          </div>
        )}

        {/* Export button */}
        <div className="pt-4">
          <button
            type="button"
            disabled={selected.size === 0 || exporting}
            onClick={handleExport}
            className="kq-btn-primary inline-flex items-center gap-2 rounded-lg px-5 py-2.5 text-sm font-bold active:scale-[0.99] disabled:cursor-not-allowed disabled:opacity-50"
          >
            {exporting ? "…" : t("export.exportBtn")}
          </button>
        </div>
      </div>

      {/* Floating scroll buttons */}
      <div className="pointer-events-none fixed bottom-6 right-6 z-50 flex flex-col gap-2">
        <button
          type="button"
          onClick={() => scrollRef.current?.scrollTo({ top: 0, behavior: "smooth" })}
          className="pointer-events-auto flex h-10 w-10 items-center justify-center rounded-full border border-[var(--kq-color-border)] bg-white/90 text-[var(--kq-color-muted)] shadow-[var(--kq-shadow-card)] backdrop-blur transition hover:bg-white hover:text-[var(--kq-color-strong)] dark:bg-zinc-800/90 dark:text-zinc-300 dark:hover:bg-zinc-800 dark:hover:text-zinc-100"
          aria-label={t("settings.scrollTop")}
          title={t("settings.scrollTop")}
        >
          <ArrowUp className="h-5 w-5" />
        </button>
        <button
          type="button"
          onClick={() =>
            scrollRef.current?.scrollTo({
              top: scrollRef.current.scrollHeight,
              behavior: "smooth",
            })
          }
          className="pointer-events-auto flex h-10 w-10 items-center justify-center rounded-full border border-[var(--kq-color-border)] bg-white/90 text-[var(--kq-color-muted)] shadow-[var(--kq-shadow-card)] backdrop-blur transition hover:bg-white hover:text-[var(--kq-color-strong)] dark:bg-zinc-800/90 dark:text-zinc-300 dark:hover:bg-zinc-800 dark:hover:text-zinc-100"
          aria-label={t("settings.scrollBottom")}
          title={t("settings.scrollBottom")}
        >
          <ArrowDown className="h-5 w-5" />
        </button>
      </div>
    </AppScaffold>
  );
}
