// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import type { LocaleKey, Localized } from "./setupCatalog/optionTypes";

const ROUTE_C_UIS = new Set([
  "weixin_route_c",
  "qqbot_route_c",
]);

export function pick(loc: Localized, locale: LocaleKey): string {
  return loc[locale] || loc.zh;
}

export function getSlice(
  wizard: Record<string, Record<string, Record<string, string>>> | undefined,
  section: string,
  optionId: string,
): Record<string, string> {
  return { ...(wizard?.[section]?.[optionId] ?? {}) };
}

export function hasRouteCUi(configUi?: string): boolean {
  return !!configUi && ROUTE_C_UIS.has(configUi);
}

export function hasConfigFieldsOrRouteC(
  configFields: unknown[] | undefined,
  configUi: string | undefined,
): boolean {
  return (configFields?.length ?? 0) > 0 || hasRouteCUi(configUi);
}
