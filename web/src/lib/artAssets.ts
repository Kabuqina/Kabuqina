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
   * 缩小后的常驻桌宠。学生可自定义替换，
   * 契约见设置里的 `settings.companionImageSpec`：PNG/WebP/SVG，≤1MB，
   * 画布约 620×548 或接近正方形，建议透明背景。
   * 默认使用体素系统组合导出的杯子 + 杯垫 + 蒸汽版本。
   */
  companionPill: "/kabuqina_voxel_appicon_steam.svg",

  /**
   * Chat 空态大图。现状：同上由 `KabuqinaSceneSvg` 生成，当前无调用点——
   * 保留为已生成资源，接入前不占位。
   */
  chatHero: `/${GENERATED_SCENE_FILENAMES.chatHero}`,

  /** Chat 空白状态中央的体素应用图标，使用设计导出的 SVG。 */
  chatEmptyCup: "/kabuqina_export_appicon.svg",

  /**
   * 启动态图形（BootPill 与 chat 首屏）。
   * 现状：手写 SVG 占位。换装契约：与 mascot 同族，不引入第二套形象。
   */
  boot: "/kabuqina_boot.svg",

  /**
   * 窗口标题栏图标。现状：48px 位图。
   * 换装契约：需同时提供 16/32/48 三档，标题栏按 DPI 取用。
   */
  windowIcon: "/kabuqina_qi_48.png",

  /**
   * 「缩到小娜」按钮图标。源自 Minecraft 风格系统的 kq-cup 档，
   * 在标题栏中按 28×28px 展示，不额外套底板。
   */
  companionButton: "/kabuqina_voxel_cup.svg",

  /** Chat 助手消息头像，使用带杯垫的体素 kq-appicon SVG。 */
  assistantAvatar: "/kabuqina_export_appicon.svg",
  assistantAvatarNight: "/kabuqina_voxel_appicon_night.svg",

  /**
   * 注册字标「卡布Qi娜」。**不是产品名**——正文里的产品名是「卡布奇娜」，
   * 字标中间那两个拉丁字母就是杯口那个 Q，两者不要互相看齐。
   *
   * 字形是注册的：不许重排、不许换字重、不许用系统字体现拼。能动的只有墨色，
   * 所以白天与夜晚是两个文件，而不是一张图套 filter——套滤镜会连字形边缘一起脏。
   * 现状：设计稿导出的 452×96 透明 PNG（横条按 15px 高用，@3x 仍有余量）。
   * 换装契约：透明背景、高度基准 96px、宽高比约 4.7:1，两档必须同尺寸同基线。
   */
  wordmark: "/kabuqina_wordmark_accent.png",
  wordmarkNight: "/kabuqina_wordmark_night.png",
} as const;

export type ArtAssetName = keyof typeof ART_ASSETS;
