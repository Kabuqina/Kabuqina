import assert from "node:assert/strict";
import fs from "node:fs";

const settingsSource = fs.readFileSync(new URL("./Settings.tsx", import.meta.url), "utf8");
const stringsSource = fs.readFileSync(new URL("../locales/strings.ts", import.meta.url), "utf8");
const packageJsonSource = fs.readFileSync(new URL("../../package.json", import.meta.url), "utf8");
const tauriConfigSource = fs.readFileSync(
  new URL("../../../tauri/tauri.conf.json", import.meta.url),
  "utf8",
);
const cargoSource = fs.readFileSync(new URL("../../../tauri/Cargo.toml", import.meta.url), "utf8");
const traySource = fs.readFileSync(new URL("../../../tauri/src/tray.rs", import.meta.url), "utf8");

for (const [sourceName, source] of [
  ["settings", settingsSource],
  ["locales", stringsSource],
  ["web dependencies", packageJsonSource],
  ["Tauri config", tauriConfigSource],
  ["Rust dependencies", cargoSource],
  ["tray menu", traySource],
]) {
  assert.doesNotMatch(source, /SettingsUpdate|software updates|软件更新|plugin[_-]updater|app-update-check-requested/i,
    `${sourceName} should not expose the desktop updater in the 0.5 MVP.`);
}
