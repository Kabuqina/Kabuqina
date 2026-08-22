// Component code: Copyright 2026 Kabuqina Contributors — Apache-2.0.
// Embedded Kabuqina brand artwork (voxel object design, block geometry, palette):
// Copyright (c) 2026 ladylydia — All Rights Reserved, NOT Apache-2.0.
// See assets/brand/LICENSE. Unbranded forks must replace the artwork.
// SPDX-License-Identifier: Apache-2.0 AND LicenseRef-Kabuqina-Brand

import { shift, voxelItem, type Box, type Decal, type ItemOptions, type VoxelArt } from "./voxelRender";

/**
 * 体素物件组（设计稿 `Kabuqina Voxel Assets` **1b 厚块体素** 定稿）。
 *
 * 全组共用一套网格、一个光照方向、一档描边——这才是「成套」的意思。要加新物件就照
 * 这里的写法堆方块，不要换投影、不要只给新物件加曲线。
 *
 * 为什么杯子是方的：Minecraft 里没有咖啡杯这件物品，最近的容器（桶、玻璃瓶、炼药锅、
 * 蜂蜜瓶）全是立方体加把手或嘴。方杯不是妥协，它就是这套语言里「一只杯子」的写法——
 * 把手和拿铁液面负责说明它是咖啡，形体保持方块。
 *
 * **每件物件有两档几何，小的那档不是缩小版。** 96px 件用 1–3 单位的小块堆细节；
 * 同一份 art 缩到导航栏尺寸，每个面只剩 3–5px，齿和灯罩必然糊成一团。所以小档是
 * 另外一件：块不小于 4 单位、齿数直接减半、杯身并成单块。分界见 `VOXEL_SMALL_MAX`。
 */

/** 厚块档统一描深缝。 */
const THICK: ItemOptions = { stroke: true };

/**
 * 换件的分界：目标最长边 ≤ 32px 用小档几何，超过用细节档。
 *
 * 32 这个数来自设计稿的规矩「块不小于 4 单位，缩放后每面 ≥6px」：导航栏那几个
 * （22–30px）在线下，3b 展示件（40px）与应用图标 96px 在线上。
 */
export const VOXEL_SMALL_MAX = 32;

/* ── 台灯：主题开关。灭＝玻璃灯泡，亮＝换成火把橙 ── */
type Bulb = "glass" | "torch";

/**
 * **中轴台灯**（第四轮重做）。悬臂构型已经废弃：悬臂的代价是灯头必须缩成一个远离
 * 灯杆的小方块，装不下灯罩轮廓，于是一路被读成凳子 / 托盘 / 字母 F。
 * 中轴把 x/z 收紧、y 拉满，灯罩才有地方铺开并收顶。
 *
 * 投影关系：屏幕宽 = 8×(x−z) 的跨度，屏幕高 = 4×(x+z) 跨度 + 8×y 跨度。
 * 本件 x−z ∈ [−10,10] → 宽 160；y 占满 16 格 → 高 176。**高必须大于宽**，
 * 否则读回台灯以外的东西。
 *
 * 剪影自下而上：底座 6 → 灯杆 2 → 发光沿 8 → 灯罩下沿 10（全件最宽）→ 收顶 6。
 * 收顶那块用薰衣草，和紫金属灯身拉开；发光沿比灯罩窄两格并紧贴罩口内侧，
 * 橙色是**沿着罩口出现**的，不是从罩前探出来。
 *
 * 台灯是全组唯一不分档的物件：这个剪影靠三段宽度差读，缩到 30px 也不糊。
 */
const lampBoxes = (bulb: Bulb): Box[] => [
  [5, 0, 5, 6, 1, 6, "metalDeep"],
  [7, 1, 7, 2, 9, 2, "metal"],
  [4, 10, 3, 8, 1, 12, bulb],
  [3, 11, 3, 10, 3, 10, "metal"],
  [5, 14, 5, 6, 2, 6, "handle"],
];

/* ── 小娜杯：吉祥物，也是品牌 mark ── */
const cupDetail: Box[] = [
  [4, 0, 4, 8, 7, 8, "ceramic"],
  [5, 7, 5, 6, 1, 6, "latte"],
  // 杯口那一圈瓷壁：四条边各一格，围出下沉的液面。
  [4, 7, 4, 1, 1, 8, "ceramic"],
  [11, 7, 4, 1, 1, 8, "ceramic"],
  [5, 7, 4, 6, 1, 1, "ceramic"],
  [5, 7, 11, 6, 1, 1, "ceramic"],
  // 把手：薰衣草色，三段折出来，正是 Q 的那一撇。
  [12, 3, 6, 2, 1, 3, "handle"],
  [13, 4, 6, 1, 2, 3, "handle"],
  [12, 6, 6, 2, 1, 3, "handle"],
];

