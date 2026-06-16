# Auto-update

Kabuqina uses Tauri's [updater plugin](https://v2.tauri.app/plugin/updater/),
pointed first at GitHub Releases and then at a Tencent COS fallback manifest.
Updates are signed with a separate Ed25519 keypair (the "updater key") so a
compromised CDN cannot push a malicious binary even if the cert is fine.

## One-time setup (project owner)

```powershell
# Generates ~/.tauri/Kabuqina.key + Kabuqina.key.pub
cargo install tauri-cli --version "^2" --locked
cargo tauri signer generate -w ~/.tauri/Kabuqina.key
```

- Put the **public key** into `tauri.conf.json#plugins.updater.pubkey`.
- Put the **private key** + its password into GitHub Actions secrets
  (`TAURI_SIGNING_PRIVATE_KEY`, `TAURI_SIGNING_PRIVATE_KEY_PASSWORD`).
  Never commit the private key.

## Release flow

1. Tag a commit: `git tag v0.1.1 && git push --tags`
2. The `release` workflow (`.github/workflows/release.yml`) builds the MSI
   with `bundle.createUpdaterArtifacts=true`, producing the normal installer
   plus Tauri updater artifacts: `*.msi.zip` and `*.msi.zip.sig`.
3. Run `scripts/make_updater_manifest.ps1` for the GitHub asset URL:
   ```powershell
   .\scripts\make_updater_manifest.ps1 -Version v0.1.1
   ```
4. Run it again for COS if COS hosts its own copy of the updater zip:
   ```powershell
   .\scripts\make_updater_manifest.ps1 `
     -Version v0.1.1 `
     -AssetBaseUrl "https://kabuqina-installer-1428509047.cos.ap-guangzhou.myqcloud.com" `
     -Out latest.cos.json
   ```
5. Attach `*.msi`, `*.msi.zip`, `*.msi.zip.sig`, and GitHub `latest.json` to
   the GitHub release.
6. Upload `latest.cos.json` as `latest.json` plus the matching `*.msi.zip`
   and `*.msi.zip.sig` to Tencent COS.
7. Existing installs check GitHub first:
   `https://github.com/Kabuqina/Kabuqina/releases/latest/download/latest.json`
   and then COS:
   `https://kabuqina-installer-1428509047.cos.ap-guangzhou.myqcloud.com/latest.json`.
   Settings and the tray menu both expose "Check for updates".

## User experience

- No surprise restarts. The updater downloads in the background and waits
  for the user to click "Restart and update".
- Failure modes (no network, bad signature, partial download) all fall
  back silently to "stay on current version" — the user is never blocked
  from chatting because of an update glitch.

## Rolling back

If a release is bad, delete the GitHub Release (or unpublish it). Existing
installs that already updated keep running. New installs and not-yet-updated
installs go to the previous release.

For an "emergency replace", publish a new tag with a higher version number
that ships the previous good code.
