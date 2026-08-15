#!/usr/bin/env python3
# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0
"""Generate neutral placeholder brand assets (Tier 2 unbranded default).

Writes every brand-asset filename the app consumes — a plain grey mug with no
face and a rounded-square "Q" tile — so a public clone builds and runs without
access to the private artwork repository. Official builds overlay the real
Kabuqina artwork on top of these files; see
docs/superpowers/plans/2026-07-11-brand-asset-tier2-overlay-plan.md.

The geometry and palette here are deliberately generic. Do NOT port the
proprietary Kabuqina cup geometry, palette, or composition into this file.

Usage (from repo root):

    python assets/brand/placeholder/generate_placeholder.py

Then regenerate the Tauri icon set from the placeholder source:

    cd tauri; cargo tauri icon icons/_icon-1024.png
    Copy-Item -Force ..\\web\\public\\kabuqina_qi_32.png .\\icons\\tray.png
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

REPO = Path(__file__).resolve().parents[3]
WEB_PUBLIC = REPO / "web" / "public"
TAURI_ICONS = REPO / "tauri" / "icons"

GREY = {
    "mug_top": "#dedede",
    "mug_bottom": "#bcbcbc",
    "mug_outline": "#8a8a8a",
    "rim": "#ececec",
    "handle": "#a6a6a6",
    "coaster_fill": "#ededed",
    "coaster_edge": "#cfcfcf",
    "shadow": "rgba(0, 0, 0, 0.12)",
    "tile_top": (110, 110, 110),
    "tile_bottom": (86, 86, 86),
    "tile_text": (245, 245, 245),
}

MARK_SIZES = (16, 32, 48, 128, 256)
MASCOT_SIZES = (64, 128, 256, 512)


# ── SVG pieces ─────────────────────────────────────────────────────────── #

def _mug_svg_group(prefix: str) -> tuple[str, str]:
    """A plain 100×100 mug: flat-top body, rim bar, ear handle. No face."""
    defs = f"""
    <linearGradient id="{prefix}mugGrad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="{GREY['mug_top']}"/>
      <stop offset="100%" stop-color="{GREY['mug_bottom']}"/>
    </linearGradient>"""
    shapes = f"""
  <path d="M 74 44 C 92 46 92 64 74 66" fill="none" stroke="{GREY['handle']}"
        stroke-width="4" stroke-linecap="round"/>
  <path d="M 24 30 L 24 70 Q 24 82 36 82 L 64 82 Q 76 82 76 70 L 76 30 Z"
        fill="url(#{prefix}mugGrad)" stroke="{GREY['mug_outline']}" stroke-width="1"/>
  <rect x="20" y="22" width="60" height="12" rx="6" fill="{GREY['rim']}"
        stroke="{GREY['mug_outline']}" stroke-width="0.8"/>"""
    return defs, shapes


def _svg(view_w: float, view_h: float, label: str, body: str, *, background: str | None = None) -> str:
    bg = f'\n  <rect x="0" y="0" width="{view_w:g}" height="{view_h:g}" fill="{background}"/>' if background else ""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {view_w:g} {view_h:g}" role="img" aria-label="{label}">
  <title>{label}</title>{bg}{body}
</svg>
"""


def _coaster_rect(cx: float, cy: float, size: float) -> str:
    half = size / 2
    return f"""
  <rect x="{cx - half:.2f}" y="{cy - half * 0.72:.2f}" width="{size:.2f}" height="{size * 0.72:.2f}"
        rx="{size * 0.2:.2f}" fill="{GREY['coaster_fill']}" stroke="{GREY['coaster_edge']}" stroke-width="2"/>"""


def _scene_body(prefix: str, view_w: float, view_h: float) -> str:
    """Coaster + shadow + mug, centered; mug drawn in a scaled 100×100 group."""
    mug_scale = view_h / 130
    mug_x = view_w / 2 - 50 * mug_scale
    mug_y = view_h * 0.98 - 90 * mug_scale
    defs, shapes = _mug_svg_group(prefix)
    coaster = _coaster_rect(view_w / 2, view_h * 0.72, view_h * 0.62)
    return f"""
  <defs>{defs}
  </defs>{coaster}
  <ellipse cx="{view_w / 2:.2f}" cy="{view_h * 0.88:.2f}" rx="{view_h * 0.28:.2f}" ry="{view_h * 0.045:.2f}"
           fill="{GREY['shadow']}"/>
  <g transform="translate({mug_x:.2f} {mug_y:.2f}) scale({mug_scale:.4f})">{shapes}
  </g>"""


# ── PNG pieces (Pillow) ────────────────────────────────────────────────── #

