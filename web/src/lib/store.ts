// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useSyncExternalStore } from "react";
import type { ProviderId } from "./providers";

export type Personality = "helpful" | "friendly" | "concise";

/** First-time setup now follows the Quick Start path. */
export type SetupMode = "quick";

/**
 * Wizard-only optional config: `section` (e.g. `gateway`, `tts`) → option id → field id → value.
 * Aligned with Hermes env / config names where applicable. Persisted in session (except main `apiKey`).
 */
export type WizardOptionConfig = Record<string, Record<string, Record<string, string>>>;

/**
 * For sections with a roster: either skip (keep CLI/Hermes defaults) or an explicit single/multi pick.
 * Key = same `section` as `SetupOptionsTable` (e.g. `tts`, `gateway`).
 */
export type SectionSelection =
  | { kind: "skip" }
  | { kind: "single"; optionId: string }
  | { kind: "multi"; optionIds: string[] };

export type WizardSectionSelections = Record<string, SectionSelection | undefined>;

export interface OnboardingDraft {
  /** Quick Start marker used to resume an in-progress onboarding draft. */
  setupMode: SetupMode | null;
  /**
   * When true (typical for Quick), we copy Hermes-style behavior: apply recommended defaults
   * for non-model sections later in the flow / via assistant restart.
   */
  useRecommendedDefaults: boolean;
  providerId: ProviderId | null;
  apiKey: string;
  personality: Personality;
  /** OpenAI-compatible API base URL (custom provider only). */
  customBaseUrl?: string;
  /** Model id as required by that endpoint (custom provider only). */
  customModel?: string;
  /** Optional provider id passed through to Hermes for a manually configured endpoint. */
  customProviderId?: string;
  /** Per-section, per-option form values from the setup option tables (can be all empty = use defaults / skip). */
  wizardConfig?: WizardOptionConfig;
  /** Single/multi/skip choice per section roster (for `next` gating + sync intent). */
  wizardSelection?: WizardSectionSelections;
}

const KEY = "kabuqina.onboarding-draft";
const LEGACY_KEY = "hermesdesk.onboarding-draft";

const initial: OnboardingDraft = {
  setupMode: null,
  useRecommendedDefaults: true,
  providerId: null,
  apiKey: "",
  personality: "helpful",
  wizardConfig: {},
  wizardSelection: {},
};

let state: OnboardingDraft = (() => {
  try {
    const raw = sessionStorage.getItem(KEY) ?? sessionStorage.getItem(LEGACY_KEY);
    if (raw) {
      sessionStorage.setItem(KEY, raw);
      const p = JSON.parse(raw) as Partial<OnboardingDraft>;
      const rawSetupMode = (p as { setupMode?: unknown }).setupMode;
      return {
        ...initial,
        ...p,
        setupMode: rawSetupMode === "quick" || rawSetupMode === "full" ? "quick" : null,
        useRecommendedDefaults: p.useRecommendedDefaults ?? true,
        wizardConfig: p.wizardConfig && typeof p.wizardConfig === "object" ? p.wizardConfig : {},
        wizardSelection: p.wizardSelection && typeof p.wizardSelection === "object" ? p.wizardSelection : {},
      };
    }
  } catch {
    // ignore
  }
  return initial;
})();

const subscribers = new Set<() => void>();

function snapshot() {
  return state;
}

/** Latest draft (for callbacks that must not close over stale React state). */
export function getDraftSnapshot(): OnboardingDraft {
  return state;
}

function subscribe(cb: () => void) {
  subscribers.add(cb);
  return () => subscribers.delete(cb);
}

export function updateDraft(patch: Partial<OnboardingDraft>) {
  state = { ...state, ...patch };
  // Persist everything EXCEPT the API key. Key must never touch disk.
  const { apiKey: _omit, ...safe } = state;
  void _omit;
  try {
    sessionStorage.setItem(KEY, JSON.stringify(safe));
  } catch {
    // ignore
  }
  subscribers.forEach((cb) => cb());
}

export function clearDraft() {
  state = initial;
  try {
    sessionStorage.removeItem(KEY);
    sessionStorage.removeItem(LEGACY_KEY);
  } catch {
    // ignore
  }
  subscribers.forEach((cb) => cb());
}

export function useDraft() {
  return useSyncExternalStore(subscribe, snapshot, snapshot);
}
