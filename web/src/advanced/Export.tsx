// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { invoke } from "@tauri-apps/api/core";
import { save } from "@tauri-apps/plugin-dialog";
import { AppScaffold } from "../components/AppScaffold";
import { BackButton } from "../components/ui/BackButton";
import { useI18n } from "../lib/i18n";
import {
  buildExportHtml,
  buildExportJson,
  buildExportMarkdown,
  buildExportText,
  defaultExportFilename,
  type ExportFormat,
  exportLabelsForLocale,
} from "../chat/chatExport";
import { HIGHLIGHT_CSS, renderChatMarkdownToHtml } from "../chat/chatExportHtml";
import {
  cmdGetSessionMessages,
  cmdGetSessions,
  type MessageRow,
  type SessionRow,
} from "../chat/chat-api";

export function Export() {
  const { t, locale } = useI18n();
  const nav = useNavigate();

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
      const labels = exportLabelsForLocale(locale);

      const entries = await Promise.all(
        selectedIds.map(async (id) => {
          try {
            const r = await cmdGetSessionMessages(id);
            return { session_id: id, messages: r.messages ?? ([] as MessageRow[]) };
          } catch {
            return { session_id: id, messages: [] as MessageRow[] };
          }
        }),
      );

      const msgsBySession = new Map(entries.map((e) => [e.session_id, e.messages]));

      let content: string;
      let defaultName: string;
      let filters: { name: string; extensions: string[] }[];

      const isPdf = format === "pdf";

      if (format === "json") {
        content = buildExportJson(sortedSessions, msgsBySession, labels, locale);
        defaultName = defaultExportFilename("json");
        filters = [{ name: "JSON", extensions: ["json"] }];
      } else if (format === "markdown") {
        content = buildExportMarkdown(sortedSessions, msgsBySession, labels, locale);
        defaultName = defaultExportFilename("markdown");
        filters = [{ name: "Markdown", extensions: ["md"] }];
      } else if (format === "text") {
        content = buildExportText(sortedSessions, msgsBySession, labels, locale);
        defaultName = defaultExportFilename("text");
        filters = [{ name: "Text", extensions: ["txt"] }];
      } else {
        content = buildExportHtml(sortedSessions, msgsBySession, labels, locale, {
          renderMarkdown: renderChatMarkdownToHtml,
          extraCss: HIGHLIGHT_CSS,
        });
        defaultName = defaultExportFilename("pdf");
        filters = [{ name: "PDF", extensions: ["pdf"] }];
      }

      const filePath = await save({
        title: t("export.exportBtn"),
        defaultPath: defaultName,
        filters,
      });
      if (!filePath) {
        setExporting(false);
        return;
      }

      if (isPdf) {
        await invoke("cmd_write_pdf_from_html", {
          pathStr: filePath,
          html: content,
        });
      } else {
        await invoke("cmd_write_text_file", {
          pathStr: filePath,
          content,
        });
      }
    } catch (e) {
      console.error(e);
    } finally {
      setExporting(false);
    }
  }, [selected, format, sessions, locale, t]);

  return (
    <AppScaffold surface="chat" className="flex h-full min-h-0 flex-col">
      <div className="hd-topbar sticky top-0 z-20 flex h-12 shrink-0 items-center gap-2 border-b px-2 sm:px-3">
        <BackButton onClick={() => nav("/chat")} className="-ml-1">
          {t("export.back")}
        </BackButton>
        <span className="text-sm font-semibold text-[var(--kq-color-strong)]">{t("export.title")}</span>
      </div>
      <div className="mx-auto flex min-h-0 w-full max-w-2xl flex-1 flex-col px-[var(--hd-page-pad-x)]">
        <div className="shrink-0 space-y-4 pt-7 sm:pt-8">
        <p className="max-w-xl text-sm leading-relaxed text-[var(--kq-color-muted)]">
          {t("export.lead")}
        </p>

        <div className="hd-setting-card p-4">
          <label className="block text-sm font-medium text-[var(--kq-color-strong)]">
            {t("export.formatLabel")}
          </label>
          <div className="mt-2 flex gap-3">
            {(["json", "markdown", "text", "pdf"] as ExportFormat[]).map((f) => (
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
                <span className="text-[var(--kq-color-ink)]">
                  {f === "json"
                    ? "JSON"
                    : f === "markdown"
                      ? "Markdown"
                      : f === "text"
                        ? "TXT"
                        : "PDF"}
                </span>
              </label>
            ))}
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={selectAll}
            className="text-sm text-[var(--kq-color-strong)] hover:text-[var(--kq-color-ink)] dark:text-[var(--kq-color-primary-light)] dark:hover:text-[var(--kq-color-primary-light)]"
          >
            {t("export.selectAll")}
          </button>
          <button
            type="button"
            onClick={deselectAll}
            className="text-sm text-[var(--kq-color-muted)] transition hover:text-[var(--kq-color-strong)]"
          >
            {t("export.deselectAll")}
          </button>
          <span className="ml-auto text-xs text-[var(--kq-color-muted)]">
            {t("export.selected", { count: selected.size })}
          </span>
        </div>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto py-3">
        {loading && (
          <p className="text-sm text-[var(--kq-color-muted)] py-8 text-center">
            {t("export.loading")}
          </p>
        )}

        {!loading && sessions.length === 0 && (
          <p className="text-sm text-[var(--kq-color-muted)] py-8 text-center">
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
                  className="flex items-center gap-3 rounded-lg px-3 py-2.5 cursor-pointer transition hover:bg-[var(--kq-hover-bg)]"
                >
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={() => toggleSession(s.id)}
                    className="accent-[var(--kq-color-primary)] shrink-0"
                  />
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-sm text-[var(--kq-color-strong)]">
                      {label}
                    </div>
                    <div className="mt-0.5 flex gap-3 text-xs text-[var(--kq-color-muted)]">
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
        </div>

        <div className="shrink-0 border-t border-[var(--kq-color-border)] py-4">
          <button
            type="button"
            disabled={selected.size === 0 || exporting}
            onClick={handleExport}
            className="kq-btn-primary inline-flex w-full items-center justify-center gap-2 rounded-lg px-5 py-2.5 text-sm font-bold active:scale-[0.99] disabled:cursor-not-allowed disabled:opacity-50"
          >
            {exporting ? "…" : t("export.exportBtn")}
          </button>
        </div>
      </div>
    </AppScaffold>
  );
}
