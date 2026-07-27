// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

export type PostPassSectionId = "tts" | "stt" | "terminal" | "tools" | "agent";

export type LocaleKey = "zh" | "en";

export type Localized = Record<LocaleKey, string>;

/**
 * A single user-editable value under a catalog row (env name / config key is usually `id`).
 * Empty string = “leave to Hermes / default / not set in this session”.
 */
export type OptionConfigField = {
  id: string;
  label: Localized;
  placeholder: Localized;
  kind: "text" | "password" | "url";
  /** If true, UI may leave blank; still saved as "". */
  optional: boolean;
};

export type SetupCatalogOption = {
  id: string;
  name: Localized;
  defaultHint: Localized;
  isDefault?: boolean;
  /**
   * When present, the row has a "配置" action that opens a form for these fields.
   * (User-facing "子流程" = concrete configuration, not a help pop-up.)
   */
  configFields?: OptionConfigField[];
};