def _render_mug_png(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    s = size / 100.0

    def box(x: float, y: float, w: float, h: float) -> tuple[float, float, float, float]:
        return (x * s, y * s, (x + w) * s, (y + h) * s)

    draw.arc(box(58, 40, 34, 28), start=-75, end=75, fill=GREY["handle"], width=max(2, round(4 * s)))
    draw.rounded_rectangle(box(24, 30, 52, 52), radius=12 * s, fill=GREY["mug_top"],
                           outline=GREY["mug_outline"], width=max(1, round(s)))
    draw.rectangle(box(24, 30, 52, 14), fill=GREY["mug_top"])  # flat top
    draw.rounded_rectangle(box(20, 22, 60, 12), radius=6 * s, fill=GREY["rim"],
                           outline=GREY["mug_outline"], width=max(1, round(0.8 * s)))
    return img


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in (Path(r"C:\Windows\Fonts\segoeuib.ttf"), Path(r"C:\Windows\Fonts\arialbd.ttf")):
        if path.is_file():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def _render_tile_png(size: int) -> Image.Image:
    """Rounded-square greyscale tile with a centered Q — the placeholder app mark."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    base = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    px = base.load()
    top, bottom = GREY["tile_top"], GREY["tile_bottom"]
    for y in range(size):
        t = y / max(size - 1, 1)
        row = tuple(round(top[i] * (1 - t) + bottom[i] * t) for i in range(3))
        for x in range(size):
            px[x, y] = (*row, 255)
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size - 1, size - 1),
                                           radius=max(2, round(size * 0.22)), fill=255)
    img = Image.composite(base, img, mask)

    draw = ImageDraw.Draw(img)
    font = _load_font(max(8, round(size * 0.58)))
    bbox = draw.textbbox((0, 0), "Q", font=font)
    tx = (size - (bbox[2] - bbox[0])) / 2 - bbox[0]
    ty = (size - (bbox[3] - bbox[1])) / 2 - bbox[1]
    draw.text((tx, ty), "Q", font=font, fill=GREY["tile_text"])
    return img


# ── outputs ────────────────────────────────────────────────────────────── #

def write_outputs() -> None:
    WEB_PUBLIC.mkdir(parents=True, exist_ok=True)
    TAURI_ICONS.mkdir(parents=True, exist_ok=True)

    mug_defs, mug_shapes = _mug_svg_group("")
    (WEB_PUBLIC / "kabuqina_mascot.svg").write_text(
        _svg(100, 100, "Placeholder mug", f"\n  <defs>{mug_defs}\n  </defs>{mug_shapes}"),
        encoding="utf-8",
    )
    for size in MASCOT_SIZES:
        _render_mug_png(size).save(WEB_PUBLIC / f"kabuqina_mascot_{size}.png", optimize=True)

    tiles = [_render_tile_png(size) for size in MARK_SIZES]
    for size, tile in zip(MARK_SIZES, tiles):
        tile.save(WEB_PUBLIC / f"kabuqina_qi_{size}.png", optimize=True)
    tiles[-1].save(WEB_PUBLIC / "kabuqina_qi.ico", format="ICO",
                   sizes=[(s, s) for s in MARK_SIZES], append_images=tiles[:-1])
    _render_tile_png(1024).save(TAURI_ICONS / "_icon-1024.png", optimize=True)

    coasters = (
        ("kabuqina_coaster_hero.svg", 909.50, 673.67, "Placeholder hero coaster"),
        ("kabuqina_coaster_pill.svg", 674.90, 488.28, "Placeholder pill coaster"),
    )
    for name, w, h, label in coasters:
        (WEB_PUBLIC / name).write_text(
            _svg(w, h, label, _coaster_rect(w / 2, h / 2, min(w, h) * 0.9)), encoding="utf-8"
        )

    scenes = (
        ("kabuqina_hero_scene.svg", 775, 685, "Placeholder hero scene", None),
        ("kabuqina_pill_scene.svg", 620, 548, "Placeholder pill scene", None),
        ("kabuqina_boot.svg", 1280, 640, "Placeholder boot scene", None),
        ("kabuqina_social_preview.svg", 1280, 640, "Placeholder social preview", "#ffffff"),
    )
    for name, w, h, label, background in scenes:
        prefix = name.removesuffix(".svg") + "_"
        (WEB_PUBLIC / name).write_text(
            _svg(w, h, label, _scene_body(prefix, w, h), background=background),
            encoding="utf-8",
        )

    print(f"Placeholder assets written to {WEB_PUBLIC} and {TAURI_ICONS / '_icon-1024.png'}")
    print("Next: cd tauri; cargo tauri icon icons/_icon-1024.png; then copy "
          "web/public/kabuqina_qi_32.png over tauri/icons/tray.png")


def main() -> int:
    write_outputs()
    return 0


if __name__ == "__main__":
    sys.exit(main())
