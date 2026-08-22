// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

/**
 * 把应用图标 / 托盘图标导成独立 SVG（`npm run export:voxel-icons`）。
 *
 * 导出走 `buildFlatVoxelArt`：文件里不能留 CSS 变量，脱离文档就没人解析它们。
 * 白天与夜间是两份文件——夜间那份把拿铁换成火把橙，等于杯子自己在发光。
 *
 * 只导 SVG。要 PNG / ICO 得再上一个栅格化器（sharp 或 resvg），仓库现在没有装。
 * 栅格化时记得对档：≥32px 用细节件，≤32px 用 `_chunky` 那两份。
 */

import { writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { buildFlatVoxelArt, type VoxelArtName } from "./voxelArt";

const publicDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../../public");

/**
 * 应用图标有日/夜与粗细档，另导出一份桌宠用的「杯垫 + 蒸汽」组合件。
 * 细节件缩到 16px 每个面不到 4px²，口沿和脸只会变成噪点——托盘/任务栏那一档必须换件。
 */
const TARGETS: Array<{ art: VoxelArtName; small: boolean; file: string; title: string }> = [
  {
    art: "appIcon",
    small: false,
    file: "kabuqina_voxel_appicon.svg",
    title: "Kabuqina app icon — voxel cup on a coaster",
  },
  {
    art: "appIconSteaming",
    small: false,
    file: "kabuqina_voxel_appicon_steam.svg",
    title: "Kabuqina companion — voxel cup, coaster, and steam",
  },
  {
    art: "appIconNight",
    small: false,
    file: "kabuqina_voxel_appicon_night.svg",
    title: "Kabuqina app icon, night — glowing latte",
  },
  {
    art: "appIcon",
    small: true,
    file: "kabuqina_voxel_appicon_chunky.svg",
    title: "Kabuqina app icon, chunky tier for 32px and below",
  },
  {
    art: "appIconNight",
    small: true,
    file: "kabuqina_voxel_appicon_chunky_night.svg",
    title: "Kabuqina app icon, chunky tier at night",
  },
];

for (const { art, small, file, title } of TARGETS) {
  const { faces, vb, aw, ah } = buildFlatVoxelArt(art, small);
  // 正方形画布：托盘和任务栏都按方形槽位裁，让物件自己在里面居中，
  // 而不是导出一个瘦长的 viewBox 交给宿主去拉伸。
  const side = Math.max(aw, ah);
  const [vx, vy, vw, vh] = vb.split(" ").map(Number);
  const box = `${(vx - (side - vw) / 2).toFixed(2)} ${(vy - (side - vh) / 2).toFixed(2)} ${side.toFixed(2)} ${side.toFixed(2)}`;
  const body = faces
    .map((f) => `<polygon points="${f.p}" fill="${f.c}" opacity="${f.o}" stroke="${f.s}" stroke-width="${f.w}"/>`)
    .join("\n");
  const svg = [
    '<?xml version="1.0" encoding="UTF-8"?>',
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="${box}" width="512" height="512" shape-rendering="crispEdges" role="img" aria-label="${title}">`,
    `<title>${title}</title>`,
    body,
    "</svg>",
    "",
  ].join("\n");
  const out = path.join(publicDir, file);
  writeFileSync(out, svg, "utf8");
  console.log(`Wrote ${out}`);
}
