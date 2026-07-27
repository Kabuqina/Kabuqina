// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { applyTheme, setThemeMode, THEME_MODE_KEY, watchSystemTheme } from "./ui-prefs";

/**
 * 「跟随系统」以前只在设置页成立：监听 `prefers-color-scheme` 的代码只写在
 * `useThemeMode()` 里，而那个 hook 只有设置页用。这里用可控的 matchMedia 桩
 * 直接驱动 change 事件——浏览器预览工具只换 `matches` 不派发事件，验不了这条。
 */

type Listener = () => void;

let matches = false;
const listeners = new Set<Listener>();

function installMatchMediaStub() {
  Object.defineProperty(window, "matchMedia", {
    configurable: true,
    writable: true,
    value: (query: string) => ({
      media: query,
      get matches() {
        return matches;
      },
      addEventListener: (_: string, cb: Listener) => listeners.add(cb),
      removeEventListener: (_: string, cb: Listener) => listeners.delete(cb),
      addListener: (cb: Listener) => listeners.add(cb),
      removeListener: (cb: Listener) => listeners.delete(cb),
      dispatchEvent: () => true,
      onchange: null,
    }),
  });
}

function setSystemDark(next: boolean) {
  matches = next;
  listeners.forEach((cb) => cb());
}

beforeEach(() => {
  matches = false;
  listeners.clear();
  window.localStorage.clear();
  installMatchMediaStub();
});

afterEach(() => {
  listeners.clear();
  window.localStorage.clear();
});

describe("watchSystemTheme", () => {
  it("follows the system while the mode is 'system'", () => {
    setThemeMode("system");
    applyTheme();
    expect(document.documentElement.dataset.theme).toBe("light");

    const stop = watchSystemTheme();
    setSystemDark(true);
    expect(document.documentElement.dataset.theme).toBe("dark");

    setSystemDark(false);
    expect(document.documentElement.dataset.theme).toBe("light");
    stop();
  });

  it("does not override an explicit choice", () => {
    setThemeMode("light");
    expect(document.documentElement.dataset.theme).toBe("light");

    const stop = watchSystemTheme();
    setSystemDark(true);
    // 明确选了浅色的人，不该因为系统切深色就被改掉。
    expect(document.documentElement.dataset.theme).toBe("light");
    expect(window.localStorage.getItem(THEME_MODE_KEY)).toBe("light");
    stop();
  });

  it("stops listening once disposed", () => {
    setThemeMode("system");
    const stop = watchSystemTheme();
    stop();
    setSystemDark(true);
    expect(document.documentElement.dataset.theme).toBe("light");
  });
});
