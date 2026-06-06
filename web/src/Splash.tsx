// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { invoke } from "@tauri-apps/api/core";
import { AppScaffold } from "./components/AppScaffold";
import { BootPill } from "./components/BootPill";
import { waitForHermesReadiness } from "./chat/hermesReadinessPoll";
import { useI18n } from "./lib/i18n";
import { clearAllowChatWithoutApi, getAllowChatWithoutApi } from "./lib/apiKeyGate";

/**
 * App entry: saved API key → chat (after Hermes ready). No key but user chose
 * “configure later” on pass step → chat (after Hermes ready). Otherwise → onboarding.
 */
export function Splash() {
  const { t } = useI18n();
  const nav = useNavigate();

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const has = await invoke<boolean>("cmd_has_secret");
        if (cancelled) {
          return;
        }
        const goChat = has || getAllowChatWithoutApi();
        if (goChat) {
          if (has) {
            clearAllowChatWithoutApi();
          }
          await waitForHermesReadiness(t, () => cancelled);
          if (cancelled) {
            return;
          }
          nav("/chat", { replace: true });
          return;
        }
        nav("/onboarding/welcome", { replace: true });
      } catch {
        if (!cancelled) {
          nav("/onboarding/welcome", { replace: true });
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [nav, t]);

  return (
    <AppScaffold className="flex h-full min-h-0 flex-col items-center justify-center">
      <BootPill />
    </AppScaffold>
  );
}
