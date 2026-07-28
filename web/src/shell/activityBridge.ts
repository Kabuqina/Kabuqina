// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

/**
 * Activity 是**跨域状态层**（架构 §5.4），入口在全局页眉上。真正的跨域面板
 * （Study 现场 + Studio 现场 + 恢复）属于 S10；在那之前，页眉这颗按钮通过这个
 * 事件桥接到已经接好真实数据的课程学习动态面板，免得重排 IA 的过程中把一个
 * 能用的功能弄丢。
 *
 * S10 落地后，这个桥换成真正的面板宿主。
 */

const OPEN_ACTIVITY_EVENT = "kabuqina-open-activity";

export function requestOpenActivity(): void {
  window.dispatchEvent(new Event(OPEN_ACTIVITY_EVENT));
}

export function onOpenActivityRequest(handler: () => void): () => void {
  window.addEventListener(OPEN_ACTIVITY_EVENT, handler);
  return () => window.removeEventListener(OPEN_ACTIVITY_EVENT, handler);
}
