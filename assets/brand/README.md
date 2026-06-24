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

## Related code (Apache-2.0)

The **CSS-rendered companion cup** in `web/src/` (e.g. `CompanionCup.tsx`) is
**Apache-2.0-licensed source code**. The **visual identity** it implements is still
proprietary — do not reuse the look for another product without permission.

## UI screenshots

Product screenshots (`Na_logo/chat_*.png`, etc.) are covered separately under
[assets/ui/](../ui/) — also All Rights Reserved.
