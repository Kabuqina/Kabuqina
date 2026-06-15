// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useEffect, useMemo, useState, type ReactNode } from "react";
import { invoke } from "@tauri-apps/api/core";
import { openUrl } from "@tauri-apps/plugin-opener";
import { Check, Loader2 } from "lucide-react";
import { Button } from "./ui/Button";
import { cn } from "../lib/cn";
import { useI18n } from "../lib/i18n";
import { findProvider, type Provider, type ProviderId } from "../lib/providers";
import {
  hostFromBaseUrl,
  initialPickerProvider,
  PROVIDER_PRESETS,
  SELECTABLE_LLM_PROVIDERS,
  type LlmConfigPreview,
  type ProviderSaveConfig,
} from "../lib/llm-config";
import { normalizeOpenAiBaseUrl, validateCustomEndpoint, validateKey } from "../lib/validate";

type Mode = "onboarding" | "settings";

type DraftPatch = {
  apiKey?: string;
  customBaseUrl?: string;
  customModel?: string;
  customProviderId?: string;
};

type Props = {
  mode: Mode;
  initialProviderId?: ProviderId | null;
  initialBaseUrl?: string;
  initialModel?: string;
  initialCustomProviderId?: string;
  onDraftChange?: (patch: DraftPatch) => void;
  onSaved: () => void | Promise<void>;
  renderActions?: (controls: { onSave: () => void; disabled: boolean; busy: boolean; label: string }) => ReactNode;
};

async function validateEndpointForProvider(
  selectedProvider: Provider | null,
  baseUrl: string,
  apiKey: string,
) {
  if (selectedProvider?.skipEndpointValidation) {
    return { ok: true as const };
  }
  if (baseUrl.trim()) {
    return validateCustomEndpoint(baseUrl, apiKey);
  }
  if (selectedProvider) {
    return validateKey(selectedProvider.id, apiKey);
  }
  return validateCustomEndpoint(baseUrl, apiKey);
}

function knownProviderOrNull(id: string): Provider | null {
  if (!id || id === "custom") return null;
  try {
    return findProvider(id as ProviderId);
  } catch {
    return null;
  }
}

function hasPreset(id: string): boolean {
  return Boolean(id && id !== "custom" && PROVIDER_PRESETS[id]);
}

function savedProviderMatchesSelection(
  preview: LlmConfigPreview | null,
  selectedProvider: ProviderId | "custom" | "",
  customProviderId: string,
): boolean {
  if (!preview?.hasSecret || !preview.provider || !selectedProvider) return false;
  if (selectedProvider !== "custom") return preview.provider === selectedProvider;
  return preview.provider === (customProviderId.trim() || "custom");
}

function resolvePreviewFields(p: LlmConfigPreview) {
  const nextProvider = initialPickerProvider(p.provider);
  const resolvedProvider = nextProvider || "deepseek";
  const nextBaseUrl = p.apiBaseUrl ?? PROVIDER_PRESETS[resolvedProvider]?.host ?? "";
  const nextModel = p.model ?? PROVIDER_PRESETS[resolvedProvider]?.model ?? "";
  const nextCustomProviderId = resolvedProvider === "custom" ? p.provider ?? "custom" : "";
  return { resolvedProvider, nextBaseUrl, nextModel, nextCustomProviderId };
}

