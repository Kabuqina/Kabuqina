// Module code: Copyright 2026 Kabuqina Contributors — Apache-2.0.
// The assets this module points at are Kabuqina brand artwork:
// Copyright (c) 2026 ladylydia — All Rights Reserved, NOT Apache-2.0.
// See assets/brand/LICENSE. Unbranded forks must replace the artwork —
// this table is the single place they need to repoint.
// SPDX-License-Identifier: Apache-2.0 AND LicenseRef-Kabuqina-Brand

/**
 * 美术换装接缝（pre-art frontend）。
 *
 * 当前前端是 pre-art：材质与色彩走 `--kq-*` 变量层，图形走这张表。最终插画、
 * 位图纹理和小娜立绘都还没接入——按 CTL-A06b 的规矩，缺美术时用现有 DOM/CSS/Lucide
 * 中性骨架，不摆空图片框、不摆灰色占位块、不预留"以后放插画"的空区。占位是**接缝**，
 * 不是**空洞**：删掉一个区域用户照样能完成任务，它现在就不该在（信息原则 §7.2）。
 *
 * 美术资源到位时**只改这张表**，不动调用点。每一项都记它是什么物件、现在是什么、
 * 以及换装时的尺寸契约——契约不写下来，换图那天就得靠猜。
 *
 * 命名说物件，不说位置（物件词汇表 §7）：`mascot` 而不是 `topLeftImage`。
 */

/** 生成物的文件名，与 `components/brand/exportBrandSvgs.ts` 共用，避免两处漂移。 */
export const GENERATED_SCENE_FILENAMES = {
  chatHero: "kabuqina_hero_scene.svg",
  companionPill: "kabuqina_pill_scene.svg",
} as const;

export const ART_ASSETS = {
  /**
   * 小娜本体。chat 头像与 onboarding 均用它。
   * 现状：手写 SVG 占位。换装契约：正方画布，最小可读尺寸 28px，需透明背景。
   */
  mascot: "/kabuqina_mascot.svg",

  /**
   * 缩小后的常驻挂件场景（杯子 + 杯垫）。学生可自定义替换，
   * 契约见设置里的 `settings.companionImageSpec`：PNG/WebP/SVG，≤1MB，
   * 画布约 620×548 或接近正方形，建议透明背景。
   * 现状：由 `KabuqinaSceneSvg` 渲染生成（`npm run export:brand`）。
   */
  companionPill: `/${GENERATED_SCENE_FILENAMES.companionPill}`,

  /**
   * Chat 空态大图。现状：同上由 `KabuqinaSceneSvg` 生成，当前无调用点——
   * 保留为已生成资源，接入前不占位。
   */
  chatHero: `/${GENERATED_SCENE_FILENAMES.chatHero}`,

  /**
   * 启动态图形（BootPill 与 chat 首屏）。
   * 现状：手写 SVG 占位。换装契约：与 mascot 同族，不引入第二套形象。
   */
  boot: "/kabuqina_boot.svg",

  /**
   * 窗口标题栏图标。现状：48px 位图。
   * 换装契约：需同时提供 16/32/48 三档，标题栏按 DPI 取用。
   */
  windowIcon: "/kabuqina_na_48.png",
} as const;

export type ArtAssetName = keyof typeof ART_ASSETS;
