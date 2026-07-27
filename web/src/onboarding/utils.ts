// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import type { LocaleKey, Localized } from "./setupCatalog/optionTypes";

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

export function hasConfigFields(configFields: unknown[] | undefined): boolean {
  return (configFields?.length ?? 0) > 0;
}
