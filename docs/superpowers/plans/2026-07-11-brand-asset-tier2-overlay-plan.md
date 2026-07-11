# A-R1b Implementation Plan — Tier 2 品牌资产私有 overlay

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans
> to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for
> tracking.

**Goal:** implement the Tier 2 (VSCodium-mode) brand asset pipeline decided in
[DECISIONS.md](../../../DECISIONS.md) (A-R1b, 2026-07-11): the private
repository `Kabuqina/kabuqina-mascot` becomes the only home of brand artwork
sources and of all future (v0.5+) scene art; the public monorepo builds a fully
functional **unbranded placeholder** app by default; official builds inject the
real assets via a build-time overlay step.

**Slice id:** A-R1b of the
[v0.4.0 development plan](2026-07-06-v0.4.0-development-plan.md).

**Non-goals:** recalling already-published artwork (git history, the six
dual-marked inline code files, the CSS cup — they stay, protected by
`LicenseRef-Kabuqina-Brand` + the owner's trademark track); any v0.5 scene art
production; CI/deploy-key integration (owner builds locally; revisit when CI
exists).

---

## Guardrails

- **No git history rewrite.** `Na_logo/` leaves HEAD via `git rm --cached`
  only. History stays intact; the moat covers future art.
- **Default build must stay green without the private repo.** A contributor
  clone with no `KABUQINA_BRAND_DIR` builds and runs the full app with
  placeholder assets under the **same filenames** — zero code changes, zero
  conditional imports.
- **Overlay never commits.** The overlay overwrites tracked placeholder files
  in the working tree only; the script refuses to run on a dirty target path
  and provides a restore mode. Real assets must never appear in a public
  commit again.
- **Do not touch the six dual-marked inline files**
  (`CompanionCupSvg.tsx` 等, see assets/brand/README.md) — already public,
  out of Tier 2 scope.
- **New-art discipline unchanged:** any new file embedding brand artwork in
  code still requires the `LicenseRef-Kabuqina-Brand` SPDX marker; v0.5 scene
  art files themselves go only to the private repo.
- Placeholder art must be genuinely neutral (generic mug/geometric mark, no
  Kabuqina geometry/palette) and Apache-2.0.
- Commit locally per task; do NOT push; stop for review at plan end.

---

### Task 1: 私有仓库定型（owner 操作 + 结构约定）

- [ ] **Step 1:** verify `Kabuqina/kabuqina-mascot` is **private** and owner
  has a local checkout (suggested: `D:\project\kabuqina-mascot`). Record the
  checkout path in progress notes.
- [ ] **Step 2:** move the full `Na_logo/` tree (masters, generator scripts,
  exports, screenshots) into the private repo, keeping
  `assets/brand/LICENSE` (All Rights Reserved) at its root, structured as:

```text
kabuqina-mascot/
  LICENSE                # All Rights Reserved (copied from assets/brand/LICENSE)
  README.md              # source-tree guide (moved/adapted from assets/brand/README.md)
  masters/               # Na_logo sources + generator scripts
  overlay/               # mirrors public-repo injection targets, pure copy:
    web/public/          #   kabuqina_*.svg/png, kabuqina_na_*.png, kabuqina_na.ico
    tauri/icons/         #   generated icon set (cargo tauri icon output)
```

- [ ] **Step 3:** regenerate/verify `overlay/` contents match today's shipped
  assets byte-for-byte (they are the current `web/public` + `tauri/icons`
  copies), so the first official overlay build is a no-op visually.

### Task 2: 公开仓库占位资产

**Files:**
- Add: `assets/brand/placeholder/generate_placeholder.py`（Apache-2.0,
  neutral geometry — plain mug silhouette + circled "N" mark, greyscale）
- Replace (same filenames): `web/public/kabuqina_*.{svg,png}`,
  `web/public/kabuqina_na_*.png`, `web/public/kabuqina_na.ico`,
  `tauri/icons/*`

- [ ] **Step 1:** write the placeholder generator; outputs every filename the
  app consumes today (enumerate from `assets/brand/README.md` tables). No new
  filenames, no code edits.
- [ ] **Step 2:** run it; regenerate `tauri/icons/` from the placeholder
  256-png via `cargo tauri icon`; commit the placeholder set. App must build
  and run showing the neutral identity.
- [ ] **Step 3:** grep-guard test (component test or script check) asserting
  no file under `web/public/` or `tauri/icons/` differs from the committed
  placeholder set at test time — catches an accidentally committed overlay.

### Task 3: overlay 注入脚本

**Files:**
- Add: `scripts/apply-brand-overlay.ps1`
- Edit: `scripts/package-portable-windows.ps1`, MSI/build docs

- [ ] **Step 1:** `apply-brand-overlay.ps1 -Apply`：requires
  `KABUQINA_BRAND_DIR`（or `-BrandDir`）；refuses if
  `git status --porcelain -- web/public tauri/icons` is non-empty；copies
  `overlay/**` over the working tree；prints an explicit "OFFICIAL BRANDED
  BUILD" banner. `-Restore`：`git checkout -- web/public tauri/icons`.
  Missing/invalid dir with `-Apply` = hard error, never a silent placeholder
  build.
- [ ] **Step 2:** wire the packaging entry points: portable zip and MSI build
  invocations gain an optional branded mode（apply → build → restore, restore
  runs in `finally`）. Dev (`dev.ps1`) stays placeholder-only by default;
  document `-Apply` for local visual checks.
- [ ] **Step 3:** smoke assertions in the packaging script: branded mode
  verifies a sentinel (e.g. hash of `kabuqina_mascot.svg` differs from
  placeholder hash) before sealing the artifact; placeholder mode verifies the
  opposite. Record both hashes in the script, not in docs.

### Task 4: `Na_logo/` 退场与文档收口

- [ ] **Step 1:** `git rm -r --cached Na_logo` + add `/Na_logo/` to
  `.gitignore`（local tree stays until owner confirms the private-repo copy,
  then owner deletes manually）.
- [ ] **Step 2:** rewrite `assets/brand/README.md`: source tree now lives in
  the private repo; document the placeholder story, the overlay step, and the
  unchanged inline-marker rule. Update `BRAND.md` / `NOTICE` references to
  `Na_logo/` paths accordingly.
- [ ] **Step 3:** update the v0.4.0 plan §6 A-R1b row and §2 Ring 1b section
  with a 完成记录 pointing at the DECISIONS.md entry and this plan.

### Task 5: 验证轮

- [ ] **Step 1:** clean-clone simulation（fresh worktree, no env var）:
  `npm run build` + `cargo tauri build` produce the placeholder app; grep
  the bundle for absence of the real-asset hashes.
- [ ] **Step 2:** branded round on owner machine: apply → build → restore;
  confirm working tree clean after restore and the artifact carries real
  branding.
- [ ] **Step 3:** record both rounds' evidence in progress notes; this plan's
  completion gates the start of any v0.5 scene-art production.
