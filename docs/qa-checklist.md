# Release QA checklist

Run this whole checklist on **both** OS images before tagging a release. Ideally use clean VMs (Hyper-V or VirtualBox) so leftover state from previous runs does not mask install bugs.

## Before you test (repo & build)

- [ ] The owned **`hermes_core/`** tree is present at the release commit; it is not a submodule. A source/runtime mismatch can break the Python bundle.
- [ ] If you build from source, use the same **tag or branch** the release is cut from, not a random main checkout.
- [ ] **Windows Defender / real-time scan** can hold file locks during bundling or first run (symptoms: `os error 32`, failed copy, or `python.exe` / build scripts failing to overwrite files). For **local dev** or **repeated bundle builds**, add exclusions for the repo path and, if needed, `%LOCALAPPDATA%\com.kabuqina.app` and your `python\dist` build output—then retry from a clean tree if a run was interrupted mid-write.

## Target images

| Image                    | Why                                        |
|--------------------------|--------------------------------------------|
| Windows 10 22H2 x64      | Lowest supported. Has WebView2 evergreen.  |
| Windows 11 23H2 x64      | Default for new PCs.                       |
| Windows 10 LTSC 2021     | (Optional) Stripped image; catches missing OS bits. |

## What you are testing (current product)

- **Shell (Tauri + `web/`)**: Splash routing, onboarding (minimal + optional messaging sections), **`/chat`** shell chat, Settings (power user, proxy, **messaging gateway**, Telegram / Feishu / QQ / Weixin blocks, pairing). This is the only shipped UI.
- **Embedded desk API** (`http://127.0.0.1:<port>/api/desk/*`): Kabuqina-owned loopback service used by the shell; no upstream dashboard is bundled.
- **Messaging gateway**: Second supervised Python process **`python -m gateway.run`** when `.env` has channel credentials — **Settings → Messaging gateway** plus [`docs/troubleshooting.md`](troubleshooting.md) §12 if startup fails.
- **Language**: Shell copy follows the selected application language.

## A. Install

- [ ] Download `.msi` from GitHub Releases over a normal browser
- [ ] SmartScreen status:
  - [ ] OV-only build: shows "More info" -> publisher = Kabuqina
  - [ ] After warm-up: no warning at all
