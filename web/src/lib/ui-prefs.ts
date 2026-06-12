// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useCallback, useEffect, useState } from "react";

/**
 * UI preferences persisted in localStorage (shell webview).
 * Root `font-size` scales `rem` used by Tailwind text utilities.
 */

const FONT_SIZE_KEY = "hermesdesk.ui.fontSize";
export const THEME_MODE_KEY = "hermesdesk.ui.themeMode";
export const CUSTOM_COMPANION_IMAGE_KEY = "hermesdesk.ui.customCompanionImage";
export const MAX_CUSTOM_COMPANION_IMAGE_BYTES = 1024 * 1024;

const CUSTOM_COMPANION_IMAGE_EVENT = "kabuqina-custom-companion-image";
const CUSTOM_COMPANION_IMAGE_TYPES = new Set(["image/png", "image/webp", "image/svg+xml"]);

export type ThemeMode = "system" | "light" | "dark";
export type ResolvedTheme = "light" | "dark";

export type FontSizeOption = "small" | "medium" | "large";

export type CustomCompanionImageValidation =
  | { ok: true }
  | { ok: false; reason: "type" | "size" };

const ROOT_PX: Record<FontSizeOption, string> = {
  small: "14px",
  medium: "16px",
  large: "18px",
};

export function getStoredFontSize(): FontSizeOption {
  if (typeof window === "undefined" || !window.localStorage) {
    return "medium";
  }
  const v = window.localStorage.getItem(FONT_SIZE_KEY);
  if (v === "small" || v === "medium" || v === "large") {
    return v;
  }
  return "medium";
}

export function setFontSize(opt: FontSizeOption): void {
  if (typeof window !== "undefined" && window.localStorage) {
    window.localStorage.setItem(FONT_SIZE_KEY, opt);
  }
  applyFontSize(opt);
}

export function applyFontSize(opt?: FontSizeOption): void {
  if (typeof document === "undefined") {
    return;
  }
  const o = opt ?? getStoredFontSize();
  document.documentElement.style.fontSize = ROOT_PX[o] ?? ROOT_PX.medium;
  document.documentElement.setAttribute("data-font-size", o);
}

export function useFontSize() {
  const [size, setSizeState] = useState<FontSizeOption>(getStoredFontSize);
  const setSize = useCallback((opt: FontSizeOption) => {
    setFontSize(opt);
    setSizeState(opt);
  }, []);
  return { size, setSize };
}

export function getStoredThemeMode(): ThemeMode {
  if (typeof window === "undefined" || !window.localStorage) {
    return "system";
  }
  const v = window.localStorage.getItem(THEME_MODE_KEY);
  if (v === "system" || v === "light" || v === "dark") {
    return v;
  }
  return "system";
}

export function systemPrefersDark(): boolean {
  if (typeof window === "undefined" || !window.matchMedia) {
    return false;
  }
  return window.matchMedia("(prefers-color-scheme: dark)").matches;
}

export function resolveTheme(mode: ThemeMode): ResolvedTheme {
  if (mode === "dark") {
    return "dark";
  }
  if (mode === "light") {
    return "light";
  }
  return systemPrefersDark() ? "dark" : "light";
}

export function applyTheme(mode?: ThemeMode): ResolvedTheme {
  if (typeof document === "undefined") {
    return "light";
  }
  const stored = mode ?? getStoredThemeMode();
  const resolved = resolveTheme(stored);
  document.documentElement.dataset.themeMode = stored;
  document.documentElement.dataset.theme = resolved;
  document.documentElement.style.colorScheme = resolved;
  return resolved;
}

export function setThemeMode(mode: ThemeMode): ResolvedTheme {
  if (typeof window !== "undefined" && window.localStorage) {
    window.localStorage.setItem(THEME_MODE_KEY, mode);
  }
  return applyTheme(mode);
}

export function useThemeMode() {
  const [mode, setModeState] = useState<ThemeMode>(getStoredThemeMode);
  const [resolved, setResolved] = useState<ResolvedTheme>(() => resolveTheme(getStoredThemeMode()));

  useEffect(() => {
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const sync = () => {
      const current = getStoredThemeMode();
      setModeState(current);
      setResolved(applyTheme(current));
    };
    sync();
    mq.addEventListener("change", sync);
    return () => mq.removeEventListener("change", sync);
  }, []);

  const setMode = useCallback((next: ThemeMode) => {
    setThemeMode(next);
    setModeState(next);
    setResolved(resolveTheme(next));
  }, []);

  return { mode, setMode, resolved };
}

export function validateCustomCompanionImageFile(file: File): CustomCompanionImageValidation {
  if (!CUSTOM_COMPANION_IMAGE_TYPES.has(file.type)) {
    return { ok: false, reason: "type" };
  }
  if (file.size > MAX_CUSTOM_COMPANION_IMAGE_BYTES) {
    return { ok: false, reason: "size" };
  }
  return { ok: true };
}

export function getCustomCompanionImage(): string | null {
  if (typeof window === "undefined" || !window.localStorage) {
    return null;
  }
  const value = window.localStorage.getItem(CUSTOM_COMPANION_IMAGE_KEY);
  return value?.startsWith("data:image/") ? value : null;
}

function emitCustomCompanionImageChanged() {
  if (typeof window === "undefined") {
    return;
  }
  window.dispatchEvent(new Event(CUSTOM_COMPANION_IMAGE_EVENT));
}

export function setCustomCompanionImage(dataUrl: string): void {
  if (typeof window !== "undefined" && window.localStorage) {
    window.localStorage.setItem(CUSTOM_COMPANION_IMAGE_KEY, dataUrl);
  }
  emitCustomCompanionImageChanged();
}

export function clearCustomCompanionImage(): void {
  if (typeof window !== "undefined" && window.localStorage) {
    window.localStorage.removeItem(CUSTOM_COMPANION_IMAGE_KEY);
  }
  emitCustomCompanionImageChanged();
}

export function useCustomCompanionImage() {
  const [image, setImage] = useState<string | null>(getCustomCompanionImage);

  useEffect(() => {
    const sync = () => setImage(getCustomCompanionImage());
    window.addEventListener("storage", sync);
    window.addEventListener(CUSTOM_COMPANION_IMAGE_EVENT, sync);
    return () => {
      window.removeEventListener("storage", sync);
      window.removeEventListener(CUSTOM_COMPANION_IMAGE_EVENT, sync);
    };
  }, []);

  return image;
}
