// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useEffect, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { Key, Loader2 } from "lucide-react";
import { Section } from "../../components/ui/Section";
import { Button } from "../../components/ui/Button";
import { useI18n } from "../../lib/i18n";
import { findProvider } from "../../lib/providers";
import { normalizeOpenAiBaseUrl } from "../../lib/validate";


type LlmConfigPreview = {
  hasSecret: boolean;
  provider: string | null;
  host: string | null;
  model: string | null;
  apiBaseUrl: string | null;
};

type SavePayload = {
  cfg: {
    provider: string;
    host: string;
    model: string | null;
    api_base_url: string | null;
  };
  secret: string | null;
};

export function SettingsLlmConfig() {
  const { t } = useI18n();
  const [preview, setPreview] = useState<LlmConfigPreview | null>(null);
  const [baseUrl, setBaseUrl] = useState("");
  const [model, setModel] = useState("");
  const [secret, setSecret] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savedNotice, setSavedNotice] = useState(false);

  useEffect(() => {
    invoke<LlmConfigPreview>("cmd_llm_config_preview")
      .then((p) => {
        setPreview(p);
        setBaseUrl(p.apiBaseUrl ?? "");
        setModel(p.model ?? "");
      })
      .catch(() => setPreview({ hasSecret: false, provider: null, host: null, model: null, apiBaseUrl: null }));
  }, []);

  const isCustom = preview?.provider === "custom";
  const providerLabel = preview?.provider
    ? (() => {
        try {
          return findProvider(preview.provider as Parameters<typeof findProvider>[0]).label;
        } catch {
          return preview.provider;
        }
      })()
    : "—";

  const canSave = isCustom
    ? Boolean(model.trim() && baseUrl.trim())
    : Boolean(model.trim());

  async function onSave() {
    if (!preview?.provider) return;
    setBusy(true);
    setError(null);
    setSavedNotice(false);
    try {
      const url = baseUrl.trim();
      const payload: SavePayload = {
        cfg: {
          provider: preview.provider,
          host: preview.host ?? "",
          model: model.trim() || null,
          api_base_url: isCustom && url ? normalizeOpenAiBaseUrl(url) : (preview.apiBaseUrl ?? null),
        },
        secret: secret.trim() || null,
      };
      await invoke("cmd_update_llm_config", payload);
      setSavedNotice(true);
      setSecret("");
    } catch (e: unknown) {
      setError(typeof e === "string" ? e : (e as Error)?.message ?? t("pass.errSave"));
    } finally {
      setBusy(false);
    }
  }

  const f =
    "w-full rounded-[var(--radius-shell)] border border-zinc-300/90 bg-white/90 px-4 py-3 font-mono text-sm dark:border-zinc-700 dark:bg-zinc-900/90";

  return (
    <Section icon={Key} title={t("settings.llmConfigTitle")} desc={t("settings.llmConfigDesc")}>
      <div className="space-y-4">
        {preview == null ? (
          <p className="text-sm text-[var(--kq-color-muted)]">{t("settings.loadPackagesChecking")}</p>
        ) : (
          <>
            <div className="space-y-1.5">
              <label className="hd-wizard-label">{t("settings.llmConfigProvider")}</label>
              <p className="text-sm text-[var(--kq-color-ink)] dark:text-zinc-300">{providerLabel}</p>
            </div>

            {isCustom && (
              <div className="space-y-1.5">
                <label className="hd-wizard-label">{t("settings.llmConfigApiUrl")}</label>
                <input
                  type="url"
                  autoComplete="off"
                  spellCheck={false}
                  value={baseUrl}
                  onChange={(e) => setBaseUrl(e.target.value)}
                  placeholder="https://…"
                  className={f}
                />
              </div>
            )}

            <div className="space-y-1.5">
              <label className="hd-wizard-label">{t("settings.llmConfigModel")}</label>
              <input
                type="text"
                autoComplete="off"
                spellCheck={false}
                value={model}
                onChange={(e) => setModel(e.target.value)}
                placeholder={t("pass.phModel")}
                className={f}
              />
            </div>

            <div className="space-y-1.5">
              <label className="hd-wizard-label">{t("settings.llmConfigKey")}</label>
              <input
                type="password"
                autoComplete="off"
                spellCheck={false}
                value={secret}
                onChange={(e) => setSecret(e.target.value)}
                placeholder={t("settings.llmConfigKeyHint")}
                className={f}
              />
              <p className="hd-wizard-hint">{t("settings.llmConfigKeyHint")}</p>
            </div>

            <div className="flex flex-wrap items-center gap-3">
              <Button onClick={() => void onSave()} disabled={busy || !canSave}>
                {busy ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    {t("settings.llmConfigSaving")}
                  </>
                ) : (
                  t("settings.llmConfigSave")
                )}
              </Button>
              {savedNotice && (
                <span className="text-sm text-emerald-600 dark:text-emerald-400">{t("settings.llmConfigSaved")}</span>
              )}
            </div>

            {error && (
              <p className="text-sm text-red-600 dark:text-red-400" role="alert">
                {error}
              </p>
            )}
          </>
        )}
      </div>
    </Section>
  );
}
