# Auto-update Design

## Goal

Before the next release, Kabuqina must be able to check for updates, download a signed updater bundle, install it, and restart into the newer version without blocking normal chat usage when update checks fail.

## Scope

This design covers Windows MSI releases built by Tauri 2. It uses Tauri's official updater plugin and static JSON manifests. It does not introduce a custom update server, forced upgrades, staged rollout logic, or a separate patcher process.

## Release Channel

GitHub Releases is the primary update source. Tencent COS is the fallback source for users who cannot reliably reach GitHub.

The Tauri updater endpoint list will be ordered:

1. `https://github.com/Kabuqina/Kabuqina/releases/latest/download/latest.json`
2. `https://kabuqina-installer-1428509047.cos.ap-guangzhou.myqcloud.com/latest.json`

Both manifests must describe the same version and the same signed updater bundle. The download URL inside the GitHub manifest may point to GitHub. The download URL inside the COS manifest may point to COS. Both bundles are verified by the updater signature, so hosting trust does not replace signature trust.

The COS release host is `https://kabuqina-installer-1428509047.cos.ap-guangzhou.myqcloud.com`. The current manually uploaded MSI object uses that host, for example `https://kabuqina-installer-1428509047.cos.ap-guangzhou.myqcloud.com/Kabuqina_0.1.0_x64_en-US.msi`. The updater implementation will publish `latest.json`, `*.msi.zip`, and `*.msi.zip.sig` beside the installer under the same host.

## Architecture

Tauri owns update installation. The React web shell owns user interaction.

The Rust shell already registers `tauri-plugin-updater`. The implementation will enable updater configuration in `tauri/tauri.conf.json`, set `bundle.createUpdaterArtifacts` so Tauri creates Windows updater artifacts, and keep updater permissions in `tauri/capabilities/default.json`.

The web shell will add a small update panel under Settings. It will call `@tauri-apps/plugin-updater`:

- `check()` to find an available update.
- `downloadAndInstall()` to download and install while reporting progress.
- a relaunch/restart path after installation succeeds.

The tray "Check for updates" item should not silently discard results. It should either surface the main window and route the user to Settings, or emit an event that the web shell displays in the same update panel.

## User Experience

Normal use must remain calm:

- The user can manually check from Settings.
- The tray menu keeps "Check for updates".
- A startup check may run silently after the app is ready, but it must not block onboarding, chat, Python startup, or gateway startup.
- If no update exists, the UI says the app is up to date.
- If an update exists, the UI shows current version, available version, release notes when present, and an "Update" button.
- During download/install, show progress when Tauri provides byte counts.
- After installation, ask the user to restart. No surprise restarts.
- If GitHub is unavailable and COS works, the user should not see a GitHub-specific failure.
- If both sources fail, show a friendly network/update error and keep the app usable.

## Release Artifacts

Tauri v2 updater artifacts on Windows are zip-wrapped installer bundles:

- Standard installer: `*.msi`
- Updater bundle: `*.msi.zip`
- Updater signature: `*.msi.zip.sig`

The manifest generator must use the updater bundle and signature, not the bare MSI. `latest.json` must include the platform key `windows-x86_64`, the SemVer version, release notes, publish date, download URL, and signature content.

The existing `scripts/make_updater_manifest.ps1` should be updated so it can generate:

- a GitHub manifest with GitHub release asset URLs;
- a COS manifest with COS asset URLs;
- or one manifest when both hosts intentionally share the same asset URL.

## Security

The updater public key is committed in `tauri/tauri.conf.json`. The private key and password stay outside the repository and are supplied by the release environment.

The release checklist must require:

- updater public key present;
- private key configured in CI or the local release environment;
- `bundle.createUpdaterArtifacts` enabled;
- `*.msi.zip`, `*.msi.zip.sig`, GitHub `latest.json`, and COS `latest.json` produced;
- both endpoint URLs manually fetched before publishing release notes.

The app must not allow downgrades by default.

## Error Handling

Update failures are non-fatal. Failed checks, bad signatures, partial downloads, missing manifests, and network timeouts report status in Settings and logs, then return the user to the current installed version.

The UI should avoid promising that GitHub failed specifically unless the implementation can identify that source. A generic message such as "Could not check for updates. Please try again later." is acceptable for the first version.

## Testing

Tests should cover the deterministic parts:

- Manifest generation selects `*.msi.zip` and `*.msi.zip.sig`.
- Manifest generation strips leading `v` from the version field.
- Settings update UI maps states correctly: idle, checking, up-to-date, update available, downloading, ready to restart, and error.
- Build config includes updater artifacts and both endpoints.

Manual QA before release:

- Current version sees no update when `latest.json` matches.
- Old installed version finds a newer release.
- GitHub endpoint unavailable but COS endpoint available still finds the update.
- Bad signature refuses installation.
- Completed install restarts into the new version.

## Configuration

The Tencent COS fallback host is known. Before tagging each release, the release operator must upload the matching `latest.json`, `*.msi.zip`, and `*.msi.zip.sig` objects to `https://kabuqina-installer-1428509047.cos.ap-guangzhou.myqcloud.com`.
