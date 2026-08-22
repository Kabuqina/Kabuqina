// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

/**
 * 体素渲染器（设计稿 `Kabuqina Voxel Assets` 第一轮 1b「厚块体素」）。
 *
 * 这里只有投影和材质，没有任何一件具体物件——物件在 `voxelArt.ts`，那份是品牌美术，
 * 授权跟 `kabuqinaBrandTokens.ts` 一样另算。
 *
 * 画法：物件写成 16×16×16 网格上的一串方块，每个方块只画三个面（顶 / 前 / 右），
 * 按 2:1 等轴投影摊平。Minecraft 从不画真圆，也从不画第四个面——这两条是这套
 * 图标读起来像 MC 物品栏的全部原因，别为了「更精细」去补面或补曲线。
 */

export type MaterialName =
  | "metal"
  | "metalDeep"
  | "glass"
  | "torch"
  | "ceramic"
  | "latte"
  | "handle"
  | "manila"
  | "woodDeep"
  | "book"
  | "coaster"
  | "stone"
  | "steam";

type Material = {
  /** 顶面 */
  t: string;
  /** 前面（朝向观察者的那面，光照下比顶面暗一档） */
  l: string;
  /** 右面（最暗的一档） */
  r: string;
  /** 整块的不透明度，只有热气用得上 */
  o?: number;
};

/**
 * 材质表就是这套美术的调色板，和 `kabuqinaBrandTokens` 同性质：色值写在 TS 里，
 * 因为导出静态 SVG 时没有文档可以解析 CSS 变量。
 *
 * 暗色主题只把「掉进黑木头里」的那几档抬亮，抬法在 index.css 的 `--vx-*`——
 * 抬的是同一个变量名，所以这里的字面值同时是浅色值与导出值的真值。
 */
export const VOXEL_MATERIALS: Record<MaterialName, Material> = {
  metal: { t: "#7A5A82", l: "#57315A", r: "#3F2247" },
  metalDeep: { t: "#6B4A73", l: "#4A2A50", r: "#33193A" },
  glass: { t: "#F0E9E4", l: "#DCD3CD", r: "#BFB4AE" },
  torch: { t: "#FFD08A", l: "#E5A54B", r: "#C4801F" },
  ceramic: { t: "#FFFCFA", l: "#F3EDE7", r: "#DDD0C6" },
  latte: { t: "#E8CFA8", l: "#D8B689", r: "#B8926A" },
  handle: { t: "#CDBEDD", l: "#B79FCD", r: "#8F75A8" },
  manila: { t: "#F5EAD8", l: "#E4D6BF", r: "#C7B79C" },
  woodDeep: { t: "#B89C8B", l: "#9C8070", r: "#7C6152" },
  book: { t: "#8E6A94", l: "#6E4370", r: "#50294F" },
  coaster: { t: "#F5EFFA", l: "#EAE1F1", r: "#D6C9E2" },
  stone: { t: "#9A9498", l: "#807A7E", r: "#645F63" },
  steam: { t: "#FFFFFF", l: "#FFFFFF", r: "#F4EEE8", o: 0.45 },
};

/** 描边＝方块之间的那道缝，不是轮廓线：厚块档每个面都描，细刻档不描。 */
export const VOXEL_EDGE = "#3B2A22";

/** `[x, y, z, 宽, 高, 深, 材质]`，坐标与尺寸都是网格格数。 */
export type Box = [number, number, number, number, number, number, MaterialName];

/** 贴在某个 z 切面上的平面色块（脸、气泡里的字迹）：`[x0, y0, x1, y1, z, 色, 不透明度?]`。 */
export type Decal = [number, number, number, number, number, string, number?];

export type Face = { p: string; c: string; o: number; s: string; w: number };

export type VoxelArt = {
  faces: Face[];
  /** SVG viewBox，已按内容裁好 */
  vb: string;
  /** 内容的原始宽高（投影单位），调用方按目标尺寸自己缩放 */
  aw: number;
  ah: number;
};

/* 等轴 2:1：横向一格 8，纵向一格 4，垂直一格 8。 */
const A = 8;
const B = 4;
const C = 8;

const pt = (x: number, y: number, z: number): [number, number] => [(x - z) * A, (x + z) * B - y * C];

/**
 * 浅色是字面值、暗色由 CSS 抬亮——所以每个面的 fill 都是「变量 + 字面值兜底」。
 * 导出静态 SVG 时没有文档定义这些变量，兜底值直接生效，同一份代码两用。
 */
const CSS_VAR = /[A-Z]/g;
function paint(name: MaterialName, face: "t" | "l" | "r", flat: boolean): string {
  const literal = VOXEL_MATERIALS[name][face];
  if (flat) return literal;
  const token = name.replace(CSS_VAR, (ch) => `-${ch.toLowerCase()}`);
  return `var(--vx-${token}-${face}, ${literal})`;
}

const poly = (pts: Array<[number, number]>): string =>
  pts.map((v) => `${v[0].toFixed(2)},${v[1].toFixed(2)}`).join(" ");

