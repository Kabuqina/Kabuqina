// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useEffect, useRef, useState } from "react";
import { listen } from "@tauri-apps/api/event";
import { Bell, MessageCircle, X } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { createDesktopDeliveryNotice, type DesktopDeliveryMessage, type DesktopDeliveryNotice } from "../lib/desktopDelivery";
import { CHAT_OPEN_REMINDER_SESSION_STATE } from "../lib/chatLocationState";
import { useI18n } from "../lib/i18n";

const EVENT_NAME = "desktop-delivery";
const MAX_VISIBLE_NOTICES = 3;
const AUTO_DISMISS_MS = 45000;

export function DesktopDeliveryNotifier() {
  const { t } = useI18n();
  const nav = useNavigate();
  const [notices, setNotices] = useState<DesktopDeliveryNotice[]>([]);
  const sequenceRef = useRef(0);

  useEffect(() => {
    const timeouts: number[] = [];
    const unlisten = listen<DesktopDeliveryMessage>(EVENT_NAME, ({ payload }) => {
      const notice = createDesktopDeliveryNotice(
        payload,
        Date.now() + sequenceRef.current++,
        t("cron.toastFallbackTitle"),
      );
      setNotices((prev) => [...prev, notice].slice(-MAX_VISIBLE_NOTICES));
      const timeout = window.setTimeout(() => {
        setNotices((prev) => prev.filter((item) => item.id !== notice.id));
      }, AUTO_DISMISS_MS);
      timeouts.push(timeout);
    });

    return () => {
      unlisten.then((fn) => fn());
      timeouts.forEach((timeout) => window.clearTimeout(timeout));
    };
  }, [t]);

  if (notices.length === 0) return null;

  const openChat = (id: string) => {
    setNotices((prev) => prev.filter((item) => item.id !== id));
    nav("/chat", { state: CHAT_OPEN_REMINDER_SESSION_STATE });
  };

  return (
    <div className="pointer-events-none fixed bottom-5 right-5 z-50 flex w-[min(24rem,calc(100vw-2rem))] flex-col gap-2">
      {notices.map((notice) => (
        <div
          key={notice.id}
          className="pointer-events-auto rounded-[var(--radius-shell-lg)] border border-[var(--kq-color-primary-pale)] bg-white p-3 shadow-xl shadow-violet-950/15 ring-1 ring-[var(--kq-color-primary-pale)] dark:border-[#D4C5E2]/40 dark:bg-zinc-900 dark:shadow-black/40 dark:ring-[#D4C5E2]/20"
          role="status"
        >
          <div className="flex items-start gap-3">
            <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[var(--kq-color-primary-pale)] text-[var(--kq-color-strong)] dark:bg-[#D4C5E2]/15 dark:text-[#D4C5E2]">
              <Bell size={16} aria-hidden="true" />
            </div>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-semibold text-zinc-900 dark:text-zinc-100">
                {notice.title}
              </p>
              {notice.preview && (
                <p className="mt-1 line-clamp-2 text-xs leading-5 text-zinc-500 dark:text-zinc-400">
                  {notice.preview}
                </p>
              )}
              <button
                type="button"
                className="mt-2 inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-xs font-medium text-[var(--kq-color-strong)] transition hover:bg-[var(--kq-color-primary-pale)] dark:text-[#D4C5E2] dark:hover:bg-[#D4C5E2]/15"
                onClick={() => openChat(notice.id)}
              >
                <MessageCircle size={14} aria-hidden="true" />
                {t("cron.toastOpen")}
              </button>
            </div>
            <button
              type="button"
              className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md text-zinc-400 transition hover:bg-zinc-100 hover:text-zinc-700 dark:hover:bg-zinc-800 dark:hover:text-zinc-200"
              onClick={() => setNotices((prev) => prev.filter((item) => item.id !== notice.id))}
              aria-label={t("cron.toastClose")}
            >
              <X size={15} aria-hidden="true" />
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}
