// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { invoke } from "@tauri-apps/api/core";
import { openUrl } from "@tauri-apps/plugin-opener";
import { findProvider, type Provider, type ProviderId } from "../../lib/providers";
import { useI18n } from "../../lib/i18n";
import { validateKey, validateCustomEndpoint, normalizeOpenAiBaseUrl } from "../../lib/validate";
import { updateDraft, useDraft } from "../../lib/store";
import { clearAllowChatWithoutApi, setAllowChatWithoutApi } from "../../lib/apiKeyGate";
import { getBackPath, getNextPathAfterPass } from "../flowConfig";
import { cn } from "../../lib/cn";
import { Check, Loader2 } from "lucide-react";
import {
  WizardFooter, WizardFooterActions,
  WizardPrimaryButton,
} from "../wizard-ui";

type LlmConfigPreview = {
  hasSecret: boolean; provider: string | null; host: string | null;
  model: string | null; apiBaseUrl: string | null;
};

const DROPDOWN_PROVIDERS: (ProviderId | "custom")[] = [
  "deepseek",
  "openai",
  "anthropic",
  "groq",
  "mistral",
  "openrouter",
  "gemini",
  "zai",
  "kimi-coding",
  "kimi-coding-cn",
  "stepfun",
  "minimax",
  "minimax-cn",
  "alibaba",
  "xai",
  "nvidia",
  "huggingface",
  "arcee",
  "gmi",
  "ollama-cloud",
  "custom",
];

const PROVIDER_PRESETS: Record<string, { host: string; model: string }> = {
  deepseek: { host: "https://api.deepseek.com", model: "deepseek-v4-flash" },
  openai: { host: "https://api.openai.com/v1", model: "gpt-4o" },
  anthropic: { host: "https://api.anthropic.com/v1", model: "claude-sonnet-4-20250514" },
  groq: { host: "https://api.groq.com/openai/v1", model: "qwen-2.5-32b" },
  mistral: { host: "https://api.mistral.ai/v1", model: "mistral-medium" },
  openrouter: { host: "https://openrouter.ai/api/v1", model: "deepseek/deepseek-v4-flash" },
  gemini: { host: "https://generativelanguage.googleapis.com/v1beta/openai", model: "gemini-3.1-pro-preview" },
  zai: { host: "https://api.z.ai/api/paas/v4", model: "glm-5.1" },
  "kimi-coding": { host: "https://api.kimi.com/coding", model: "kimi-k2.6" },
  "kimi-coding-cn": { host: "https://api.kimi.com/coding/v1", model: "kimi-k2.6" },
  stepfun: { host: "https://api.stepfun.ai/step_plan/v1", model: "step-3.5-flash" },
  minimax: { host: "https://api.minimax.io/anthropic", model: "MiniMax-M2.7" },
  "minimax-cn": { host: "https://api.minimaxi.com/v1", model: "MiniMax-M2.7" },
  alibaba: { host: "https://dashscope-intl.aliyuncs.com/compatible-mode/v1", model: "qwen3.6-plus" },
  xai: { host: "https://api.x.ai/v1", model: "grok-4.20" },
  nvidia: { host: "https://integrate.api.nvidia.com/v1", model: "nvidia/nemotron-3-super-120b-a12b" },
  huggingface: { host: "https://router.huggingface.co/v1", model: "moonshotai/Kimi-K2.5" },
  arcee: { host: "https://api.arcee.ai/api/v1", model: "auto" },
  gmi: { host: "https://api.gmi-serving.com/v1", model: "auto" },
  "ollama-cloud": { host: "https://ollama.com/v1", model: "gpt-oss:120b" },
};

