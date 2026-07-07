# Brand & asset licensing (dual license)

Kabuqina uses a **dual license** model:

| What | License | Where |
| ---- | ------- | ----- |
| **Kabuqina source code** (Rust, Python policy layer, web app, scripts, docs as text) | [Apache-2.0](./LICENSE) | Repository root |
| **Brand assets** (name, logos, mascot, scene/coaster SVGs, icons, `Na_logo/` generator scripts) | [All Rights Reserved](./assets/brand/LICENSE) | [assets/brand/](./assets/brand/) |
| **UI screenshots / promo images** | [All Rights Reserved](./assets/ui/LICENSE) | [assets/ui/](./assets/ui/) |
| **Hermes Agent snapshot** | MIT (upstream, unchanged) | [hermes_core/LICENSE](./hermes_core/LICENSE) |

## Quick rules

- You **may** fork and modify the **Kabuqina code** under Apache-2.0 terms (include copyright notice and NOTICE).
- You **may not** rebrand a fork using Kabuqina logos, the 卡布奇娜 / Kabuqina name as
  your product identity, or the coffee-cup mascot without **written permission**.
- Running an **official, unmodified** build from us does not grant rights to extract
  and reuse brand files elsewhere.

## Asset locations

Brand and UI files currently live in their build paths (`web/public/`, `Na_logo/`,
`tauri/icons/`). Legal coverage is defined by [assets/brand/LICENSE](./assets/brand/LICENSE)
— the covered directories, the `LicenseRef-Kabuqina-Brand` SPDX marker, and the
artwork-as-a-work clause — not by directory name alone.

The mascot's **inline renderings in code** (`web/src/components/brand/*`,
`CompanionCup.tsx`, `CompanionPillScene.tsx`, and the `.kq-companion-cup*`
CSS block in `web/src/index.css`) are dual-marked
`Apache-2.0 AND LicenseRef-Kabuqina-Brand`: the component code is open, the
embedded artwork is proprietary. Any future file embedding brand artwork
(including the v0.5 desk / notebook / whiteboard scene) must carry the same
marker.

## Copyright holder (brand & UI assets)

**ladylydia** — [github.com/ladylydia](https://github.com/ladylydia) · lilyreso@gmail.com

## Licensing contact

Email: **lilyreso@gmail.com**  
GitHub: [@ladylydia](https://github.com/ladylydia) · issues on [Kabuqina](https://github.com/Kabuqina/Kabuqina/issues) (label: licensing)
