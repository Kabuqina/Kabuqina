/* global URL */
import assert from "node:assert/strict";
import fs from "node:fs";

const tauriConfig = JSON.parse(
  fs.readFileSync(new URL("../../../tauri/tauri.conf.json", import.meta.url), "utf8"),
);
const cargoSource = fs.readFileSync(new URL("../../../tauri/Cargo.toml", import.meta.url), "utf8");
const libSource = fs.readFileSync(new URL("../../../tauri/src/lib.rs", import.meta.url), "utf8");
const traySource = fs.readFileSync(new URL("../../../tauri/src/tray.rs", import.meta.url), "utf8");
const capabilitiesSource = fs.readFileSync(
  new URL("../../../tauri/capabilities/default.json", import.meta.url),
  "utf8",
);
const settingsSource = fs.readFileSync(new URL("./Settings.tsx", import.meta.url), "utf8");
const updateApiSource = fs.readFileSync(new URL("../lib/app-update.ts", import.meta.url), "utf8");
const settingsUpdateSource = fs.readFileSync(new URL("./settings/SettingsUpdate.tsx", import.meta.url), "utf8");
const stringsSource = fs.readFileSync(new URL("../locales/strings.ts", import.meta.url), "utf8");
const packageJsonSource = fs.readFileSync(new URL("../../package.json", import.meta.url), "utf8");

assert.equal(
  tauriConfig.bundle.createUpdaterArtifacts,
  true,
  "Tauri release builds should create updater zip/signature artifacts.",
);
assert.equal(
  tauriConfig.plugins.updater.active,
  true,
  "Tauri updater plugin should be active for release builds.",
);
assert.deepEqual(
  tauriConfig.plugins.updater.endpoints,
  [
    "https://github.com/Kabuqina/Kabuqina/releases/latest/download/latest.json",
    "https://kabuqina-installer-1428509047.cos.ap-guangzhou.myqcloud.com/latest.json",
  ],
  "Updater should try GitHub first and Tencent COS second.",
);
assert.match(
  tauriConfig.plugins.updater.pubkey,
  /^[A-Za-z0-9+/=\r\n]+$/,
  "Updater public key should be committed as base64 text.",
);
assert.match(cargoSource, /tauri-plugin-process/, "Cargo should include the process plugin.");
assert.match(libSource, /tauri_plugin_process::init\(\)/, "Rust shell should register the process plugin.");
assert.match(capabilitiesSource, /updater:default/, "Main window should be allowed to use updater APIs.");
assert.match(capabilitiesSource, /process:default/, "Main window should be allowed to relaunch after update.");

assert.match(settingsSource, /SettingsUpdate/, "Settings should mount the update panel.");
assert.match(updateApiSource, /checkForAppUpdate/, "Update API wrapper should expose checkForAppUpdate.");
assert.match(updateApiSource, /installAppUpdate/, "Update API wrapper should expose installAppUpdate.");
assert.match(updateApiSource, /relaunchApp/, "Update API wrapper should expose relaunchApp.");
assert.match(settingsUpdateSource, /settings\.updateTitle/, "Update panel should render localized title.");
assert.match(settingsUpdateSource, /checkForAppUpdate/, "Update panel should check through the wrapper.");
assert.match(settingsUpdateSource, /installAppUpdate/, "Update panel should install through the wrapper.");
assert.match(settingsUpdateSource, /relaunchApp/, "Update panel should relaunch through the wrapper.");
assert.match(settingsUpdateSource, /app-update-check-requested/, "Update panel should listen for tray update checks.");
assert.match(traySource, /app-update-check-requested/, "Tray menu should emit an update check request.");
assert.match(packageJsonSource, /@tauri-apps\/plugin-updater/, "Web app should depend on updater plugin.");
assert.match(packageJsonSource, /@tauri-apps\/plugin-process/, "Web app should depend on process plugin.");
assert.match(stringsSource, /updateTitle/, "Localized update strings should exist.");
assert.match(stringsSource, /updateAvailable/, "Localized update availability strings should exist.");
