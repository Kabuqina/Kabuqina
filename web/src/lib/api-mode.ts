// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

export type ApiMode = "chat_completions" | "anthropic_messages";
export type ApiModeSelection = "auto" | ApiMode;

export function normalizeApiBaseUrl(url: string): string {
  return url.trim().replace(/\/+$/, "");
}

export function inferApiMode(provider: string, rawBaseUrl: string): ApiMode {
  const providerId = provider.trim().toLowerCase();
  const baseUrl = normalizeApiBaseUrl(rawBaseUrl);
  if (providerId === "anthropic") return "anthropic_messages";

  try {
    const parsed = new URL(baseUrl);
    const host = parsed.hostname.toLowerCase();
    const path = parsed.pathname.replace(/\/+$/, "").toLowerCase();
    if (host === "api.anthropic.com") return "anthropic_messages";
    if (path.endsWith("/anthropic")) return "anthropic_messages";
    if (host === "api.kimi.com" && path.includes("/coding")) {
      return "anthropic_messages";
    }
  } catch {
    // Rust remains the URL trust boundary; invalid URLs are not protocol evidence.
  }

  return "chat_completions";
}

export function effectiveApiMode(
  selection: ApiModeSelection,
  provider: string,
  baseUrl: string,
): ApiMode {
  return selection === "auto" ? inferApiMode(provider, baseUrl) : selection;
}

export function persistedApiMode(selection: ApiModeSelection): ApiMode | null {
  return selection === "auto" ? null : selection;
}

export function shouldProbeOpenAiModels(
  selection: ApiModeSelection,
  provider: string,
  baseUrl: string,
): boolean {
  return effectiveApiMode(selection, provider, baseUrl) === "chat_completions";
}
