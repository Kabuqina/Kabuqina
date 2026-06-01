// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import type { Locale } from "./i18n-core";

const ISO_PREFIX = /^\d{4}-\d{2}-\d{2}[T ]/;

function parseIso(value: string): Date | null {
  const trimmed = value.trim();
  if (!trimmed) return null;
  const ms = Date.parse(trimmed);
  if (!Number.isFinite(ms)) return null;
  return new Date(ms);
}

function startOfLocalDay(d: Date): number {
  const x = new Date(d);
  x.setHours(0, 0, 0, 0);
  return x.getTime();
}

function formatTimeOnly(d: Date, locale: Locale): string {
  const loc = locale === "en" ? "en-US" : "zh-CN";
  return d.toLocaleString(loc, {
    hour: "2-digit",
    minute: "2-digit",
    hour12: locale === "en",
  });
}

function formatDateTime(d: Date, locale: Locale, includeYear: boolean): string {
  const loc = locale === "en" ? "en-US" : "zh-CN";
  return d.toLocaleString(loc, {
    ...(includeYear ? { year: "numeric" as const } : {}),
    month: locale === "zh" ? "numeric" : "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: locale === "en",
  });
}

/** True when the value looks like an ISO-8601 timestamp (e.g. one-shot schedule). */
export function isIsoDateTime(value: string): boolean {
  return ISO_PREFIX.test(value.trim());
}

/** Compact display for cron next-run / completed timestamps. */
export function formatCronDateTime(value: string | null | undefined, locale: Locale): string {
  if (!value?.trim()) return "";
  const parsed = parseIso(value);
  if (!parsed) {
    return value.replace(/\.\d+(?=[Z+-])/, "").replace(/([+-]\d{2}):(\d{2})$/, "$1$2");
  }

  const now = new Date();
  const today = startOfLocalDay(now);
  const targetDay = startOfLocalDay(parsed);
  const dayMs = 86_400_000;
  const time = formatTimeOnly(parsed, locale);

  if (targetDay === today) {
    return locale === "zh" ? `今天 ${time}` : `Today, ${time}`;
  }
  if (targetDay === today + dayMs) {
    return locale === "zh" ? `明天 ${time}` : `Tomorrow, ${time}`;
  }
  if (targetDay === today - dayMs) {
    return locale === "zh" ? `昨天 ${time}` : `Yesterday, ${time}`;
  }

  const sameYear = parsed.getFullYear() === now.getFullYear();
  return formatDateTime(parsed, locale, !sameYear);
}

/** Human-readable schedule; ISO one-shot values become short local datetimes. */
export function formatCronSchedule(schedule: string, locale: Locale): string {
  const raw = schedule.trim();
  if (!raw) return raw;
  if (!isIsoDateTime(raw)) return raw;
  return formatCronDateTime(raw, locale);
}
