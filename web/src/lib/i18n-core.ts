// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { MESSAGES } from "../locales/strings";

export type Locale = "zh" | "en";

const STORAGE_KEY = "kabuqina.locale";
const LEGACY_STORAGE_KEY = "hermesdesk.locale";

export function getLocale(): Locale {
  if (typeof window === "undefined" || !window.localStorage) return "zh";
  const value = window.localStorage.getItem(STORAGE_KEY) ?? window.localStorage.getItem(LEGACY_STORAGE_KEY);
  if (value) window.localStorage.setItem(STORAGE_KEY, value);
  return value === "en" ? "en" : "zh";
}

export function setStoredLocale(locale: Locale): void {
  if (typeof window === "undefined" || !window.localStorage) return;
  window.localStorage.setItem(STORAGE_KEY, locale);
}

export function applyDocumentLang(locale: Locale): void {
  if (typeof document === "undefined") return;
  document.documentElement.lang = locale === "zh" ? "zh-CN" : "en";
}

function getNested(obj: unknown, path: string): string | undefined {
  const parts = path.split(".");
  let cur: unknown = obj;
  for (const p of parts) {
    if (cur == null || typeof cur !== "object") return undefined;
    cur = (cur as Record<string, unknown>)[p];
  }
  return typeof cur === "string" ? cur : undefined;
}

/**
 * Dot-path lookup in `MESSAGES[locale]`, fallback to zh, then path string.
 * Optional `{{key}}` interpolation from `params`.
 */
export function translate(
  path: string,
  locale?: Locale,
  params?: Record<string, string | number>
): string {
  const loc = locale ?? getLocale();
  const primary = MESSAGES[loc] as unknown as Record<string, unknown>;
  const fallback = MESSAGES.zh as unknown as Record<string, unknown>;
  let s = getNested(primary, path) ?? getNested(fallback, path) ?? path;
  if (params) {
    s = s.replace(/\{\{(\w+)\}\}/g, (_, k: string) =>
      params[k] !== undefined ? String(params[k]) : `{{${k}}}`
    );
  }
  return s;
}
