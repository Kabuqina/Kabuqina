// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import type { ProviderId } from "./providers";
import type { ApiMode } from "./api-mode";

export type LlmConfigPreview = {
  hasSecret: boolean;
  provider: string | null;
  host: string | null;
  model: string | null;
  apiBaseUrl: string | null;
  apiMode: ApiMode | null;
};

export type ProviderSaveConfig = {
  provider: string;
  host: string;
  model: string | null;
  api_base_url: string | null;
  api_mode: ApiMode | null;
};

export const SELECTABLE_LLM_PROVIDERS: (ProviderId | "custom")[] = [
  "deepseek",
  "spark",
  "zai",
  "kimi-coding",
  "kimi-coding-cn",
  "stepfun",
  "minimax-cn",
  "alibaba",
  "custom",
];

export const PROVIDER_PRESETS: Record<string, { host: string; model: string }> = {
  deepseek: { host: "https://api.deepseek.com/v1", model: "deepseek-v4-flash" },
  spark: { host: "https://spark-api-open.xf-yun.com/v1", model: "generalv3.5" },
  zai: { host: "https://api.z.ai/api/paas/v4", model: "glm-5.1" },
  "kimi-coding": { host: "https://api.kimi.com/coding", model: "kimi-k2.6" },
  "kimi-coding-cn": { host: "https://api.kimi.com/coding/v1", model: "kimi-k2.6" },
  stepfun: { host: "https://api.stepfun.ai/step_plan/v1", model: "step-3.5-flash" },
  "minimax-cn": { host: "https://api.minimaxi.com/v1", model: "MiniMax-M2.7" },
  alibaba: { host: "https://dashscope-intl.aliyuncs.com/compatible-mode/v1", model: "qwen3.6-plus" },
};

export function hostFromBaseUrl(url: string): string {
  try {
    return new URL(url).host;
  } catch {
    return url
      .replace(/^https?:\/\//i, "")
      .split("/")[0]
      .trim();
  }
}

export function initialPickerProvider(providerId: string | null | undefined): ProviderId | "custom" | "" {
  const id = providerId?.trim();
  if (!id) return "";
  if (SELECTABLE_LLM_PROVIDERS.includes(id as ProviderId)) return id as ProviderId;
  return "custom";
}
