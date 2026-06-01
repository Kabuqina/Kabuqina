// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { invoke } from "@tauri-apps/api/core";
import { getLocale, translate } from "./i18n-core";
import { findProvider, type ProviderId } from "./providers";

/** Strip trailing slashes for OpenAI-compatible base URLs. */
export function normalizeOpenAiBaseUrl(url: string): string {
  return url.trim().replace(/\/+$/, "");
}

function hasTauriInvoke(): boolean {
  return typeof window !== "undefined" && !!(window as unknown as { __TAURI_INTERNALS__?: unknown }).__TAURI_INTERNALS__;
}

function loc() {
  return getLocale();
}

/**
 * Validate a custom OpenAI-compatible endpoint.
 */
export async function validateCustomEndpoint(
  baseUrl: string,
  apiKey: string
): Promise<ValidateResult> {
  const base = normalizeOpenAiBaseUrl(baseUrl);
  if (!base) {
    return { ok: false, message: translate("validate.needUrl", loc()) };
  }
  const trimmed = apiKey.trim();
  if (!trimmed) {
    return { ok: false, message: translate("validate.needKey", loc()) };
  }

  const modelsUrl = `${base}/models`;

  if (!hasTauriInvoke()) {
    return { ok: false, message: translate("validate.unreachable", loc()) };
  }

  try {
    await invoke("cmd_validate_endpoint", {
      url: modelsUrl,
      apiKey: trimmed,
    });
    return { ok: true };
  } catch (e: unknown) {
    const msg =
      e instanceof Error ? e.message : typeof e === "string" ? e : JSON.stringify(e);
    return { ok: false, message: msg || translate("validate.unreachable", loc()) };
  }
}

export interface ValidateResult {
  ok: boolean;
  message?: string;
}

export async function validateKey(
  providerId: ProviderId,
  key: string
): Promise<ValidateResult> {
  const provider = findProvider(providerId);
  const l = loc();
  const trimmed = key.trim();
  if (!trimmed) return { ok: false, message: translate("validate.needKey", l) };

  if (provider.keyPrefixHint && !trimmed.startsWith(provider.keyPrefixHint)) {
    return {
      ok: false,
      message: translate("validate.keyPrefix", l, {
        label: provider.label,
        hint: provider.keyPrefixHint,
      }),
    };
  }

  if (!hasTauriInvoke()) {
    return { ok: false, message: translate("validate.unreachable", l) };
  }

  try {
    await invoke("cmd_validate_endpoint", {
      url: provider.validateUrl,
      apiKey: trimmed,
    });
    return { ok: true };
  } catch (e: unknown) {
    const msg =
      e instanceof Error ? e.message : typeof e === "string" ? e : JSON.stringify(e);
    return { ok: false, message: msg || translate("validate.providerReach", l, { label: provider.label }) };
  }
}
