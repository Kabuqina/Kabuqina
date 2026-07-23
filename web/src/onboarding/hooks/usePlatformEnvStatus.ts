// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useEffect, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import type { SetupCatalogOption } from "../setupCatalog/optionTypes";
import type { WeixinEnvSnapshot } from "../../components/WeixinQrRouteCBlock";
import type { QqEnvSnapshot } from "../../components/QqbotQrRouteBlock";

export function usePlatformEnvStatus(items: SetupCatalogOption[]) {
  const [weixinEnv, setWeixinEnv] = useState<WeixinEnvSnapshot | null>(null);
  const [qqEnv, setQqEnv] = useState<QqEnvSnapshot | null>(null);

  useEffect(() => {
    if (items.some((r) => r.configUi === "weixin_route_c")) {
      invoke<WeixinEnvSnapshot>("cmd_weixin_env_status").then(setWeixinEnv).catch(() => setWeixinEnv(null));
    }
  }, [items]);

  useEffect(() => {
    if (items.some((r) => r.configUi === "qqbot_route_c")) {
      invoke<QqEnvSnapshot>("cmd_qq_env_status").then(setQqEnv).catch(() => setQqEnv(null));
    }
  }, [items]);

  return { weixinEnv, qqEnv } as const;
}
