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

/* ── 抽屉里的字形 ──
   屉壁已经承担了纵深，所以屉里除了拉手全是平面墨迹；工具原来是 lucide 发丝，
   压在深木壁上太轻，换成同一 16 网格、2 单位笔画的像素件。 */

/** 开一张新纸。 */
const PLUS: GlyphCell[] = [[7, 2, 2, 12], [2, 7, 12, 2]];

/** 进行中：三条待办，每条一个方点 + 一道横线。 */
const LIST_TODO: GlyphCell[] = [
  [2, 2, 2, 2], [6, 2, 8, 2],
  [2, 7, 2, 2], [6, 7, 8, 2],
  [2, 12, 2, 2], [6, 12, 8, 2],
];

/** 定时任务：闹钟＝钟体 + 两只脚 + 两颗铃铛 + 指针。 */
const ALARM: GlyphCell[] = [
  [6, 1, 4, 2], [4, 3, 8, 2], [2, 5, 2, 6], [12, 5, 2, 6],
  [4, 11, 8, 2], [6, 13, 4, 2],
  [7, 5, 2, 4], [9, 8, 2, 2],
  [1, 1, 2, 2], [13, 1, 2, 2],
];

/** 导出：一支向下的箭头落在托底上。 */
const DOWNLOAD: GlyphCell[] = [
  [7, 2, 2, 6], [4, 7, 2, 2], [10, 7, 2, 2], [6, 9, 4, 2], [2, 12, 12, 2],
];

/**
 * 收起 / 展开上下文标题：同一个外框，横条在顶＝收起，在中＝展开。
 * 顶那档照 `PanelTopClose` 来；展开那档设计稿没画，按同一构型把横条下移两格。
 */
const CONTEXT_HIDE: GlyphCell[] = [
  [2, 2, 12, 2], [2, 12, 12, 2], [2, 4, 2, 8], [12, 4, 2, 8], [4, 6, 8, 2],
];
const CONTEXT_SHOW: GlyphCell[] = [
  [2, 2, 12, 2], [2, 12, 12, 2], [2, 4, 2, 8], [12, 4, 2, 8], [4, 8, 8, 2],
];

const GLYPHS = {
  minimize: MINIMIZE,
  maximize: MAXIMIZE,
  close: CLOSE,
  plus: PLUS,
  listTodo: LIST_TODO,
  alarm: ALARM,
  download: DOWNLOAD,
  contextHide: CONTEXT_HIDE,
  contextShow: CONTEXT_SHOW,
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