- [ ] Double-click the `.msi`
  - [ ] No UAC prompt (per-user install)
  - [ ] Finishes within 60s on a clean SSD
  - [ ] Start Menu has "Kabuqina"
  - [ ] No desktop shortcut unless we ship one (we don't, by design)
- [ ] Disk usage at `%LOCALAPPDATA%\com.kabuqina.app` is between 80 and 200 MB

## B. First launch (cold)

- [ ] App opens within a few seconds (Splash visible)
- [ ] If no API key yet: routes to **onboarding**
- [ ] If a key already exists: Splash routes to **`/chat`**
- [ ] Optional: user chose **configure API later** → Splash may route to **`/chat`** without Credential Manager key (limited flows — see shell `apiKeyGate`)
- [ ] No console window flashes or stays open
- [ ] Tray icon appears
- [ ] `%LOCALAPPDATA%\com.kabuqina.app\logs\kabuqina.log` exists and contains a line like `python ready on port` with a port number (desk API is up)

## C. Onboarding wizard (zero-jargon happy path)

- [ ] Welcome screen wording reads naturally to a non-tech tester
- [ ] "Pick a brain" - tap "Free starter" -> "Get your access pass"
- [ ] Provider signup link opens **DeepSeek** (or chosen provider) in default browser, **not** in-app
- [ ] Paste a known-good key, hit "Save and continue":
  - [ ] Validation succeeds within a few seconds
  - [ ] No plaintext key in `%LOCALAPPDATA%\com.kabuqina.app\settings.json`
  - [ ] `cmdkey /list:Kabuqina*` lists the credential
- [ ] Pick a vibe -> **Done** page renders
- [ ] "Open workspace folder" opens `Documents\KabuqinaWork` in Explorer
- [ ] Done primary CTA opens **`/chat`** or **dashboard** per build UX; extended wizard optionally completes **one** messaging channel (Weixin / QQ / Feishu / Telegram)

## D. Desk API + shell `/chat` sanity

- [ ] **`/chat`**: send a short message and receive an assistant reply using the configured Credential Manager key.
- [ ] **Smoke**: Settings status, sessions, and one minimal model-backed flow work through the bundled desk API.
- [ ] (When applicable) Drop a `.txt` file into the workspace folder and confirm workspace-scoped tools behave per jail rules.
- [ ] (When applicable) Ask for an action that should be **jailed** to the workspace; out-of-workspace paths should be denied with a clear error.

## E. Safety / Power user

- [ ] In Settings, attempt to enable Power user - confirmation dialog appears
- [ ] Enable, then ask the agent to run `dir`:
  - [ ] Native Windows dialog appears with the command and CWD
  - [ ] "Deny" leaves the workspace untouched
  - [ ] "Allow this once" runs it; output reaches the chat or tool surface your build uses
  - [ ] Re-asking later still re-prompts (no implicit "always allow")
- [ ] Disable Power user, restart - Power-user-only tools no longer appear in the agent's tool list

## F. Persistence + restart

- [ ] Close main window (title bar **×** or Alt+F4) — app **stays in tray**; left-click tray or **Open** restores the main window
- [ ] Quit via tray "Quit" — no orphan **`python.exe`** processes (expect **two** while messaging gateway was running: web + gateway — both should exit)
- [ ] Reopen — skips onboarding when configured; Splash routes per **`cmd_has_secret`** / gate flags (**`/chat`** when key exists)
- [ ] Reboot the VM, open the app — same behavior, key still works

## G. Network allowlist

- [ ] Ask the agent to fetch `https://example.com` — blocked with a clear error unless the host is allowlisted.
- [ ] Settings → add **`example.com`** to extra hosts → retry → succeeds (without relying on power-user toggle to disable the allowlist).

## H. Updates

- [ ] Install v0.1.0
- [ ] Publish v0.1.1 release with bumped version
- [ ] Tray menu -> "Check for updates" finds it
- [ ] Click update -> download progress visible
- [ ] After restart, Settings shows v0.1.1
- [ ] Workspace folder + saved key carried forward

## I. Uninstall

- [ ] Settings -> Apps -> Kabuqina -> Uninstall
- [ ] No UAC prompt
- [ ] Removes `%LOCALAPPDATA%\com.kabuqina.app\` (or leaves only the workspace folder under `Documents\` - confirm we never delete user docs)
- [ ] Tray icon disappears
- [ ] Credential Manager entry is removed (or, if not, `Sign out` did it before uninstall and we documented the split)

## J. Crash recovery

- [ ] Kill `python.exe` from Task Manager - Tauri shows a recovery path within a few seconds (e.g. helper restart prompt), consistent with current implementation
- [ ] Confirm recovery restores normal operation after accepting the prompt

## K. Accessibility smoke

- [ ] Tab order through onboarding is sensible
- [ ] Screen reader (NVDA) reads each step's heading and primary action
- [ ] System "high contrast" theme does not break the wizard

## L. Messaging gateway smoke

- [ ] **Settings → Messaging gateway**: Start / Stop responds; status text updates (poll every few seconds while on page)
- [ ] With **no** messaging vars in `kabuqina-home/.env`: gateway section explains eligibility / points to Settings or onboarding
- [ ] Configure **one** channel (Telegram token fastest; or QQ/Feishu/Weixin QR if test accounts exist); confirm `.env` keys appear
- [ ] **Start gateway** — remains running ≥10s (no immediate exit **1**); if instant failure, verify **`embeddedGatewayStartupSurvival`** hint and **`python/build_bundle.ps1`** ([troubleshooting §12](troubleshooting.md))
- [ ] Send a test message on that platform → assistant responds using configured LLM

## M. Study notebook (D-5, v0.4.0+)

Use a disposable owner/fixture. Export a recoverable backup before upgrade or delete tests;
never run destructive smoke against the tester's real learning history.

- [ ] `/study` canonicalizes root and space-only URLs to Flyleaf; direct links to Flyleaf,
  Plan, Learn, Evaluate, and Practice survive restart and keep the URL-selected course.
- [ ] With two courses, switch spaces and verify plan/drafts/detail/source audit/wrongbook/
  practice never show the other course's title, body, ids, or counts.
- [ ] Exercise the five lifecycle pages: plan resume/complete/skip; M5 content and draft
  lifecycle; wrongbook retry; card review; quiz/code/derivation practice; draft semantic review.
- [ ] Verify heading focus, `aria-current`, dialog focus trap/return, Escape, pure keyboard,
  dirty-practice leave confirmation, 200% zoom, reduced motion, light/dark, and zh/en at
  narrow, medium, and wide window sizes.
- [ ] Settings → Study improvement counts starts **off**. With it off, use Study and confirm
  no `kabuqina.telemetry.study-ia.aggregate.v1` value appears. Enable it and confirm stored
  evidence contains only approved event/page/action/success/count buckets—never fixture
  title/question/answer/id/source/URL. Disable it and confirm the aggregate is erased.
- [ ] Start with pre-D5 profile/flashcard/quiz localStorage fixtures. Confirm successful
  migration is idempotent across restart, failed profile migration preserves the old key,
  and migration failure/status export remains available.
- [ ] Confirm `/chat` STUDY mode has one notebook entry and no second profile/practice/draft
  mutation surface; knowledge-point chips still capture and explicitly retry refresh.
- [ ] Repeat the upgrade with A-R3's legacy app-data/config/credential names present; Study
  migration and persistence rename must both complete without overwriting each other.

---

## Sign-off

| Tester | OS              | Date | Build | Notes |
|--------|-----------------|------|-------|-------|
|        | Win 10 22H2     |      |       |       |
|        | Win 11 23H2     |      |       |       |
