// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { describe, expect, it } from "vitest";
import { buildFlatVoxelArt, getVoxelArt, VOXEL_SMALL_MAX, type VoxelArtName } from "./voxelArt";
import { VOXEL_EDGE, VOXEL_MATERIALS } from "./voxelRender";

const ALL: VoxelArtName[] = [
  "lamp",
  "lampLit",
  "mark",
  "markSteaming",
  "study",
  "chat",
  "settings",
  "appIcon",
  "appIconSteaming",
  "appIconNight",
];

/** 有小档几何的物件。 */
const TWO_TIER: VoxelArtName[] = ["study", "chat", "settings", "appIcon", "appIconSteaming", "appIconNight"];

/**
 * 不分档的物件，两个尺寸必须拿到同一件：
 * mark 在横条上是 26px 的细节件，脸要看得见；台灯的中轴剪影靠三段宽度差读，缩放不糊。
 */
const ONE_TIER: VoxelArtName[] = ["mark", "markSteaming", "lamp", "lampLit"];

const SMALL = VOXEL_SMALL_MAX;
const BIG = VOXEL_SMALL_MAX + 1;

describe("voxel art", () => {
  it("gives every object a non-degenerate, finite viewBox at both tiers", () => {
    for (const name of ALL) {
      for (const size of [SMALL, BIG]) {
        const art = getVoxelArt(name, size);
        const at = `${name}@${size}`;
        expect(art.faces.length, at).toBeGreaterThan(0);
        expect(Number.isFinite(art.aw) && art.aw > 0, at).toBe(true);
        expect(Number.isFinite(art.ah) && art.ah > 0, at).toBe(true);
        expect(art.vb, at).not.toMatch(/NaN|Infinity/);
      }
    }
  });

  it("swaps in a different object below the small threshold, not the same one shrunk", () => {
    // 这条是整套小档存在的理由：细节件缩到导航栏尺寸每面只剩 3–5px，齿和灯罩必然糊掉。
    for (const name of TWO_TIER) {
      const small = getVoxelArt(name, SMALL);
      const detail = getVoxelArt(name, BIG);
      expect(small.faces.map((f) => f.p), name).not.toEqual(detail.faces.map((f) => f.p));
    }
    for (const name of ONE_TIER) {
      expect(getVoxelArt(name, SMALL).faces, name).toEqual(getVoxelArt(name, BIG).faces);
    }
  });

  it("keeps the small gear at four teeth so each face survives the nav bar", () => {
    // 八齿环在 28px 盒子里把同样面积切成三十来个面，比四齿糊得更狠。
    const small = getVoxelArt("settings", SMALL);
    const detail = getVoxelArt("settings", BIG);
    // 每个方块画三个面：小档 4 齿 + 盘 + 轴心 = 6 块，细节档 4 齿 + 盘 + 轴心 = 6 块，
    // 但小档的块更大——用面积而不是块数来钉这条。
    const minFace = (a: typeof small) =>
      Math.min(...a.faces.map((f) => {
        const pts = f.p.split(" ").map((p) => p.split(",").map(Number));
        const xs = pts.map((p) => p[0]);
        const ys = pts.map((p) => p[1]);
        return (Math.max(...xs) - Math.min(...xs)) * (Math.max(...ys) - Math.min(...ys));
      }));
    expect(minFace(small) / small.aw ** 2).toBeGreaterThan(minFace(detail) / detail.aw ** 2);
  });

  it("drops the face decals from the chunky app icon", () => {
    // 16px 下脸只是噪点：贴花是唯一不描边的面，粗块档一个都不该有。
    expect(getVoxelArt("appIcon", SMALL).faces.filter((f) => f.s === "none")).toHaveLength(0);
    expect(getVoxelArt("appIconNight", SMALL).faces.filter((f) => f.s === "none")).toHaveLength(0);
    expect(getVoxelArt("appIcon", BIG).faces.filter((f) => f.s === "none")).toHaveLength(4);
  });

  it("paints in-app faces through --vx-* so the dark theme can lift them", () => {
    // 每个方块面都必须是「变量 + 字面值兜底」：变量给暗色补光留口子，
    // 兜底值让同一份代码在没有文档的导出场景里也画得出来。齿轮全是方块、没有贴花。
    const faces = getVoxelArt("settings", BIG).faces;
    expect(faces.length).toBeGreaterThan(0);
    for (const f of faces) {
      expect(f.c).toMatch(/^var\(--vx-[a-z-]+-[tlr], #[0-9A-F]{6}\)$/);
    }
  });

  it("exports flat colours only — CSS variables do not resolve outside a document", () => {
    for (const name of ALL) {
      for (const small of [true, false]) {
        for (const f of buildFlatVoxelArt(name, small).faces) {
          expect(f.c, `${name} ${f.c}`).not.toMatch(/var\(/);
        }
      }
    }
  });

  it("lights the lamp by swapping the bulb material, not by recolouring the icon", () => {
    for (const small of [true, false]) {
      const off = buildFlatVoxelArt("lamp", small);
      const on = buildFlatVoxelArt("lampLit", small);
      // 几何一模一样：亮灭之间形体不动。
      expect(on.faces.map((f) => f.p)).toEqual(off.faces.map((f) => f.p));
      const colours = (a: typeof on) => new Set(a.faces.map((f) => f.c));
      expect(colours(off).has(VOXEL_MATERIALS.glass.t)).toBe(true);
      expect(colours(off).has(VOXEL_MATERIALS.torch.t)).toBe(false);
      expect(colours(on).has(VOXEL_MATERIALS.torch.t)).toBe(true);
    }
  });

  it("keeps both app icon tiers close to square so 16px still reads as a cup", () => {
    // 杯垫裁到杯子的落脚范围就是为了这个：铺满杯垫的话缩到 16px 只剩一块纯色方片。
    for (const size of [SMALL, BIG]) {
      const { aw, ah } = getVoxelArt("appIcon", size);
      expect(Math.max(aw, ah) / Math.min(aw, ah), `@${size}`).toBeLessThan(1.25);
    }
  });

  it("strokes the blocks but never the decals", () => {
    const chat = buildFlatVoxelArt("chat", false);
    expect(chat.faces.some((f) => f.s === VOXEL_EDGE && f.w > 0)).toBe(true);
    // 气泡上的字迹是印上去的，描了边就成了又一块方块——不描边的面正好就是它们。
    const ink = chat.faces.filter((f) => f.s === "none");
    expect(ink).toHaveLength(2);
    for (const f of ink) expect(f.w).toBe(0);
  });
});
