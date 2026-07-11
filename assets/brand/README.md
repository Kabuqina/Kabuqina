# Kabuqina brand assets (proprietary)

**License:** [LICENSE](./LICENSE) - All Rights Reserved. **Not Apache-2.0.**
**Copyright:** ladylydia · lilyreso@gmail.com · [github.com/ladylydia](https://github.com/ladylydia)

The authoritative artwork **masters** and generator scripts live in the
private `Kabuqina/kabuqina-mascot` repository. **This branch
(`stu-competition`) is a branded distribution:** it contains the real
Kabuqina brand assets as distribution copies under the build paths
(`web/public/`, `tauri/icons/`) so the competition deliverable runs with the
official visual identity.

Those build-path copies are **proprietary and All Rights Reserved**, just like
the masters. They are not neutral placeholders and are not licensed under
Apache-2.0. See [LICENSE](./LICENSE) and [BRAND.md](../../BRAND.md) for the
coverage rules.

## Asset locations in this branch

| Location | Role |
| -------- | ---- |
| `web/public/kabuqina_*` | App bundle copies consumed by the web shell and Tauri build |
| `tauri/icons/` | Generated app icons consumed by the Tauri bundler |
| `assets/brand/` | Brand documentation and legal files |
| `assets/ui/` | UI screenshots / promo images (also All Rights Reserved) |

The historical `Na_logo/` tree is no longer tracked in this branch, but
remains covered wherever it appears in git history.

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

**Rule going forward:** any new file embedding brand artwork MUST carry the
`LicenseRef-Kabuqina-Brand` SPDX marker.

## UI screenshots

Product screenshots (`assets/ui/chat_*.png`, etc.) are covered separately
under [assets/ui/](../ui/) — also All Rights Reserved.
