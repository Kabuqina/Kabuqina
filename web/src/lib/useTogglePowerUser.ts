// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useCallback, useEffect } from "react";
import { invoke } from "@tauri-apps/api/core";
import { confirm } from "./confirmDialog";
import { useI18n } from "./i18n";
import { setPowerUser, usePowerUser } from "./powerUser";

export function useTogglePowerUser() {
  const { t } = useI18n();
  const powerUser = usePowerUser();

  useEffect(() => {
    void (async () => {
      try {
        const v = await invoke<boolean>("cmd_get_power_user");
        setPowerUser(!!v);
      } catch {
        /* optional */
      }
    })();
  }, []);

  const togglePowerUser = useCallback(
    async (next: boolean) => {
      if (next) {
        const ok = await confirm({
          title: t("settings.powerAskTitle"),
          message: t("settings.powerAsk"),
          confirmLabel: t("dialog.enable"),
          cancelLabel: t("dialog.cancel"),
          tone: "warning",
        });
        if (!ok) return;
      }
      try {
        await invoke("cmd_set_power_user", { enabled: next });
        setPowerUser(next);
      } catch (e) {
        console.error(e);
      }
    },
    [t],
  );

  return { powerUser, togglePowerUser };
}
