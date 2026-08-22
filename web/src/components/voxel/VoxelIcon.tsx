// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useMemo } from "react";
import { getVoxelArt, type VoxelArtName } from "./voxelArt";

/**
 * 一件体素物件的 SVG。
 *
 * `size` 是**最长边**的目标像素，不是宽也不是高——物件各有各的长宽比（台灯高、气泡宽），
 * 按最长边对齐才能让一条横条上的东西看着一样大。
 *
 * 它同时决定用哪一档几何：小尺寸拿到的是**另一件** art（块更大、齿更少），不是同一件
 * 缩小。见 `VOXEL_SMALL_MAX`。所以改 size 有可能连形体一起换掉，调之前先看那条分界。
 *
 * `shape-rendering="crispEdges"` 不能去掉：这套图形靠像素对齐的硬边读作方块，
 * 一开抗锯齿就变成一坨软糖。
 */
export type VoxelIconProps = {
  art: VoxelArtName;
  size: number;
};

export function VoxelIcon({ art, size }: VoxelIconProps) {
  const shape = useMemo(() => {
    const { faces, vb, aw, ah } = getVoxelArt(art, size);
    const scale = size / Math.max(aw, ah);
    return { faces, vb, w: Math.round(aw * scale), h: Math.round(ah * scale) };
  }, [art, size]);

  return (
    <svg
      viewBox={shape.vb}
      width={shape.w}
      height={shape.h}
      shapeRendering="crispEdges"
      aria-hidden
      focusable="false"
      /* 台灯亮起时的暖斑是 drop-shadow，会画到 viewBox 之外。 */
      style={{ display: "block", overflow: "visible" }}
    >
      {shape.faces.map((f, i) => (
        <polygon key={i} points={f.p} fill={f.c} opacity={f.o} stroke={f.s} strokeWidth={f.w} />
      ))}
    </svg>
  );
}
