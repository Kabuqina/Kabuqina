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

- [x] **Step 1:** verify `Kabuqina/kabuqina-mascot` is **private** and owner
  has a local checkout. *(2026-07-11: checkout at
  `D:\project\kabuqina-mascot`.)*
- [x] **Step 2:** move the full `Na_logo/` tree (masters, generator scripts,
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

- [x] **Step 3:** regenerate/verify `overlay/` contents match today's shipped
  assets byte-for-byte (they are the current `web/public` + `tauri/icons`
  copies), so the first official overlay build is a no-op visually.
  *(2026-07-11: overlay tree verified complete — 17 `web/public` files
  including `kabuqina_boot.svg`, full `tauri/icons` set, no course-material
  or `$RECYCLE.BIN` residue; copies were taken directly from the then-shipped
  working tree before the placeholder swap. Legacy exports were pruned and
  the tree was renamed `Na_logo/` → `masters/` during intake.)*

### Task 2: 公开仓库占位资产

**Files:**
- Add: `assets/brand/placeholder/generate_placeholder.py`（Apache-2.0,
  neutral geometry — plain mug silhouette + circled "N" mark, greyscale）
- Replace (same filenames): `web/public/kabuqina_*.{svg,png}`,
  `web/public/kabuqina_na_*.png`, `web/public/kabuqina_na.ico`,
  `tauri/icons/*`

- [x] **Step 1:** write the placeholder generator; outputs every filename the
  app consumes today (enumerate from `assets/brand/README.md` tables). No new
  filenames, no code edits. *(2026-07-11: generator at
  `assets/brand/placeholder/generate_placeholder.py`; canvas sizes mirror the
  shipped SVGs, geometry/palette all-new greyscale, `<title>Placeholder …` is
  the machine-checkable sentinel.)*
- [x] **Step 2:** run it; regenerate `tauri/icons/` from the placeholder
  source via `cargo tauri icon icons/_icon-1024.png` + tray copy; commit the
  placeholder set. *(2026-07-11: `npm run build` green — entry chunk
  1,568.75 kB / 471.59 kB gzip, StudyRoute still its own chunk; placeholder
  sentinel confirmed in `web/dist`; owner visually accepted the neutral
  identity.)*
- [x] **Step 3:** guard implemented as `apply-brand-overlay.ps1 -Check`
  (fails when `web/public` or `tauri/icons` differ from HEAD) — ran OK after
  the placeholder commit.

### Task 3: overlay 注入脚本

**Files:**
- Add: `scripts/apply-brand-overlay.ps1`
- Edit: `scripts/package-portable-windows.ps1`, MSI/build docs

- [x] **Step 1:** `apply-brand-overlay.ps1 -Apply`：requires
  `KABUQINA_BRAND_DIR`（or `-BrandDir`）；refuses if
  `git status --porcelain -- web/public tauri/icons` is non-empty；copies
  exactly the files present under the private `overlay/` tree（whitelist by
  construction — never a wildcard over the target dirs; `README.md`
  excluded）；prints an explicit "OFFICIAL BRANDED BUILD" banner.
  `-Restore`：`git checkout -- web/public tauri/icons`. `-Check`：fails if
  the two paths differ from HEAD（the Task 2 Step 3 guard）. Missing/invalid
  dir with `-Apply` = hard error, never a silent placeholder build.
- [x] **Step 2:** wire the packaging entry points. *(portable script gained
  the sentinel + `-ExpectBranded`; the official branded sequence is documented
  in `assets/brand/README.md` and the packaging script header; `dev.ps1`
  stays placeholder-only by default.)*
- [x] **Step 3:** smoke assertion in `package-portable-windows.ps1`: it reads
  `web/dist/kabuqina_mascot.svg`（what the exe build embedded）and matches the
  `<title>Placeholder` sentinel — default run refuses a branded tree,
  `-ExpectBranded` refuses a placeholder tree. Title sentinel replaces the
  originally planned hash bookkeeping（robuster across regeneration）.

### Task 4: `Na_logo/` 退场与文档收口

- [x] **Step 1:** `git rm -r --cached Na_logo` + `/Na_logo/` in `.gitignore`.
  *(2026-07-11: landed as `8b833bd1`; `git ls-files Na_logo` is empty. Local
  tree stays until the owner confirms the private-repo copy, then deletes it
  manually.)*
- [x] **Step 2:** rewrite `assets/brand/README.md`（Tier 2 layout: private
  masters + public placeholders + overlay/branded-build runbooks）; `BRAND.md`
  asset-locations updated. `NOTICE` deliberately unchanged: its `Na_logo/`
  coverage clause stays protective for historical checkouts.
- [x] **Step 3:** v0.4.0 plan §6 A-R1b row and §2 Ring 1b updated with the
  decision record（done in the A-R1b decision commit）.

### Task 5: 验证轮

- [ ] **Step 1:** clean-clone simulation（fresh worktree, no env var）:
  `npm run build` + `cargo tauri build` produce the placeholder app; grep
  the bundle for absence of the real-asset hashes.
- [ ] **Step 2:** branded round on owner machine: apply → build → restore;
  confirm working tree clean after restore and the artifact carries real
  branding. *(2026-07-11: apply → restore mechanics verified — banner shown,
  tree clean after restore; the full round with a rebuild in between is still
  owed at release time.)*
- [ ] **Step 3:** record both rounds' evidence in progress notes; this plan's
  completion gates the start of any v0.5 scene-art production.
