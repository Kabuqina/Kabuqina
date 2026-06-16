# Auto-update Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a user-visible, signed auto-update flow before the next Windows release.

**Architecture:** Tauri owns update checking, installation, and relaunch through official updater/process plugins. The React settings page presents states and progress, while the tray menu opens Settings and asks the web shell to check. Release scripts generate static JSON manifests for GitHub primary and Tencent COS fallback.

**Tech Stack:** Tauri 2, Rust, React/Vite/TypeScript, PowerShell, Node source assertion tests.

---

## File Structure

- Modify `tauri/tauri.conf.json`: enable updater artifacts, add GitHub and COS endpoints, and wire the updater public key value that the release owner supplies.
- Modify `tauri/Cargo.toml`: add `tauri-plugin-process`.
- Modify `tauri/src/lib.rs`: register `tauri_plugin_process::init()`.
- Modify `tauri/src/tray.rs`: make "Check for updates" focus the main window and emit an event to the web shell.
- Modify `tauri/capabilities/default.json`: add process relaunch permission if required by the plugin.
- Modify `web/package.json` and `web/package-lock.json`: add `@tauri-apps/plugin-updater` and `@tauri-apps/plugin-process`.
- Create `web/src/lib/app-update.ts`: typed wrapper around Tauri updater/process APIs plus pure progress reducer helpers.
- Create `web/src/advanced/settings/SettingsUpdate.tsx`: Settings panel for check, download/install, and restart.
- Modify `web/src/advanced/Settings.tsx`: mount update panel in the General tab.
- Modify `web/src/locales/strings.ts`: add zh/en update strings.
- Create `web/src/advanced/settingsUpdate.test.mjs`: source-level regression tests for update UI and wiring.
- Modify `scripts/make_updater_manifest.ps1`: use `*.msi.zip` and `*.msi.zip.sig`, support GitHub/COS URL modes.
- Create `scripts/test_make_updater_manifest.ps1`: deterministic manifest-generation test.
- Modify `docs/auto-update.md` and `docs/release-checklist.md`: document GitHub primary, COS fallback, and updater artifact names.

## Task 1: Release Manifest Script

**Files:**
- Modify: `scripts/make_updater_manifest.ps1`
- Create: `scripts/test_make_updater_manifest.ps1`

- [ ] **Step 1: Write the failing script test**

Create `scripts/test_make_updater_manifest.ps1` that builds a temp bundle directory containing `Kabuqina_0.2.0_x64_en-US.msi`, `Kabuqina_0.2.0_x64_en-US.msi.zip`, and `Kabuqina_0.2.0_x64_en-US.msi.zip.sig`, invokes `make_updater_manifest.ps1`, parses JSON, and asserts:

```powershell
if ($json.version -ne "0.2.0") { throw "version mismatch" }
if ($json.platforms.'windows-x86_64'.url -notlike "*.msi.zip") { throw "not updater zip" }
if ($json.platforms.'windows-x86_64'.signature -ne "sig-value") { throw "signature mismatch" }
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pwsh -File scripts/test_make_updater_manifest.ps1`

Expected: fails because the current generator searches for `*.msi.sig` and emits bare MSI URLs.

- [ ] **Step 3: Implement minimal script support**

Update `scripts/make_updater_manifest.ps1` to:

- select `*.msi.zip`;
- select `*.msi.zip.sig`;
- accept `-AssetBaseUrl`;
- accept `-Out latest.json`;
- default GitHub URL to `https://github.com/$Repo/releases/download/$Version`;
- write `platforms.windows-x86_64.url` as `$AssetBaseUrl/$($zip.Name)`.

- [ ] **Step 4: Verify script test passes**

Run: `pwsh -File scripts/test_make_updater_manifest.ps1`

Expected: PASS with a success line.

## Task 2: Tauri Updater Configuration

**Files:**
- Modify: `tauri/tauri.conf.json`
- Modify: `tauri/Cargo.toml`
- Modify: `tauri/src/lib.rs`
- Modify: `tauri/capabilities/default.json`

- [ ] **Step 1: Write failing config assertions**

Add assertions to `web/src/advanced/settingsUpdate.test.mjs` that read `../../tauri/tauri.conf.json`, `../../tauri/Cargo.toml`, `../../tauri/src/lib.rs`, and `../../tauri/capabilities/default.json`, then assert:

```js
assert.equal(config.bundle.createUpdaterArtifacts, true);
assert.deepEqual(config.plugins.updater.endpoints, [
  "https://github.com/Kabuqina/Kabuqina/releases/latest/download/latest.json",
  "https://kabuqina-installer-1428509047.cos.ap-guangzhou.myqcloud.com/latest.json",
]);
assert.match(cargoSource, /tauri-plugin-process/);
assert.match(libSource, /tauri_plugin_process::init\(\)/);
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web; node src/advanced/settingsUpdate.test.mjs`

