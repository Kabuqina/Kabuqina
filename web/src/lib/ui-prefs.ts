// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useCallback, useState } from "react";

/**
 * UI preferences persisted in localStorage (shell webview).
 * Root `font-size` scales `rem` used by Tailwind text utilities.
 */

const FONT_SIZE_KEY = "hermesdesk.ui.fontSize";

export type FontSizeOption = "small" | "medium" | "large";

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
