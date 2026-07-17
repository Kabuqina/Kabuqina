# Auto-update

Kabuqina uses Tauri's [updater plugin](https://v2.tauri.app/plugin/updater/).
The updater checks Tencent COS first and GitHub Releases second. Update
artifacts are signed with a dedicated Ed25519 updater keypair; this keypair is
independent from the optional Windows Authenticode certificate.

## v0.4 trust-root reset

The updater private key used before v0.4 is no longer recoverable. Therefore:

- v0.2/v0.3 installations cannot authenticate v0.4 through the old updater
  chain and must install v0.4 manually once.
- v0.4 embeds a newly generated public key and starts the replacement trust
  chain. Keep the matching encrypted private key so v0.5 and later releases
  can update v0.4 automatically.
- The old `latest.json` channel is retired and must not be overwritten with an
  artifact signed by the new key. The replacement channel is
  `latest-v2.json` on both COS and GitHub.

This is a one-time manual migration, not a normal automatic update test.

## One-time key setup (project owner only)

Generate the replacement key outside the repository. The command prompts for
a password; never paste the private key or password into an issue, task, chat,
log, or committed file.

```powershell
cd D:\project\Kabuqina\tauri
cargo tauri signer generate -w "C:\Users\X13\.tauri\Kabuqina-updater-v2.key"
```

Immediately after generation:

1. Put the generated **public key** in
   `tauri/tauri.conf.json#plugins.updater.pubkey`. The public key is safe to
   commit.
2. Keep two recoverable copies of the encrypted private-key file on separate,
   access-controlled storage. GitHub Actions is not a backup.
3. Store the password in a password manager separately from the key file, with
   enough labeling to identify the Kabuqina updater v2 key.
4. Put the encrypted private-key content in GitHub secret
   `TAURI_UPDATER_PRIVATE_KEY` and its password in
   `TAURI_UPDATER_PRIVATE_KEY_PASSWORD`.
5. In a clean shell, perform a signing/build recovery drill using the backed-up
   key and password, and confirm that Tauri produces
   `*-setup.nsis.zip.sig`. Record only that the drill passed, never the secret.

The release workflow and local Tauri build run
`scripts/check_updater_release.ps1`. It rejects the retired public key,
misaligned versions, wrong endpoints, and a tag that does not match the app
version. CI additionally rejects missing signing secrets.

## Release flow

1. Align `tauri/tauri.conf.json`, `tauri/Cargo.toml`, `web/package.json`, and
   `web/package-lock.json` to the release version.
2. Run the updater configuration check:

   ```powershell
   .\scripts\check_updater_release.ps1 -ExpectedVersion v0.4.0
   ```

3. Build the Python bundle, Web shell, and signed NSIS package in the order
   documented in `AGENTS.md`. Tauri produces `*-setup.exe`,
   `*-setup.nsis.zip`, and `*-setup.nsis.zip.sig` because
   `bundle.createUpdaterArtifacts=true`.
4. Generate the COS manifest and upload it as `latest-v2.json` together with
   the matching installer, updater zip, and signature:

   ```powershell
   .\scripts\make_updater_manifest.ps1 `
     -Version v0.4.0 `
     -AssetBaseUrl "https://kabuqina-installer-1428509047.cos.ap-guangzhou.myqcloud.com" `
     -Out latest-v2.cos.json
   ```

5. Add `docs/releases/vX.Y.Z.md`, then push the matching tag. The release
   workflow generates the GitHub manifest as `latest-v2.json` and attaches it
   with the same artifacts to a **draft** GitHub Release. For a manual release,
   generate it explicitly:

   ```powershell
   .\scripts\make_updater_manifest.ps1 `
     -Version v0.4.0 `
     -Out latest-v2.github.json
   ```

6. Install and smoke-test the draft artifacts, upload the matching COS
   artifacts and COS manifest, then publish the GitHub draft only after those
   gates pass.

7. Verify both published manifests report the same version, contain a non-empty
   signature, and link to downloadable artifacts:

   - `https://kabuqina-installer-1428509047.cos.ap-guangzhou.myqcloud.com/latest-v2.json`
   - `https://github.com/Kabuqina/Kabuqina/releases/latest/download/latest-v2.json`

8. For the v0.4 transition, verify a manual v0.4 install over an existing
   v0.2/v0.3 installation preserves app data. The first end-to-end automatic
   updater proof for the new chain is a separately signed version higher than
   v0.4 (normally v0.5 or a controlled prerelease), not v0.4 updating itself.

## User experience

- No surprise restarts. The updater downloads in the background and waits for
  the user to click "Restart and update".
- Network, manifest, download, or signature failure leaves the installed app
  usable on its current version.
- Release notes for v0.4 must tell v0.2/v0.3 users that one manual installer
  run is required to join the replacement update chain.

## Rolling back

Do not republish an older version under the same release. Publish a higher
version containing the previous good code and sign it with the same updater v2
private key. Keep both COS and GitHub manifests consistent.