export function LlmConfigEditor({
  mode,
  initialProviderId,
  initialBaseUrl = "",
  initialModel = "",
  initialCustomProviderId = "",
  onDraftChange,
  onSaved,
  renderActions,
}: Props) {
  const { t } = useI18n();
  const initialSelectedProvider = initialPickerProvider(mode === "onboarding" ? initialProviderId : null);
  const [preview, setPreview] = useState<LlmConfigPreview | null>(null);
  const [selectedProvider, setSelectedProvider] = useState<ProviderId | "custom" | "">(
    initialSelectedProvider,
  );
  const [customProviderId, setCustomProviderId] = useState(initialCustomProviderId);
  const [baseUrl, setBaseUrl] = useState(initialBaseUrl || (initialSelectedProvider && PROVIDER_PRESETS[initialSelectedProvider]?.host) || "");
  const [modelId, setModelId] = useState(initialModel || (initialSelectedProvider && PROVIDER_PRESETS[initialSelectedProvider]?.model) || "");
  const [key, setKey] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savedNotice, setSavedNotice] = useState(false);
  const [validationStatus, setValidationStatus] = useState<"idle" | "validating" | "valid" | "invalid">("idle");
  const [validationMessage, setValidationMessage] = useState<string | null>(null);

  const selectedKnownProvider = useMemo(() => knownProviderOrNull(selectedProvider), [selectedProvider]);
  const isManualCustom = selectedProvider === "custom";
  const isOnboardingFixedProvider = mode === "onboarding" && initialProviderId !== "custom";
  const savedMatches = savedProviderMatchesSelection(preview, selectedProvider, customProviderId);

  useEffect(() => {
    invoke<LlmConfigPreview>("cmd_llm_config_preview")
      .then((p) => {
        setPreview(p);
        if (mode === "settings" || (mode === "onboarding" && initialProviderId === "custom" && p.provider)) {
          const { resolvedProvider, nextBaseUrl, nextModel, nextCustomProviderId } = resolvePreviewFields(p);
          setSelectedProvider(resolvedProvider);
          setCustomProviderId(nextCustomProviderId);
          setBaseUrl(nextBaseUrl);
          setModelId(nextModel);
          if (mode === "onboarding" && initialProviderId === "custom") {
            onDraftChange?.({
              customBaseUrl: nextBaseUrl,
              customModel: nextModel,
              customProviderId: nextCustomProviderId || resolvedProvider,
            });
          }
        }
      })
      .catch(() => setPreview({ hasSecret: false, provider: null, host: null, model: null, apiBaseUrl: null }));
  }, [initialProviderId, mode, onDraftChange]);

  useEffect(() => {
    const trimmed = key.trim();
    if (!trimmed || !selectedProvider) {
      setValidationStatus("idle");
      setValidationMessage(null);
      return;
    }

    const timer = setTimeout(async () => {
      setValidationStatus("validating");
      try {
        const result = await validateEndpointForProvider(selectedKnownProvider, baseUrl, key);
        setValidationStatus(result.ok ? "valid" : "invalid");
        setValidationMessage(result.message ?? null);
      } catch {
        setValidationStatus("invalid");
        setValidationMessage(t("pass.errGeneric"));
      }
    }, 800);
    return () => clearTimeout(timer);
  }, [baseUrl, key, selectedKnownProvider, selectedProvider, t]);

  function applyProvider(next: ProviderId | "custom" | "") {
    setSelectedProvider(next);
    setError(null);
    setSavedNotice(false);
    if (hasPreset(next)) {
      const preset = PROVIDER_PRESETS[next];
      setBaseUrl(preset.host);
      setModelId(preset.model);
      setCustomProviderId("");
      onDraftChange?.({ customBaseUrl: preset.host, customModel: preset.model, customProviderId: "" });
    } else if (next === "custom") {
      setBaseUrl("");
      setModelId("");
      setCustomProviderId("");
      onDraftChange?.({ customBaseUrl: "", customModel: "", customProviderId: "" });
    }
  }

  async function openSignup() {
    if (!selectedKnownProvider?.signupUrl) return;
    try {
      await openUrl(selectedKnownProvider.signupUrl);
    } catch (e) {
      console.error(e);
    }
  }

  function buildSaveConfig(): ProviderSaveConfig | null {
    if (!selectedProvider) return null;
    const providerForSave = selectedProvider !== "custom" ? selectedProvider : customProviderId.trim() || "custom";
    const url = baseUrl.trim();
    const preset = selectedProvider !== "custom" ? PROVIDER_PRESETS[selectedProvider] : null;
    const model = modelId.trim() || preset?.model || null;
    return {
      provider: providerForSave,
      host: selectedKnownProvider?.host || hostFromBaseUrl(url),
      model,
      api_base_url: url ? normalizeOpenAiBaseUrl(url) : null,
    };
  }

  async function onSave() {
    const cfg = buildSaveConfig();
    if (!cfg) return;
    setBusy(true);
    setError(null);
    setSavedNotice(false);
    try {
      const continuingWithSaved = savedMatches && !key.trim();
      if (!continuingWithSaved) {
        const result = await validateEndpointForProvider(selectedKnownProvider, baseUrl, key);
        if (!result.ok) {
          setError(result.message ?? t("pass.errGeneric"));
          return;
        }
      }

      await invoke(continuingWithSaved ? "cmd_update_llm_config" : "cmd_save_secret", {
        cfg,
        secret: continuingWithSaved ? null : key.trim(),
      });
      setSavedNotice(mode === "settings");
      setKey("");
      onDraftChange?.({
        apiKey: "",
        customBaseUrl: baseUrl.trim(),
        customModel: cfg.model ?? "",
        customProviderId: cfg.provider,
      });
      await onSaved();
    } catch (e: unknown) {
      setError(typeof e === "string" ? e : (e as Error)?.message ?? t("pass.errSave"));
    } finally {
      setBusy(false);
    }
  }

  const canSubmit = savedMatches && !key.trim()
    ? true
    : isManualCustom
      ? Boolean(key.trim() && baseUrl.trim() && modelId.trim())
      : Boolean(selectedProvider && key.trim());
  const showProviderPicker = mode === "settings" || initialProviderId === "custom";
  const showApiUrl = isManualCustom;
  const fieldClass =
    "w-full rounded-[var(--radius-shell)] border border-[var(--kq-color-border)] bg-[var(--kq-input-surface)] px-4 py-3 font-mono text-sm";
  const actionLabel = busy
    ? mode === "settings" ? t("settings.llmConfigSaving") : t("pass.checkWait")
    : mode === "settings" ? t("settings.llmConfigSave")
      : savedMatches && !key.trim() ? t("pass.continueCta")
        : t("pass.cta");
  const disabled = busy || !canSubmit;

  return (
    <div className="space-y-4">
      {showProviderPicker ? (
        <div className="space-y-2">
          <label className="hd-wizard-label">{t("pass.labelProvider")}</label>
          <select
            value={selectedProvider}
            onChange={(e) => applyProvider(e.target.value as ProviderId | "custom" | "")}
            className="w-full rounded-[var(--radius-shell)] border border-[var(--kq-color-border)] bg-[var(--kq-input-surface)] px-4 py-3 text-sm"
          >
            <option value="">{t("pass.selectProvider")}</option>
            {SELECTABLE_LLM_PROVIDERS.filter((pid) => pid !== "custom").map((pid) => (
              <option key={pid} value={pid}>{findProvider(pid).label}</option>
            ))}
            <option disabled>--</option>
            <option value="custom">{t("pass.providerCustomLabel")}</option>
          </select>
        </div>
      ) : null}

      {!showProviderPicker && selectedKnownProvider ? (
        <div className="space-y-1.5">
          <label className="hd-wizard-label">{t("settings.llmConfigProvider")}</label>
          <p className="text-sm text-[var(--kq-color-ink)]">{selectedKnownProvider.label}</p>
        </div>
      ) : null}

      {isManualCustom ? (
        <div className="space-y-2">
          <label className="hd-wizard-label">{t("pass.labelCustomProviderId")}</label>
          <input
            type="text"
            autoComplete="off"
            spellCheck={false}
            value={customProviderId}
            onChange={(e) => {
              setCustomProviderId(e.target.value);
              onDraftChange?.({ customProviderId: e.target.value });
            }}
            placeholder={t("pass.phCustomProviderId")}
            className={fieldClass}
          />
          <p className="hd-wizard-hint">{t("pass.customProviderHint")}</p>
        </div>
      ) : null}

      {showApiUrl ? (
        <div className="space-y-2">
          <label className="hd-wizard-label">{t("pass.labelApiUrl")}</label>
          <input
            type="url"
            autoComplete="off"
            spellCheck={false}
            value={baseUrl}
            onChange={(e) => {
              setBaseUrl(e.target.value);
              onDraftChange?.({ customBaseUrl: e.target.value });
            }}
            placeholder={t("pass.phApiUrl")}
            className={fieldClass}
          />
        </div>
      ) : null}

      <div className="space-y-2">
        <label className="hd-wizard-label">{t("settings.llmConfigModel")}</label>
        <input
          type="text"
          autoComplete="off"
          spellCheck={false}
          value={modelId}
          onChange={(e) => {
            setModelId(e.target.value);
            onDraftChange?.({ customModel: e.target.value });
          }}
          placeholder={t("pass.phModel")}
          className={fieldClass}
        />
      </div>

      <div className="space-y-2">
        <label className="hd-wizard-label">
          {mode === "settings" ? t("settings.llmConfigKey") : isManualCustom ? t("pass.labelKeyCustom") : t("pass.labelKey")}
        </label>
        <div className="relative">
          <input
            type="password"
            autoComplete="off"
            spellCheck={false}
            value={key}
            onChange={(e) => setKey(e.target.value)}
            placeholder={savedMatches ? t("pass.keyPlaceholderSaved") : selectedKnownProvider?.keyPrefixHint ? `${selectedKnownProvider.keyPrefixHint}...` : t("pass.phKey")}
            className={cn(
              fieldClass,
              "pr-10",
              validationStatus === "valid" && "border-emerald-400 dark:border-emerald-600",
              validationStatus === "invalid" && "border-red-400 dark:border-red-600",
            )}
          />
          {validationStatus === "validating" ? (
            <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2">
              <Loader2 className="h-4 w-4 animate-spin text-[var(--kq-color-muted)]" />
            </span>
          ) : null}
          {validationStatus === "valid" ? (
            <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-emerald-500">
              <Check className="h-4 w-4" strokeWidth={3} />
            </span>
          ) : null}
        </div>
        {mode === "settings" ? <p className="hd-wizard-hint">{t("settings.llmConfigKeyHint")}</p> : null}
        {validationStatus === "invalid" && validationMessage ? (
          <p className="hd-wizard-body text-red-600 dark:text-red-400">{validationMessage}</p>
        ) : null}
        {error ? <p className="hd-wizard-body text-red-600 dark:text-red-400">{error}</p> : null}
      </div>

      {mode === "onboarding" && isOnboardingFixedProvider && selectedKnownProvider?.signupUrl ? (
        <button
          type="button"
          onClick={openSignup}
          className="w-full rounded-[var(--radius-shell-lg)] border border-[var(--kq-color-border)] px-4 py-3 transition hover:bg-[var(--kq-hover-bg)]"
        >
          {t("pass.openVendor", { label: selectedKnownProvider.label })}
        </button>
      ) : null}

      {renderActions ? (
        renderActions({ onSave: () => void onSave(), disabled, busy, label: actionLabel })
      ) : (
      <div className="flex flex-wrap items-center gap-3">
        <Button onClick={() => void onSave()} disabled={disabled}>
          {busy ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              {actionLabel}
            </>
          ) : (
            actionLabel
          )}
        </Button>
        {savedNotice ? (
          <span className="text-sm text-emerald-600 dark:text-emerald-400">{t("settings.llmConfigSaved")}</span>
        ) : null}
      </div>
      )}
    </div>
  );
}
