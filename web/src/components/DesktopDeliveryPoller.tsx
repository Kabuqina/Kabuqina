// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useEffect } from "react";
import { listen } from "@tauri-apps/api/event";
import { drainDesktopDeliveries } from "../lib/desktopDeliveryFeed";
import type { DesktopDeliveryMessage } from "../lib/desktopDelivery";

const EVENT_NAME = "desktop-delivery";
const POLL_MS = 4000;

/** Drain Rust delivery queue app-wide so reminders are not lost off /chat. */
export function DesktopDeliveryPoller() {
  useEffect(() => {
    let cancelled = false;
    const tick = async () => {
      if (cancelled) return;
      await drainDesktopDeliveries();
    };
    void tick();
    const handle = window.setInterval(() => {
      void tick();
    }, POLL_MS);
    const unlisten = listen<DesktopDeliveryMessage>(EVENT_NAME, () => {
      void tick();
    });
    return () => {
      cancelled = true;
      window.clearInterval(handle);
      unlisten.then((fn) => fn());
    };
  }, []);

  return null;
}
