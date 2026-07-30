// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

/**
 * Activity 是**跨域状态层**（架构 §5.4），入口在全局页眉上。事件桥只负责让
 * 当前表面和全局入口打开同一个 S10 面板；面板的数据来自 B-10 聚合投影。
 */

const OPEN_ACTIVITY_EVENT = "kabuqina-open-activity";

export function requestOpenActivity(): void {
  window.dispatchEvent(new Event(OPEN_ACTIVITY_EVENT));
}

export function onOpenActivityRequest(handler: () => void): () => void {
  window.addEventListener(OPEN_ACTIVITY_EVENT, handler);
  return () => window.removeEventListener(OPEN_ACTIVITY_EVENT, handler);
}
