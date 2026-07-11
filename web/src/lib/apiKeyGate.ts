// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

/** User chose “configure API later” on the pass step; allows opening /chat without a saved key until they configure. */
const STORAGE_KEY = "kabuqina.allow_chat_without_api";
const LEGACY_STORAGE_KEY = "hermesdesk.allow_chat_without_api";

export function setAllowChatWithoutApi(): void {
  try {
    localStorage.setItem(STORAGE_KEY, "1");
  } catch {
    /* ignore */
  }
}

export function getAllowChatWithoutApi(): boolean {
  try {
    const value = localStorage.getItem(STORAGE_KEY) ?? localStorage.getItem(LEGACY_STORAGE_KEY);
    if (value === "1") localStorage.setItem(STORAGE_KEY, value);
    return value === "1";
  } catch {
    return false;
  }
}

export function clearAllowChatWithoutApi(): void {
  try {
    localStorage.removeItem(STORAGE_KEY);
    localStorage.removeItem(LEGACY_STORAGE_KEY);
  } catch {
    /* ignore */
  }
}