function hostFromBaseUrl(url: string): string {
  try {
    return new URL(url).host;
  } catch {
    return url
      .replace(/^https?:\/\//i, "")
      .split("/")[0]
      .trim();
  }
}

async function validateEndpointForProvider(
  selectedProvider: Provider | null,
  baseUrl: string,
  apiKey: string,
) {
  if (selectedProvider?.skipEndpointValidation) {
    return { ok: true as const };
  }
  return validateCustomEndpoint(baseUrl, apiKey);
}

function initialDropdownProvider(customProviderId: string | undefined): ProviderId | "custom" | "" {
  const id = customProviderId?.trim();
  if (!id) return "";
  if (DROPDOWN_PROVIDERS.includes(id as ProviderId)) return id as ProviderId;
  return "custom";
}

export function GetAccessPass() {
  const { t } = useI18n();
  const nav = useNavigate();
  const draft = useDraft();
  const [key, setKey] = useState(draft.apiKey);
  const [baseUrl, setBaseUrl] = useState(draft.customBaseUrl ?? "");
  const [modelId, setModelId] = useState(draft.customModel ?? "");
  const [customProviderId, setCustomProviderId] = useState(draft.customProviderId ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [preview, setPreview] = useState<LlmConfigPreview | null>(null);
  const [dropdownProvider, setDropdownProvider] = useState<ProviderId | "custom" | "">(
    initialDropdownProvider(draft.customProviderId),
  );
  const [validationStatus, setValidationStatus] = useState<"idle" | "validating" | "valid" | "invalid">("idle");
  const [validationMessage, setValidationMessage] = useState<string | null>(null);
  const provider = draft.providerId ? findProvider(draft.providerId) : null;
  const isCustom = provider?.id === "custom";
  const effectiveProvider = useMemo(() => {
    if (!provider) return null;
    if (!isCustom) return provider;
    if (dropdownProvider && dropdownProvider !== "custom") return findProvider(dropdownProvider);
    return null;
  }, [isCustom, provider, dropdownProvider]);

  useEffect(() => {
    invoke<LlmConfigPreview>("cmd_llm_config_preview").then(setPreview)
      .catch(() => setPreview({ hasSecret: false, provider: null, host: null, model: null, apiBaseUrl: null }));
  }, []);

  // Debounced auto-validation of the API key
  useEffect(() => {
    const pid = draft.providerId;
    const trimmed = key.trim();
    if (!trimmed || !pid) {
      setValidationStatus("idle");
      setValidationMessage(null);
      return;
    }
    if (preview?.hasSecret && !trimmed) {
      setValidationStatus("valid");
      setValidationMessage(null);
      return;
    }
    const timer = setTimeout(async () => {
      setValidationStatus("validating");
      try {
        const result = pid === "custom"
          ? await validateEndpointForProvider(effectiveProvider, baseUrl, key)
          : await validateKey(pid, key);
        setValidationStatus(result.ok ? "valid" : "invalid");
        setValidationMessage(result.message ?? null);
      } catch {
        setValidationStatus("invalid");
        setValidationMessage(t("pass.errGeneric"));
      }
    }, 800);
    return () => clearTimeout(timer);
  }, [key, baseUrl, draft.providerId, effectiveProvider, preview?.hasSecret, t]);

  useEffect(() => {
    if (draft.setupMode !== "quick" || !draft.useRecommendedDefaults) {
      updateDraft({ setupMode: "quick", useRecommendedDefaults: true });
    }
  }, [draft.setupMode, draft.useRecommendedDefaults]);

  useEffect(() => {
    if (!draft.providerId) nav("/onboarding/brain", { replace: true });
  }, [draft.providerId, nav]);

  // Pre-fill from saved preview
  useEffect(() => {
    if (!preview?.hasSecret || !isCustom) return;
    setBaseUrl((u) => (u.trim() ? u : preview.apiBaseUrl?.trim() ?? ""));
    setModelId((m) => (m.trim() ? m : preview.model?.trim() ?? ""));
  }, [preview, isCustom]);

  if (!provider) return null;

  async function openSignup() {
    if (!effectiveProvider?.signupUrl) return;
    try { await openUrl(effectiveProvider.signupUrl); } catch (e) { console.error(e); }
  }

  async function onSave() {
    const mode = "quick"; if (!provider) return;
    setBusy(true); setError(null);
    try {
      if (preview?.hasSecret && !key.trim()) {
        try { await invoke("cmd_set_personality", { name: draft.personality }); } catch {
          /* optional */
        }
        clearAllowChatWithoutApi(); nav(getNextPathAfterPass(mode), { replace: true }); return;
      }
      if (isCustom) {
        const dp = dropdownProvider && dropdownProvider !== "custom" ? dropdownProvider : "custom";
        const providerForSave = dp !== "custom" ? dp : customProviderId.trim() || "custom";
        const mid = dp !== "custom" ? (PROVIDER_PRESETS[dp]?.model ?? modelId.trim()) : modelId.trim();
        if (!mid) { setError(t("pass.errModel")); return; }
        const url = baseUrl.trim();
        const r = await validateEndpointForProvider(effectiveProvider, url, key);
        if (!r.ok) { setError(r.message ?? t("pass.errGeneric")); return; }
        await invoke("cmd_save_secret", {
          cfg: { provider: providerForSave, host: effectiveProvider?.host || hostFromBaseUrl(url), model: mid, api_base_url: normalizeOpenAiBaseUrl(url) },
          secret: key.trim(),
        });
        updateDraft({ apiKey: "", customBaseUrl: url, customModel: mid, customProviderId: providerForSave });
      } else {
        const r = await validateKey(provider.id, key);
        if (!r.ok) { setError(r.message ?? t("pass.errGeneric")); return; }
        const isDeepseek = provider.id === "deepseek";
        const dsPreset = isDeepseek ? PROVIDER_PRESETS.deepseek : null;
        await invoke("cmd_save_secret", {
          cfg: {
            provider: provider.id,
            host: provider.host,
            model: dsPreset ? dsPreset.model : null,
            api_base_url: isDeepseek
              ? normalizeOpenAiBaseUrl(`https://${provider.host}/v1`)
              : null,
          },
          secret: key.trim(),
        });
        updateDraft({ apiKey: "" });
      }
      try { await invoke("cmd_set_personality", { name: draft.personality }); } catch {
        /* optional */
      }
      clearAllowChatWithoutApi(); nav(getNextPathAfterPass(mode), { replace: true });
    } catch (e: unknown) {
      setError(typeof e === "string" ? e : (e as Error)?.message ?? t("pass.errSave"));
    } finally { setBusy(false); }
  }

  const continuingWithSaved = Boolean(preview?.hasSecret && !key.trim());
  const canSubmit = continuingWithSaved ? true : isCustom ? Boolean(key.trim() && baseUrl.trim() && modelId.trim()) : Boolean(key.trim());
  const f = "w-full rounded-[var(--radius-shell)] border border-zinc-300/90 bg-white/90 px-4 py-3 font-mono text-sm dark:border-zinc-700 dark:bg-zinc-900/90";

  const leadText = isCustom
    ? t("pass.customLead1")
    : effectiveProvider
      ? t("pass.providerLead", { label: effectiveProvider.label })
      : t("pass.lead");

  return (<div className="space-y-8">
    <div className="space-y-3">
      <h1 className="hd-wizard-title">{t("pass.title")}</h1>
      <p className="hd-wizard-lead">{leadText}</p>
    </div>

    {!isCustom && (<ol className="hd-glass-subtle list-decimal space-y-2.5 pl-6 pr-4 py-4 hd-wizard-body">
      <li>{t("pass.steps.s1", { label: provider.label })}</li>
      <li>{t("pass.steps.s2")}</li>
      <li>{t("pass.steps.s3")}</li>
    </ol>)}

    {isCustom && (<div className="space-y-2">
      <label className="hd-wizard-label">{t("pass.labelProvider")}</label>
      <select value={dropdownProvider} onChange={(e) => {
        const v = e.target.value as typeof dropdownProvider;
        setDropdownProvider(v);
        if (v && v !== "custom" && PROVIDER_PRESETS[v]) {
          setBaseUrl(PROVIDER_PRESETS[v].host);
          setModelId(PROVIDER_PRESETS[v].model);
          setCustomProviderId("");
          updateDraft({ customBaseUrl: PROVIDER_PRESETS[v].host, customModel: PROVIDER_PRESETS[v].model, customProviderId: "" });
        } else if (v === "custom") {
          setBaseUrl("");
          setModelId("");
          setCustomProviderId("");
          updateDraft({ customBaseUrl: "", customModel: "", customProviderId: "" });
        }
      }} className="w-full rounded-[var(--radius-shell)] border border-zinc-300/90 bg-white/90 px-4 py-3 text-sm dark:border-zinc-700 dark:bg-zinc-900/90">
        <option value="">{t("pass.selectProvider")}</option>
        {DROPDOWN_PROVIDERS.filter((pid) => pid !== "custom").map((pid) => <option key={pid} value={pid}>{findProvider(pid).label}</option>)}
        <option disabled>──</option>
        <option value="custom">{t("pass.providerCustomLabel")}</option>
      </select>
    </div>)}

    {isCustom && dropdownProvider === "custom" && (<div className="space-y-2">
      <label className="hd-wizard-label">{t("pass.labelCustomProviderId")}</label>
      <input type="text" autoComplete="off" spellCheck={false} value={customProviderId}
        onChange={(e) => { setCustomProviderId(e.target.value); updateDraft({ customProviderId: e.target.value }); }}
        placeholder={t("pass.phCustomProviderId")} className={f} />
      <p className="hd-wizard-hint">{t("pass.customProviderHint")}</p>
    </div>)}

    {isCustom && (<div className="space-y-2">
      <label className="hd-wizard-label">{t("pass.labelApiUrl")}</label>
      <input type="url" autoComplete="off" spellCheck={false} value={baseUrl}
        onChange={(e) => { setBaseUrl(e.target.value); updateDraft({ customBaseUrl: e.target.value }); }}
        placeholder={t("pass.phApiUrl")} className={f} />
    </div>)}

    {isCustom && (<div className="space-y-2">
      <label className="hd-wizard-label">{t("pass.labelModel")}</label>
      <input type="text" autoComplete="off" spellCheck={false} value={modelId}
        onChange={(e) => { setModelId(e.target.value); updateDraft({ customModel: e.target.value }); }}
        placeholder={t("pass.phModel")} className={f} />
    </div>)}

    <div className="space-y-2">
      <label className="hd-wizard-label">{isCustom ? t("pass.labelKeyCustom") : t("pass.labelKey")}</label>
      <div className="relative">
        <input type="password" autoComplete="off" spellCheck={false} value={key} onChange={(e) => setKey(e.target.value)}
          placeholder={preview?.hasSecret ? t("pass.keyPlaceholderSaved") : effectiveProvider?.keyPrefixHint ? `${effectiveProvider.keyPrefixHint}\u2026` : t("pass.phKey")}
          className={cn(
            f,
            "pr-10",
            validationStatus === "valid" && "border-emerald-400 dark:border-emerald-600",
            validationStatus === "invalid" && "border-red-400 dark:border-red-600",
          )} />
        {validationStatus === "validating" && (
          <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2">
            <Loader2 className="h-4 w-4 animate-spin text-zinc-400" />
          </span>
        )}
        {validationStatus === "valid" && (
          <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-emerald-500">
            <Check className="h-4 w-4" strokeWidth={3} />
          </span>
        )}
      </div>
      {validationStatus === "invalid" && validationMessage && (
        <p className="hd-wizard-body text-red-600 dark:text-red-400">{validationMessage}</p>
      )}
      {error && <p className="hd-wizard-body text-red-600 dark:text-red-400">{error}</p>}
    </div>

    {!isCustom && (<button type="button" onClick={openSignup}
      className="w-full rounded-[var(--radius-shell-lg)] border border-zinc-300/90 px-4 py-3 transition hover:bg-zinc-100/80 dark:border-zinc-700 dark:hover:bg-zinc-900/80">
      {t("pass.openVendor", { label: provider.label })}</button>)}

    <WizardFooter>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <WizardPrimaryButton onClick={() => nav(getBackPath("pass", draft.setupMode)!)}>
          {t("onboarding.back")}
        </WizardPrimaryButton>
        <WizardFooterActions>
          <button
            type="button"
            className="hd-wizard-hint rounded-[var(--radius-shell-lg)] px-4 py-2.5 underline-offset-2 hover:underline"
            onClick={() => {
              setAllowChatWithoutApi();
              nav("/chat", { replace: true });
            }}
          >
            {t("pass.skipCta")}
          </button>
          <WizardPrimaryButton onClick={() => void onSave()} disabled={busy || !canSubmit}>
            {busy ? t("pass.checkWait") : preview?.hasSecret && !key.trim() ? t("pass.continueCta") : t("pass.cta")}
          </WizardPrimaryButton>
        </WizardFooterActions>
      </div>
    </WizardFooter>
  </div>);
}