Expected: FAIL because updater artifacts are disabled/missing and process plugin is not registered.

- [ ] **Step 3: Implement config**

Set:

```json
"bundle": {
  "createUpdaterArtifacts": true
}
```

inside the existing bundle object. Set updater config:

```json
"plugins": {
  "updater": {
    "endpoints": [
      "https://github.com/Kabuqina/Kabuqina/releases/latest/download/latest.json",
      "https://kabuqina-installer-1428509047.cos.ap-guangzhou.myqcloud.com/latest.json"
    ],
    "windows": { "installMode": "passive" },
    "pubkey": "<release updater public key>"
  }
}
```

Add `tauri-plugin-process = "2"` and register `.plugin(tauri_plugin_process::init())`. If no release updater key exists yet, generate it with `cargo tauri signer generate --ci --write-keys "$HOME/.tauri/Kabuqina.key"` and commit only the emitted public key.

- [ ] **Step 4: Verify config tests pass**

Run: `cd web; node src/advanced/settingsUpdate.test.mjs`

Expected: PASS.

## Task 3: Web Update State and Settings UI

**Files:**
- Create: `web/src/lib/app-update.ts`
- Create: `web/src/advanced/settings/SettingsUpdate.tsx`
- Modify: `web/src/advanced/Settings.tsx`
- Modify: `web/src/locales/strings.ts`
- Modify: `web/package.json`
- Modify: `web/package-lock.json`
- Test: `web/src/advanced/settingsUpdate.test.mjs`

- [ ] **Step 1: Extend failing UI assertions**

In `settingsUpdate.test.mjs`, assert:

```js
assert.match(settingsSource, /SettingsUpdate/);
assert.match(updateSource, /checkForAppUpdate/);
assert.match(updateSource, /installAppUpdate/);
assert.match(updateSource, /relaunchApp/);
assert.match(settingsUpdateSource, /settings\.updateTitle/);
assert.match(stringsSource, /updateAvailable/);
assert.match(packageJsonSource, /@tauri-apps\/plugin-updater/);
assert.match(packageJsonSource, /@tauri-apps\/plugin-process/);
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web; node src/advanced/settingsUpdate.test.mjs`

Expected: FAIL because files and dependencies are missing.

- [ ] **Step 3: Add dependencies**

Run: `cd web; npm install @tauri-apps/plugin-updater @tauri-apps/plugin-process`

- [ ] **Step 4: Add update API wrapper**

Create `web/src/lib/app-update.ts` with exported `checkForAppUpdate`, `installAppUpdate`, and `relaunchApp`. The wrapper imports `check` from `@tauri-apps/plugin-updater` and `relaunch` from `@tauri-apps/plugin-process`.

- [ ] **Step 5: Add SettingsUpdate panel**

Create `SettingsUpdate.tsx` with idle/checking/up-to-date/update-available/downloading/ready/error states. Use existing `Section` and `Button` components.

- [ ] **Step 6: Mount panel and strings**

Mount `<SettingsUpdate />` in the General tab and add zh/en strings under `settings`.

- [ ] **Step 7: Verify UI tests pass**

Run: `cd web; node src/advanced/settingsUpdate.test.mjs`

Expected: PASS.

## Task 4: Tray Check Event

**Files:**
- Modify: `tauri/src/tray.rs`
- Modify: `web/src/advanced/settings/SettingsUpdate.tsx`
- Test: `web/src/advanced/settingsUpdate.test.mjs`

- [ ] **Step 1: Write failing event assertions**

Assert `tray.rs` emits an `app-update-check-requested` event and `SettingsUpdate.tsx` listens for that event.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web; node src/advanced/settingsUpdate.test.mjs`

Expected: FAIL until tray and listener are wired.

- [ ] **Step 3: Implement event wiring**

On tray update click, focus the main window and emit `app-update-check-requested`. In `SettingsUpdate`, listen for the event and call the same check handler.

- [ ] **Step 4: Verify test passes**

Run: `cd web; node src/advanced/settingsUpdate.test.mjs`

Expected: PASS.

## Task 5: Docs and Full Verification

**Files:**
- Modify: `docs/auto-update.md`
- Modify: `docs/release-checklist.md`

- [ ] **Step 1: Update docs**

Document GitHub primary + COS fallback, updater artifact names, and manifest generation examples:

```powershell
.\scripts\make_updater_manifest.ps1 -Version v0.2.0 -Channel github
.\scripts\make_updater_manifest.ps1 -Version v0.2.0 -Channel cos -Out latest.cos.json
```

- [ ] **Step 2: Run verification**

Run:

```powershell
pwsh -File scripts/test_make_updater_manifest.ps1
cd web; node src/advanced/settingsUpdate.test.mjs; npm run build
cd ..\tauri; cargo check
```

Expected: all pass.
