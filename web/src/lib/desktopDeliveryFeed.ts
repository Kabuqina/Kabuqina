// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { invoke } from "@tauri-apps/api/core";
import type { DesktopDeliveryMessage } from "./desktopDelivery";

export async function drainDesktopDeliveries(): Promise<DesktopDeliveryMessage[]> {
  try {
    const msgs = await invoke<DesktopDeliveryMessage[]>("cmd_desktop_messages");
    return msgs?.length ? msgs : [];
  } catch (e) {
    console.debug("cmd_desktop_messages skipped:", e);
    return [];
  }
}

export function formatReminderChatText(
  delivery: DesktopDeliveryMessage,
  streamTitle: string,
): string {
  const header = delivery.title?.trim() || streamTitle;
  const body = delivery.message?.trim() ?? "";
  return body ? `**${streamTitle}: ${header}**\n\n${body}` : `**${streamTitle}: ${header}**`;
}