/** 脸只在正面，永远只有这四块：两只眼睛 + 两团腮红。 */
const cupFace: Decal[] = [
  [5.6, 3.2, 6.8, 4.4, 12, "#43334A"],
  [9.2, 3.2, 10.4, 4.4, 12, "#43334A"],
  [4.4, 2.0, 5.6, 2.7, 12, "#C495A0", 0.7],
  [10.4, 2.0, 11.6, 2.7, 12, "#C495A0", 0.7],
];

/**
 * 小档杯：杯身并成单块、把手并成单块、口沿那一圈瓷壁不要了，也不贴脸。
 * 16px 下细节件每个面不到 4px²，那些一格宽的口沿只会变成杯子边上的一圈脏点。
 */
const cupChunky: Box[] = [
  [4, 1, 4, 8, 7, 8, "ceramic"],
  [5, 8, 5, 6, 1, 6, "latte"],
  [12, 3, 6, 2, 4, 4, "handle"],
];

const steamBoxes: Box[] = [
  [7, 9, 6, 2, 1, 2, "steam"],
  [6, 10, 8, 2, 1, 2, "steam"],
  [9, 11, 7, 2, 1, 2, "steam"],
];

/* ── 三个目的地图标：同一网格、同一光照，和台灯成套 ── */
const bookDetail: Box[] = [
  [2, 0, 3, 12, 2, 10, "book"],
  [3, 2, 4, 10, 2, 8, "manila"],
  [3, 4, 3, 11, 2, 9, "book"],
];

/** 小档：三层各加厚一格，书页那层才不至于在 22px 下被上下封面挤没。 */
const bookSmall: Box[] = [
  [2, 0, 3, 12, 3, 10, "book"],
  [3, 3, 4, 10, 2, 8, "manila"],
  [3, 5, 3, 11, 3, 9, "book"],
];

/**
 * 气泡是**近立方 + 底前戳出的尾巴**，不是一块横板——横板在等轴视图里读作路牌。
 * 薰衣草色：它和把手同族，说明「这是小娜在说话」。
 */
const chatDetail: Box[] = [
  [3, 3, 4, 10, 8, 7, "handle"],
  [5, 0, 9, 3, 3, 3, "handle"],
];

const chatSmall: Box[] = [
  [3, 3, 4, 10, 8, 8, "handle"],
  [5, 0, 10, 3, 3, 4, "handle"],
];

/** 气泡上的字迹：两块实墨，从不写真字。细线在这个尺寸下会被描边吃掉。 */
const chatDetailInk: Decal[] = [
  [4.4, 4.2, 11.6, 6.2, 11, "#3B2145", 0.95],
  [4.4, 8.0, 9.6, 10.0, 11, "#3B2145", 0.95],
];

const chatSmallInk: Decal[] = [
  [4.6, 4.4, 11.4, 6.6, 12, "#3B2145", 0.95],
  [4.6, 8.4, 9.4, 10.6, 12, "#3B2145", 0.95],
];

const gearDetail: Box[] = [
  [4, 0, 4, 8, 2, 8, "stone"],
  [1, 0, 6, 3, 2, 4, "metal"],
  [12, 0, 6, 3, 2, 4, "metal"],
  [6, 0, 1, 4, 2, 3, "metal"],
  [6, 0, 12, 4, 2, 3, "metal"],
  [5, 2, 5, 6, 1, 6, "metalDeep"],
];

/**
 * 小档齿轮**故意只有四颗齿**，而且每颗都是 4×4×4 的方块。
 * 八齿环在 28px 的盒子里把同样的面积切成三十来个面，每面掉到 13px²，比四齿糊得更狠——
 * 小尺寸不是缩小版，齿数本身要减。
 */
const gearSmall: Box[] = [
  [1, 0, 6, 4, 4, 4, "metal"],
  [11, 0, 6, 4, 4, 4, "metal"],
  [6, 0, 1, 4, 4, 4, "metal"],
  [6, 0, 11, 4, 4, 4, "metal"],
  // 盘面走瓷白、轴心走薰衣草：小档只剩四颗齿，齿与盘必须靠明度差分开，
  // 石头盘 + 深紫轴心在 28px 下会和齿糊成一坨。
  [5, 0, 5, 6, 5, 6, "ceramic"],
  // 轴心压在盘面上，让它读作齿轮而不是一枚方章。
  [6, 5, 6, 4, 1, 4, "handle"],
];

