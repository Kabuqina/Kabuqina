# Kabuqina brand assets (proprietary)

**License:** [LICENSE](./LICENSE) - All Rights Reserved. **Not Apache-2.0.**
**Copyright:** ladylydia · lilyreso@gmail.com · [github.com/ladylydia](https://github.com/ladylydia)

These paths in the monorepo ship **preview / distribution copies** of the
Kabuqina visual identity. Do not treat them as freely reusable clip art.

## Directories

| Location | Role |
| -------- | ---- |
| `Na_logo/` | **Source tree** — authoritative copies, exports, and generator scripts |
| `web/public/` | **App bundle copies** — `kabuqina_*` SVG/PNG consumed by the web shell and Tauri build |
| `tauri/icons/` | **Generated app icons** — from `web/public/kabuqina_na_256.png` via `cargo tauri icon` |

Keep `Na_logo/` and `web/public/` in sync when changing marks. Regenerate with
the scripts below where noted.

## Vector masters (SVG)

Generated from `Na_logo/generate_mascot.py` and `Na_logo/generate_mascot_scenes.py`.
Copied to `web/public/` on each run (except where noted).

| File | Contents |
| ---- | -------- |
| `kabuqina_mascot.svg` | Coffee-cup mascot — **cup-only vector master** (avatar, icons) |
| `kabuqina_coaster_hero.svg` | Gingham coaster only — chat hero size, tilted |
| `kabuqina_coaster_pill.svg` | Gingham coaster only — companion pill size, tilted |
| `kabuqina_hero_scene.svg` | Chat empty-state composite — cup + hero coaster + ground/contact shadows + steam |
| `kabuqina_pill_scene.svg` | Companion pill composite — cup + pill coaster + shadows + steam |
| `kabuqina_social_preview.svg` | Social / OG banner — 1280×640, white background, no steam |

**Note:** The live app still renders chat hero and companion pill with **CSS**
(`CompanionCup.tsx`, `index.css`). Scene SVGs are **material / export** assets;
geometry is tuned in `generate_mascot_scenes.py` (`cup_foot_nudge_down_rem`, etc.).

## Raster exports

| Pattern | Contents | Sync |
| ------- | -------- | ---- |
| `kabuqina_mascot_{64,128,256,512}.png` | Mascot PNGs (transparent) | `Na_logo/` + `web/public/` |
| `kabuqina_na_{16,32,48,128,256}.png` | **Na** app-mark PNGs | `Na_logo/` + `web/public/` |
| `kabuqina_na.ico` | Windows ICO (multi-size) | `Na_logo/` + `web/public/` |
| `kabuqina_social_preview.png` | Social / OG raster (legacy reference) | `Na_logo/` only |
| `mascot.png` | Legacy full mascot export | `Na_logo/` only |
| `mascot_wide.png` | Wide-layout mascot export | `Na_logo/` only |
| `mascot_round_coaster.png` | Round avatar / coaster crop | `Na_logo/` only |
| `mascot_square_standard.png` | Square avatar — standard crop | `Na_logo/` only |
| `mascot_square_strong.png` | Square avatar — tighter crop | `Na_logo/` only |
| `mascot_squre_coaster.*` | Coaster-style square crop (`.jpg` in `Na_logo/`, `.png` in `web/public/`) | mixed |

## Generator scripts (`Na_logo/`) — All Rights Reserved

These Python files encode mascot geometry, palette, and export pipelines. They
are **proprietary brand tooling**, not Apache-2.0-licensed application code:

| Script | Purpose |
| ------ | ------- |
| `generate_mascot.py` | `kabuqina_mascot.svg` + `kabuqina_mascot_*.png` → copies to `web/public/` |
| `generate_mascot_scenes.py` | All scene/coaster SVGs above + `kabuqina_social_preview.svg` → copies to `web/public/` |
| `generate_na_mark.py` | `kabuqina_na_*.png` + `kabuqina_na.ico` → copies to `web/public/` |
| `fix_mascot_png_alpha.py` | Remove checkerboard / flat backdrop from legacy mascot PNGs (in-place) |

From repo root:

```bash
python Na_logo/generate_mascot.py
python Na_logo/generate_mascot_scenes.py
python Na_logo/generate_na_mark.py
```

## Inline copies in code (dual-marked)

The mascot artwork also exists as **inline vector/CSS renderings inside
source files**. Those files carry the dual SPDX expression
`Apache-2.0 AND LicenseRef-Kabuqina-Brand`: the component CODE is
Apache-2.0, the embedded ARTWORK (geometry, palette, composition) is
proprietary under [LICENSE](./LICENSE). Current set:

| File | Embedded artwork |
| ---- | ---------------- |
| `web/src/components/brand/CompanionCupSvg.tsx` | Cup vector |
| `web/src/components/brand/KabuqinaCoasterSvg.tsx` | Coaster vector |
| `web/src/components/brand/KabuqinaSceneSvg.tsx` | Scene composite |
| `web/src/components/brand/kabuqinaBrandTokens.ts` | Palette + geometry tokens |
| `web/src/components/CompanionCup.tsx` | CSS-rendered cup |
| `web/src/components/CompanionPillScene.tsx` | Pill scene composition |
| `web/src/index.css` (`.kq-companion-cup*` block) | CSS mascot rules (banner comment marks the block) |

**Rule going forward:** any new file embedding brand artwork (including the
v0.5 desk/notebook/whiteboard scene assets) MUST carry the
`LicenseRef-Kabuqina-Brand` SPDX marker — coverage follows the marker and
the directories, not this table. Unbranded forks may keep the Apache code
and replace the artwork data.

## UI screenshots

Product screenshots (`Na_logo/chat_*.png`, etc.) are covered separately under
[assets/ui/](../ui/) — also All Rights Reserved.
