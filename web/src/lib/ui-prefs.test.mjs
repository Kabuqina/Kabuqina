import assert from "node:assert/strict";
import fs from "node:fs";

const uiPrefsSource = fs.readFileSync(new URL("./ui-prefs.ts", import.meta.url), "utf8");
const indexHtmlSource = fs.readFileSync(new URL("../../index.html", import.meta.url), "utf8");
const indexCssSource = fs.readFileSync(new URL("../index.css", import.meta.url), "utf8");
const settingsDisplaySource = fs.readFileSync(
  new URL("../advanced/settings/SettingsDisplay.tsx", import.meta.url),
  "utf8",
);
const mainSource = fs.readFileSync(new URL("../main.tsx", import.meta.url), "utf8");

assert.match(uiPrefsSource, /export type ThemeMode = "system" \| "light" \| "dark"/);
assert.match(uiPrefsSource, /export const THEME_MODE_KEY = "hermesdesk\.ui\.themeMode"/);
assert.match(uiPrefsSource, /export function applyTheme/);
assert.match(uiPrefsSource, /export function useThemeMode/);
assert.match(uiPrefsSource, /prefers-color-scheme: dark/);

assert.match(indexHtmlSource, /hermesdesk\.ui\.themeMode/);
assert.match(indexHtmlSource, /dataset\.themeMode/);
assert.match(indexHtmlSource, /dataset\.theme = dark \? "dark" : "light"/);

assert.match(indexCssSource, /@custom-variant dark/);
assert.match(indexCssSource, /\[data-theme="dark"\][\s\S]*--kq-color-ink:\s*#e2dde8/);

assert.match(settingsDisplaySource, /settings\.themeTitle/);
assert.match(settingsDisplaySource, /onSetThemeMode/);
assert.match(mainSource, /applyTheme\(\)/);

console.log("ui-prefs.test.mjs: ok");