/* ── 应用图标 / 托盘 ──
   杯垫只裁到杯子的落脚范围（x3..15 / z3..13），整块接近正方——缩到 16px 还读得出
   是只杯子。杯垫铺满会让 16px 变成一个纯色方片。 */
const coaster: Box[] = [[3, 0, 3, 12, 1, 11, "coaster"]];

const litLatte = (boxes: Box[]): Box[] =>
  boxes.map((b) => (b[6] === "latte" ? ([b[0], b[1], b[2], b[3], b[4], b[5], "torch"] as Box) : b));

const appDetail: Box[] = coaster.concat(shift(cupDetail, 0, 1, 0));
/** 桌宠展示态：杯子落在杯垫上，同时保留蒸汽。 */
const appDetailSteaming: Box[] = appDetail.concat(shift(steamBoxes, 0, 1, 0));
/** 夜间态只把拿铁换成火把橙；头像尺寸下不加蒸汽，保持轮廓干净。 */
const appDetailLit: Box[] = coaster.concat(shift(litLatte(cupDetail), 0, 1, 0));
/** 杯子被杯垫垫高一格，脸也要跟着抬。 */
const appFace: Decal[] = cupFace.map((d) => [d[0], d[1] + 1, d[2], d[3] + 1, d[4], d[5], d[6]] as Decal);

/** 粗块档不冒热气也不贴脸：16px 下这两样都只是噪点。 */
const appChunky: Box[] = coaster.concat(cupChunky);
const appChunkyLit: Box[] = coaster.concat(litLatte(cupChunky));

export type VoxelArtName =
  | "lamp"
  | "lampLit"
  | "mark"
  | "markSteaming"
  | "study"
  | "chat"
  | "settings"
  | "appIcon"
  | "appIconSteaming"
  | "appIconNight";

function build(name: VoxelArtName, small: boolean, flat: boolean): VoxelArt {
  const base: ItemOptions = flat ? { stroke: true, flat: true } : THICK;
  const withDecals = (decals: Decal[]): ItemOptions => ({ ...base, decals });
  switch (name) {
    // 台灯和 mark 一样不分档：中轴剪影靠三段宽度差读，缩放不糊。
    case "lamp":
      return voxelItem(lampBoxes("glass"), base);
    case "lampLit":
      return voxelItem(lampBoxes("torch"), base);
    // 品牌 mark 没有小档：横条上它是 26px 的细节件，脸要看得见。
    case "mark":
      return voxelItem(cupDetail, withDecals(cupFace));
    case "markSteaming":
      return voxelItem(cupDetail.concat(steamBoxes), withDecals(cupFace));
    case "study":
      return voxelItem(small ? bookSmall : bookDetail, base);
    case "chat":
      return voxelItem(small ? chatSmall : chatDetail, withDecals(small ? chatSmallInk : chatDetailInk));
    case "settings":
      return voxelItem(small ? gearSmall : gearDetail, base);
    case "appIcon":
      return small ? voxelItem(appChunky, base) : voxelItem(appDetail, withDecals(appFace));
    case "appIconSteaming":
      return small ? voxelItem(appChunky, base) : voxelItem(appDetailSteaming, withDecals(appFace));
    case "appIconNight":
      return small ? voxelItem(appChunkyLit, base) : voxelItem(appDetailLit, withDecals(appFace));
  }
}

const cache = new Map<string, VoxelArt>();

/**
 * 几何与主题无关，同一档算一次就够。
 *
 * `size` 只用来挑档（见 `VOXEL_SMALL_MAX`），不参与缩放——缩放由调用方按最长边做，
 * 所以同一档的两个尺寸共用一份多边形。
 */
export function getVoxelArt(name: VoxelArtName, size: number): VoxelArt {
  const small = size <= VOXEL_SMALL_MAX;
  const key = `${name}|${small}`;
  let art = cache.get(key);
  if (!art) {
    art = build(name, small, false);
    cache.set(key, art);
  }
  return art;
}

/** 导出静态 SVG 用：CSS 变量在文档外解析不了，这一份只吐字面色值。 */
export function buildFlatVoxelArt(name: VoxelArtName, small: boolean): VoxelArt {
  return build(name, small, true);
}