export type RenderOptions = {
  /** 厚块档为 true：每个面描一道深缝 */
  stroke?: boolean;
  /** 导出静态 SVG 时为 true：不吐 CSS 变量，只吐字面色值 */
  flat?: boolean;
};

/**
 * 画家算法：按「离观察者的远近」排序，后画的盖前画的。
 * 权重里 y 乘 1.5，因为等轴视图下抬高一格比往前一格更能挡住东西。
 */
function depth(b: Box): number {
  return b[0] + b[3] / 2 + (b[2] + b[5] / 2) + (b[1] + b[4] / 2) * 1.5;
}

export function isoFaces(boxes: Box[], opts: RenderOptions = {}): Face[] {
  const stroke = opts.stroke ? VOXEL_EDGE : "none";
  const width = opts.stroke ? 0.7 : 0;
  const flat = !!opts.flat;
  const out: Face[] = [];
  const quad = (pts: Array<[number, number]>, c: string, o?: number) =>
    out.push({ p: poly(pts), c, o: o == null ? 1 : o, s: stroke, w: width });

  for (const box of boxes.slice().sort((p, q) => depth(p) - depth(q))) {
    const [x, y, z, sx, sy, sz, name] = box;
    const o = VOXEL_MATERIALS[name].o;
    quad(
      [pt(x, y + sy, z), pt(x + sx, y + sy, z), pt(x + sx, y + sy, z + sz), pt(x, y + sy, z + sz)],
      paint(name, "t", flat),
      o,
    );
    quad(
      [pt(x, y + sy, z + sz), pt(x + sx, y + sy, z + sz), pt(x + sx, y, z + sz), pt(x, y, z + sz)],
      paint(name, "l", flat),
      o,
    );
    quad(
      [pt(x + sx, y + sy, z + sz), pt(x + sx, y + sy, z), pt(x + sx, y, z), pt(x + sx, y, z + sz)],
      paint(name, "r", flat),
      o,
    );
  }
  return out;
}

/** 贴花永远画在方块之后，也永远不描边——它是印上去的，不是又一块方块。 */
export function decalFaces(list: Decal[]): Face[] {
  return list.map(([x0, y0, x1, y1, z, c, o]) => ({
    p: poly([pt(x0, y1, z), pt(x1, y1, z), pt(x1, y0, z), pt(x0, y0, z)]),
    c,
    o: o == null ? 1 : o,
    s: "none",
    w: 0,
  }));
}

function fit(faces: Face[], pad: number): { vb: string; aw: number; ah: number } {
  let x0 = Infinity;
  let y0 = Infinity;
  let x1 = -Infinity;
  let y1 = -Infinity;
  for (const f of faces) {
    for (const p of f.p.split(" ")) {
      const [x, y] = p.split(",").map(Number);
      if (x < x0) x0 = x;
      if (x > x1) x1 = x;
      if (y < y0) y0 = y;
      if (y > y1) y1 = y;
    }
  }
  const aw = x1 - x0 + pad * 2;
  const ah = y1 - y0 + pad * 2;
  return { vb: `${(x0 - pad).toFixed(2)} ${(y0 - pad).toFixed(2)} ${aw.toFixed(2)} ${ah.toFixed(2)}`, aw, ah };
}

export type ItemOptions = RenderOptions & { decals?: Decal[] };

/** 一件物件＝方块 + 贴花 + 裁好的 viewBox。尺寸不在这里定，交给调用方按用途缩放。 */
export function voxelItem(boxes: Box[], opts: ItemOptions = {}): VoxelArt {
  const faces = isoFaces(boxes, opts).concat(decalFaces(opts.decals ?? []));
  return { faces, ...fit(faces, 2) };
}

/**
 * 平面像素字形：**不做等轴**。
 *
 * 窗口控制是系统 chrome，立体化会和内容争视觉——所以它们和物件共用 16×16 网格与
 * 硬边像素质感，但留在正面，笔画统一 2 单位。
 *
 * 视框固定成完整的 0..16，不裁到墨迹：「—」只占 12×2，裁过之后按高度放大就成了
 * 一根 66×11 的长条，三颗按钮立刻不同框。
 */
export type GlyphCell = [x: number, y: number, w: number, h: number];

export function pixelGlyph(cells: GlyphCell[]): VoxelArt {
  const faces: Face[] = cells.map(([x, y, w, h]) => ({
    p: poly([
      [x, y],
      [x + w, y],
      [x + w, y + h],
      [x, y + h],
    ]),
    // 字形的墨色归 CSS 管：悬停、关闭的红底、两个主题都靠它翻。
    c: "currentColor",
    o: 1,
    s: "none",
    w: 0,
  }));
  return { faces, vb: "0 0 16 16", aw: 16, ah: 16 };
}

/** 把一串方块整体平移，用来把杯子摆到杯垫上。 */
export function shift(boxes: Box[], dx: number, dy: number, dz: number): Box[] {
  return boxes.map((b) => [b[0] + dx, b[1] + dy, b[2] + dz, b[3], b[4], b[5], b[6]] as Box);
}
