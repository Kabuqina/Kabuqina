// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useCallback, useEffect, useRef, useState } from "react";
import { STUDY_LEARNING_EVENT } from "../study/learningEvent";
import { cmdActivityRecords, type GlobalActivityRecord } from "./activityApi";

/**
 * 「进行中」按需出现（v0.5.0）。Studio/Report 砍掉后，Activity 缩成一个 Study
 * 的「接续现场」托盘——绝大多数时间是空的，不该常驻一个和 Chat / 设置平级的顶层
 * 按钮。这个 hook 只回答一个问题：现在到底有没有**还活着**的学习现场？有几个？
 * 外壳据此决定那颗按钮冒不冒出来、带几号角标。
 *
 * 没有后端推送，只能拉。但也不盲目定时刷：主要靠 STUDY_LEARNING_EVENT（各 Study
 * 页面改动学习库后都会发）事件驱动，另加一个 30s 兜底——为了「人已经切到 Chat，
 * 后台知识核还在编译」这个我们特意保留的安全网：编译完成时把角标点亮。
 */

// 「还活着」＝还需要你回去接续的现场。已完成/已失败/已取消不是「进行中」，不点亮。
function isLive(record: GlobalActivityRecord): boolean {
  if (record.domain !== "study") return false;
  if (record.kind === "knowledge_core_compilation") {
    // 整理中、待采用、等待知识源都算活；只有明确收尾的两态不算。
    return record.sourceStatus !== "failed" && record.sourceStatus !== "cancelled";
  }
  return (
    record.status === "running"
    || record.status === "waiting"
    || record.status === "interrupted"
    || record.status === "recoverable"
  );
}

const REFRESH_INTERVAL_MS = 30_000;

export function useActivityBadge(load = cmdActivityRecords): { count: number; refresh: () => void } {
  const [count, setCount] = useState(0);
  // 卸载后别再 setState；浏览器 DEV 没有后端，invoke 会 reject，静默归零即可。
  const alive = useRef(true);

  const refresh = useCallback(() => {
    // await 在 try 里同时吃掉「同步抛出」和「promise 拒绝」两种失败——
    // 浏览器 DEV 无 Tauri 时 invoke 会炸，绝不能漏成 uncaught rejection。
    void (async () => {
      try {
        const data = await load(undefined, 100);
        if (alive.current) setCount(data.items.filter(isLive).length);
      } catch {
        if (alive.current) setCount(0);
      }
    })();
  }, [load]);

  useEffect(() => {
    alive.current = true;
    refresh();
    window.addEventListener(STUDY_LEARNING_EVENT, refresh);
    const timer = window.setInterval(refresh, REFRESH_INTERVAL_MS);
    return () => {
      alive.current = false;
      window.removeEventListener(STUDY_LEARNING_EVENT, refresh);
      window.clearInterval(timer);
    };
  }, [refresh]);

  return { count, refresh };
}
