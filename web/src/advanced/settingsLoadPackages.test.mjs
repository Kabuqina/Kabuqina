/* global URL */
import assert from "node:assert/strict";
import fs from "node:fs";

const settingsSource = fs.readFileSync(new URL("./Settings.tsx", import.meta.url), "utf8");
const loadPackagesSource = fs.readFileSync(
  new URL("./settings/SettingsLoadPackages.tsx", import.meta.url),
  "utf8",
);
const chatApiSource = fs.readFileSync(new URL("../chat/chat-api.ts", import.meta.url), "utf8");
const stringsSource = fs.readFileSync(new URL("../locales/strings.ts", import.meta.url), "utf8");

assert.match(
  settingsSource,
  /SettingsLoadPackages/,
  "Settings should mount the generic load-package manager.",
);
assert.doesNotMatch(
  settingsSource,
  /SettingsFormulaModel/,
  "Settings should not mount the old formula-only model block.",
);
assert.match(
  loadPackagesSource,
  /cmdLoadPackages[\s\S]*packages\.map/,
  "The load-package manager should render packages returned by the generic API.",
);
assert.match(
  chatApiSource,
  /cmd_load_packages[\s\S]*cmd_load_package_download[\s\S]*cmd_load_package_delete/,
  "The web API should use the generic Tauri load-package commands.",
);
assert.match(
  chatApiSource,
  /desktop_bridge_unavailable/,
  "The load-package API should throw a stable error when the Tauri bridge is unavailable.",
);
assert.match(
  chatApiSource,
  /__TAURI_INTERNALS__[\s\S]*invoke/,
  "The load-package API should check for the actual Tauri invoke bridge.",
);
assert.match(
  loadPackagesSource,
  /loadPackagesDesktopOnly/,
  "The Settings UI should show a friendly desktop-only message instead of raw invoke errors.",
);
assert.doesNotMatch(
  chatApiSource,
  /cmd_formula_model_|FormulaModelStatus|cmdFormulaModel/,
  "The web API should not expose the old formula-only commands.",
);
assert.match(stringsSource, /loadPackagesTitle/);
assert.match(stringsSource, /loadPackagesDesktopOnly/);
assert.match(stringsSource, /docling-codeformula/);
assert.match(stringsSource, /local-stt-base-q5_1/);
