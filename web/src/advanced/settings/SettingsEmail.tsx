// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useCallback, useEffect, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { confirm } from "../../lib/confirmDialog";
import { useI18n } from "../../lib/i18n";
import { cn } from "../../lib/cn";
import { StatusBanner } from "../../components/ui/StatusBanner";
import { PlatformButton } from "../../components/ui/PlatformButton";

export type EmailEnvSnapshot = {
  configured: boolean;
  authMode?: string;
  hasAddress?: boolean;
  hasPassword?: boolean;
  hasOauth2AccessToken?: boolean;
  hasOauth2RefreshToken?: boolean;
  hasOauth2ClientId?: boolean;
  hasImapHost?: boolean;
  hasSmtpHost?: boolean;
  addressHint?: string | null;
};

type EmailOAuthDeviceStart = {
  deviceCode: string;
  userCode: string;
  verificationUri: string;
  expiresIn: number;
  interval: number;
  message: string;
};

type EmailOAuthStatus = {
  hasDefaultClientId: boolean;
};

const inputClass = "hd-input font-mono dark:border-zinc-700 dark:bg-zinc-900/90 dark:text-zinc-100";

export function SettingsEmailBlock({ className }: { className?: string }) {
  const { t } = useI18n();
  const [env, setEnv] = useState<EmailEnvSnapshot | null>(null);
  const [address, setAddress] = useState("");
  const [password, setPassword] = useState("");
  const [authMode, setAuthMode] = useState<"password" | "oauth2">("password");
  const [oauth2AccessToken, setOauth2AccessToken] = useState("");
  const [oauth2RefreshToken, setOauth2RefreshToken] = useState("");
  const [oauth2ClientId, setOauth2ClientId] = useState("");
  const [oauth2Tenant, setOauth2Tenant] = useState("common");
  const [oauthFlow, setOauthFlow] = useState<EmailOAuthDeviceStart | null>(null);
  const [oauthHasDefaultClientId, setOauthHasDefaultClientId] = useState(false);
  const [showOauthAdvanced, setShowOauthAdvanced] = useState(false);
  const [oauthBusy, setOauthBusy] = useState(false);
  const [imapHost, setImapHost] = useState("");
  const [smtpHost, setSmtpHost] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [removing, setRemoving] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const snap = await invoke<EmailEnvSnapshot>("cmd_email_env_status");
      setEnv(snap);
      const oauth = await invoke<EmailOAuthStatus>("cmd_email_oauth_status");
      setOauthHasDefaultClientId(oauth.hasDefaultClientId);
    } catch {
      setEnv(null);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function saveConfig() {
    const addr = address.trim();
    const pass = password.trim();
    const accessToken = oauth2AccessToken.trim();
    const refreshToken = oauth2RefreshToken.trim();
    const clientId = oauth2ClientId.trim();
    const imap = imapHost.trim();
    const smtp = smtpHost.trim();
    const authReady =
      authMode === "password"
        ? !!pass
        : !!accessToken || (!!clientId && !!refreshToken);
    if (!addr || !authReady || !imap || !smtp) return;
    setSaving(true);
    setError(null);
    try {
      await invoke("cmd_email_save_config", {
        address: addr,
        password: pass,
        imapHost: imap,
        smtpHost: smtp,
        authMode,
        oauth2AccessToken: accessToken,
        oauth2RefreshToken: refreshToken,
        oauth2ClientId: clientId,
        oauth2ClientSecret: "",
        oauth2Tenant: oauth2Tenant.trim() || "common",
        oauth2TokenUrl: "",
        oauth2Scope: "",
      });
      setShowForm(false);
      setAddress("");
      setPassword("");
      setAuthMode("password");
      setOauth2AccessToken("");
      setOauth2RefreshToken("");
      setOauth2ClientId("");
      setOauth2Tenant("common");
      setShowOauthAdvanced(false);
      setImapHost("");
      setSmtpHost("");
      void refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  }

  async function startOutlookOAuth() {
    const clientId = oauth2ClientId.trim();
    if (!clientId && !oauthHasDefaultClientId) return;
    setOauthBusy(true);
    setError(null);
    try {
      const flow = await invoke<EmailOAuthDeviceStart>("cmd_email_oauth_device_start", {
        clientId,
        tenant: oauth2Tenant.trim() || "common",
        scope: "",
      });
      setOauthFlow(flow);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setOauthBusy(false);
    }
  }

  async function finishOutlookOAuth() {
    const flow = oauthFlow;
    const addr = address.trim();
    const imap = imapHost.trim();
    const smtp = smtpHost.trim();
    const clientId = oauth2ClientId.trim();
    if (!flow || !addr || !imap || !smtp || (!clientId && !oauthHasDefaultClientId)) return;
    setOauthBusy(true);
    setError(null);
    try {
      await invoke("cmd_email_oauth_device_finish", {
        address: addr,
        imapHost: imap,
        smtpHost: smtp,
        clientId,
        tenant: oauth2Tenant.trim() || "common",
        deviceCode: flow.deviceCode,
        interval: flow.interval,
        expiresIn: flow.expiresIn,
      });
      setShowForm(false);
      setAddress("");
      setPassword("");
      setAuthMode("password");
      setOauth2AccessToken("");
      setOauth2RefreshToken("");
      setOauth2ClientId("");
      setOauth2Tenant("common");
      setOauthFlow(null);
      setShowOauthAdvanced(false);
      setImapHost("");
      setSmtpHost("");
      void refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setOauthBusy(false);
    }
  }

  async function handleRemove() {
    const ok = await confirm({
      title: t("settings.removeConfigAskTitle"),
      message: t("settings.removeConfigAsk"),
      confirmLabel: t("dialog.remove"),
      cancelLabel: t("dialog.cancel"),
      tone: "warning",
    });
    if (!ok) return;
    setRemoving(true);
    try {
      await invoke("cmd_email_env_remove");
      setShowForm(false);
      void refresh();
    } catch {
      void refresh();
    } finally {
      setRemoving(false);
    }
  }

  return (
    <div className={cn("w-full min-w-0 space-y-3", className)}>
      {!env?.configured && !showForm ? (
        <>
          <StatusBanner variant="neutral" title={t("settings.emailNotConfigured")} />
          <PlatformButton onClick={() => setShowForm(true)}>
            {t("settings.emailSetup")}
          </PlatformButton>
        </>
      ) : null}

      {env?.configured && !showForm ? (
        <div className="rounded-[var(--radius-shell-lg)] border border-emerald-200/90 bg-emerald-50/60 px-3 py-2.5 text-sm dark:border-emerald-900/60 dark:bg-emerald-950/35">
          <p className="font-medium text-emerald-900 dark:text-emerald-100">{t("settings.emailAlreadyTitle")}</p>
          {env.addressHint ? (
            <p className="mt-1.5 font-mono text-xs text-emerald-950/90 dark:text-emerald-50/90">
              {t("settings.emailAddressHint", { hint: env.addressHint })}
            </p>
          ) : null}
          <p className="mt-1 font-mono text-xs text-emerald-950/80 dark:text-emerald-50/80">
            {t("settings.emailAuthHint", { mode: env.authMode === "oauth2" ? "OAuth2" : "Password" })}
          </p>
        </div>
      ) : null}

      {env?.configured && !showForm ? (
        <div className="flex flex-wrap items-center gap-2">
          <PlatformButton onClick={() => setShowForm(true)}>
            {t("settings.emailReconfigure")}
          </PlatformButton>
          <PlatformButton variant="danger" onClick={() => void handleRemove()} disabled={removing}>
            {removing ? "…" : t("settings.emailRemoveConfig")}
          </PlatformButton>
        </div>
      ) : null}

      {showForm ? (
        <div className="kq-info-panel space-y-3 px-3 py-3 dark:border-[#D4C5E2]/20 dark:bg-[#D4C5E2]/10">
          <p className="text-xs leading-relaxed text-zinc-600 dark:text-zinc-400">
            {t("settings.emailFormLead")}
          </p>
          <input
            className={inputClass}
            type="text"
            value={address}
            placeholder={t("settings.emailAddressPlaceholder")}
            autoComplete="off"
            spellCheck={false}
            onChange={(e) => setAddress(e.target.value)}
          />
          <select
            className={inputClass}
            value={authMode}
            onChange={(e) => setAuthMode(e.target.value === "oauth2" ? "oauth2" : "password")}
          >
            <option value="password">{t("settings.emailAuthPassword")}</option>
            <option value="oauth2">{t("settings.emailAuthOauth2")}</option>
          </select>
          {authMode === "password" ? (
            <input
              className={inputClass}
              type="password"
              value={password}
              placeholder={t("settings.emailPasswordPlaceholder")}
              autoComplete="off"
              spellCheck={false}
              onChange={(e) => setPassword(e.target.value)}
            />
          ) : (
            <>
              <input
                className={inputClass}
                type="password"
                value={oauth2AccessToken}
                placeholder={t("settings.emailOauth2AccessTokenPlaceholder")}
                autoComplete="off"
                spellCheck={false}
                onChange={(e) => setOauth2AccessToken(e.target.value)}
              />
              <input
                className={inputClass}
                type="password"
                value={oauth2RefreshToken}
                placeholder={t("settings.emailOauth2RefreshTokenPlaceholder")}
                autoComplete="off"
                spellCheck={false}
                onChange={(e) => setOauth2RefreshToken(e.target.value)}
              />
              <button
                type="button"
                className="hd-link text-xs font-medium underline-offset-2"
                onClick={() => setShowOauthAdvanced((v) => !v)}
              >
                {showOauthAdvanced
                  ? t("settings.emailOauth2HideAdvanced")
                  : t("settings.emailOauth2ShowAdvanced")}
              </button>
              {showOauthAdvanced || !oauthHasDefaultClientId ? (
                <div className="space-y-2 rounded-[var(--radius-shell-lg)] border border-zinc-200 bg-white/70 px-3 py-2 dark:border-zinc-700 dark:bg-zinc-900/70">
                  {!oauthHasDefaultClientId ? (
                    <p className="text-xs text-zinc-500 dark:text-zinc-400">
                      {t("settings.emailOauth2NoBuiltInApp")}
                    </p>
                  ) : null}
                  <input
                    className={inputClass}
                    type="text"
                    value={oauth2ClientId}
                    placeholder={t("settings.emailOauth2ClientIdPlaceholder")}
                    autoComplete="off"
                    spellCheck={false}
                    onChange={(e) => setOauth2ClientId(e.target.value)}
                  />
                  <input
                    className={inputClass}
                    type="text"
                    value={oauth2Tenant}
                    placeholder={t("settings.emailOauth2TenantPlaceholder")}
                    autoComplete="off"
                    spellCheck={false}
                    onChange={(e) => setOauth2Tenant(e.target.value)}
                  />
                </div>
              ) : null}
              <div className="rounded-[var(--radius-shell-lg)] border border-zinc-200 bg-white/70 px-3 py-2 text-xs dark:border-zinc-700 dark:bg-zinc-900/70">
                <div className="flex flex-wrap items-center gap-2">
                  <PlatformButton
                    disabled={oauthBusy || (!oauthHasDefaultClientId && !oauth2ClientId.trim())}
                    onClick={() => void startOutlookOAuth()}
                  >
                    {oauthBusy ? "…" : t("settings.emailOauth2Start")}
                  </PlatformButton>
                  <PlatformButton
                    variant="primary"
                    disabled={
                      oauthBusy ||
                      !oauthFlow ||
                      !address.trim() ||
                      !imapHost.trim() ||
                      !smtpHost.trim() ||
                      (!oauthHasDefaultClientId && !oauth2ClientId.trim())
                    }
                    onClick={() => void finishOutlookOAuth()}
                  >
                    {oauthBusy ? "…" : t("settings.emailOauth2Finish")}
                  </PlatformButton>
                </div>
                {oauthFlow ? (
                  <div className="mt-2 space-y-1 text-zinc-600 dark:text-zinc-300">
                    <p>{t("settings.emailOauth2Code", { code: oauthFlow.userCode })}</p>
                    <p className="break-all">{oauthFlow.verificationUri}</p>
                    <p>{oauthFlow.message}</p>
                  </div>
                ) : (
                  <p className="mt-2 text-zinc-500">{t("settings.emailOauth2StartHint")}</p>
                )}
              </div>
            </>
          )}
          <input
            className={inputClass}
            type="text"
            value={imapHost}
            placeholder={t("settings.emailImapPlaceholder")}
            autoComplete="off"
            spellCheck={false}
            onChange={(e) => setImapHost(e.target.value)}
          />
          <input
            className={inputClass}
            type="text"
            value={smtpHost}
            placeholder={t("settings.emailSmtpPlaceholder")}
            autoComplete="off"
            spellCheck={false}
            onChange={(e) => setSmtpHost(e.target.value)}
          />
          <div className="flex flex-wrap items-center gap-2">
            <PlatformButton
              variant="primary"
              onClick={() => void saveConfig()}
              disabled={
                saving ||
                !address.trim() ||
                !imapHost.trim() ||
                !smtpHost.trim() ||
                (authMode === "password"
                  ? !password.trim()
                  : !oauth2AccessToken.trim() && (!oauth2ClientId.trim() || !oauth2RefreshToken.trim()))
              }
            >
              {saving ? "…" : t("settings.emailFormSave")}
            </PlatformButton>
            <PlatformButton onClick={() => { setShowForm(false); setError(null); setAddress(""); setPassword(""); setAuthMode("password"); setOauth2AccessToken(""); setOauth2RefreshToken(""); setOauth2ClientId(""); setOauth2Tenant("common"); setOauthFlow(null); setShowOauthAdvanced(false); setImapHost(""); setSmtpHost(""); }}>
              {t("settings.emailFormCancel")}
            </PlatformButton>
          </div>
          {error ? (
            <StatusBanner variant="error" title={t("settings.emailFormError", { msg: error })} />
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
