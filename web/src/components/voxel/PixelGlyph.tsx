// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useMemo } from "react";
import { pixelGlyph, type GlyphCell } from "./voxelRender";

/**
 * 窗口控制的像素字形（设计稿第四轮 4a）。
 *
 * 和体素物件同一张 16×16 网格、同样的硬边，但**留在正面不做等轴**：这几颗是系统
 * chrome，立体化会和内容争视觉。笔画统一 2 单位——lucide 那几根发丝摆在方块旁边太轻。
 *
 * 墨色走 `currentColor`，由 CSS 决定：悬停、关闭的红底、两个主题各自的墨都靠它翻。
 */

const MINIMIZE: GlyphCell[] = [[2, 7, 12, 2]];

/**
 * 展开照 `Maximize2` 的形来做：右上、左下两个角括号 + 一条对角线。
 * 不是方框——原来那颗 lucide 就是箭头，换成 □ 等于换了语义。
 */
const MAXIMIZE: GlyphCell[] = [
  [8, 2, 6, 2],
  [12, 2, 2, 6],
  [2, 12, 6, 2],
  [2, 8, 2, 6],
  [10, 4, 2, 2],
  [8, 6, 2, 2],
  [6, 8, 2, 2],
  [4, 10, 2, 2],
];

const CLOSE: GlyphCell[] = [
  [2, 2, 2, 2],
  [4, 4, 2, 2],
  [6, 6, 2, 2],
  [8, 8, 2, 2],
  [10, 10, 2, 2],
  [12, 12, 2, 2],
  [12, 2, 2, 2],
  [10, 4, 2, 2],
  [8, 6, 2, 2],
  [6, 8, 2, 2],
  [4, 10, 2, 2],
  [2, 12, 2, 2],
];

const GLYPHS = {
  minimize: MINIMIZE,
  maximize: MAXIMIZE,
  close: CLOSE,
} as const;

export type PixelGlyphName = keyof typeof GLYPHS;

export function PixelGlyph({ name, size }: { name: PixelGlyphName; size: number }) {
  const shape = useMemo(() => pixelGlyph(GLYPHS[name]), [name]);
  return (
    <svg
      viewBox={shape.vb}
      width={size}
      height={size}
      shapeRendering="crispEdges"
      aria-hidden
      focusable="false"
      style={{ display: "block" }}
    >
      {shape.faces.map((f, i) => (
        <polygon key={i} points={f.p} fill={f.c} />
      ))}
    </svg>
  );
}
