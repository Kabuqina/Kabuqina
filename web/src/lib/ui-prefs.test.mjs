import assert from "node:assert/strict";
import fs from "node:fs";

const uiPrefsSource = fs.readFileSync(new URL("./ui-prefs.ts", import.meta.url), "utf8");
const indexHtmlSource = fs.readFileSync(new URL("../../index.html", import.meta.url), "utf8");
const indexCssSource = fs.readFileSync(new URL("../index.css", import.meta.url), "utf8");
const settingsDisplaySource = fs.readFileSync(
  new URL("../advanced/settings/SettingsDisplay.tsx", import.meta.url),
  "utf8",
);
const companionPillSource = fs.readFileSync(
  new URL("../components/CompanionPillScene.tsx", import.meta.url),
  "utf8",
);
const artAssetsSource = fs.readFileSync(new URL("./artAssets.ts", import.meta.url), "utf8");
const mainSource = fs.readFileSync(new URL("../main.tsx", import.meta.url), "utf8");

assert.match(uiPrefsSource, /export type ThemeMode = "system" \| "light" \| "dark"/);
assert.match(uiPrefsSource, /export const THEME_MODE_KEY = "kabuqina\.ui\.themeMode"/);
assert.match(uiPrefsSource, /LEGACY_THEME_MODE_KEY = "hermesdesk\.ui\.themeMode"/);
assert.match(uiPrefsSource, /readAndMigrate\(THEME_MODE_KEY, LEGACY_THEME_MODE_KEY\)/);
assert.match(uiPrefsSource, /export function applyTheme/);
assert.match(uiPrefsSource, /export function useThemeMode/);
assert.match(uiPrefsSource, /prefers-color-scheme: dark/);

assert.match(indexHtmlSource, /kabuqina\.ui\.themeMode/);
assert.match(indexHtmlSource, /hermesdesk\.ui\.themeMode/);
assert.match(indexHtmlSource, /dataset\.themeMode/);
assert.match(indexHtmlSource, /dataset\.theme = dark \? "dark" : "light"/);

assert.match(indexCssSource, /@custom-variant dark/);
assert.match(indexCssSource, /\[data-theme="dark"\][\s\S]*--kq-color-ink:\s*#e2dde8/);

assert.match(settingsDisplaySource, /settings\.themeTitle/);
assert.match(settingsDisplaySource, /onSetThemeMode/);
assert.match(mainSource, /applyTheme\(\)/);

assert.match(uiPrefsSource, /CUSTOM_COMPANION_IMAGE_KEY\s*=\s*"kabuqina\.ui\.customCompanionImage"/);
assert.match(uiPrefsSource, /LEGACY_CUSTOM_COMPANION_IMAGE_KEY = "hermesdesk\.ui\.customCompanionImage"/);
assert.match(uiPrefsSource, /MAX_CUSTOM_COMPANION_IMAGE_BYTES\s*=\s*1024 \* 1024/);
assert.match(uiPrefsSource, /validateCustomCompanionImageFile/);
assert.match(uiPrefsSource, /image\/png[\s\S]*image\/webp[\s\S]*image\/svg\+xml/);
assert.match(uiPrefsSource, /getCustomCompanionImage[\s\S]*setCustomCompanionImage[\s\S]*clearCustomCompanionImage/);

assert.match(settingsDisplaySource, /ImageIcon/);
assert.match(settingsDisplaySource, /settings\.companionImageTitle/);
assert.match(settingsDisplaySource, /settings\.companionImageSpec/);
assert.match(settingsDisplaySource, /accept="image\/png,image\/webp,image\/svg\+xml"/);
assert.match(settingsDisplaySource, /validateCustomCompanionImageFile[\s\S]*setCustomCompanionImage/);
assert.match(settingsDisplaySource, /settings\.companionImageReset/);

assert.match(companionPillSource, /useCustomCompanionImage/);
// 默认图走换装表（pre-art 接缝），自定义图仍然优先。
assert.match(companionPillSource, /customImage \?\? ART_ASSETS\.companionPill/);
assert.match(artAssetsSource, /companionPill:\s*`\/\$\{GENERATED_SCENE_FILENAMES\.companionPill\}`/);

assert.match(
  settingsDisplaySource,
  /open\(\{[\s\S]*directory:\s*true[\s\S]*multiple:\s*false/,
  "Workspace settings should use the system directory picker.",
);
assert.match(
  settingsDisplaySource,
  /cmd_set_workspace[\s\S]*migrateFiles/,
  "Workspace settings should persist custom workspace selection with optional migration.",
);
assert.match(
  settingsDisplaySource,
  /workspaceMigrateFiles[\s\S]*workspaceChoose[\s\S]*workspaceResetDefault/,
  "Workspace settings should expose migration, choose, and reset controls.",
);

console.log("ui-prefs.test.mjs: ok");
