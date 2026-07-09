// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useMemo, useState } from "react";
import { AudioLines, Mic } from "lucide-react";
import { useI18n } from "../../lib/i18n";
import { cmdSaveVoiceSetup, type VoiceSetupSection } from "../../lib/voice-setup-api";
import { CATALOG_STT, CATALOG_TTS } from "../../onboarding/setupCatalog/optionData";
import type { SetupCatalogOption } from "../../onboarding/setupCatalog/optionTypes";

/**
 * UI catalog row id → canonical ``<section>.provider`` string written to
 * config.yaml. Mirrors the mapping in
 * ``onboarding/steps/SectionPlaceholderStep.tsx`` so the Settings tab and the
 * onboarding wizard persist identical provider strings.
 */
const TTS_UI_TO_PROVIDER: Record<string, string | null> = {
  edge: "edge",
  elevenlabs: "elevenlabs",
  minimax: "minimax",
  mistral_tts: "mistral",
  xai: "xai",
  neutts: "neutts",
  xfyun: "xfyun",
};
const STT_UI_TO_PROVIDER: Record<string, string | null> = {
  local_whisper_cpp: "local_command",
};

function uiIdToProvider(section: VoiceSetupSection, optionId: string): string | null {
  if (section === "stt") return STT_UI_TO_PROVIDER[optionId] ?? optionId;
  return TTS_UI_TO_PROVIDER[optionId] ?? optionId;
}

function VoiceSectionCard({
  section,
  title,
  hint,
  options,
}: {
  section: VoiceSetupSection;
  title: string;
  hint: string;
  options: SetupCatalogOption[];
}) {
  const { locale } = useI18n();
  const zh = locale === "zh";
  const [optionId, setOptionId] = useState<string>(
    options.find((o) => o.isDefault)?.id ?? options[0]?.id ?? "",
  );
  // Field values keyed by option id so switching providers doesn't wipe input.
  const [configByOption, setConfigByOption] = useState<Record<string, Record<string, string>>>({});
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  const selected = useMemo(() => options.find((o) => o.id === optionId), [options, optionId]);
  const fields = selected?.configFields ?? [];
  const values = configByOption[optionId] ?? {};

  const setField = (fieldId: string, value: string) => {
    setConfigByOption((prev) => ({
      ...prev,
      [optionId]: { ...(prev[optionId] ?? {}), [fieldId]: value },
    }));
  };

  const onSave = async () => {
    setMsg(null);
    setSaving(true);
    try {
      const provider = uiIdToProvider(section, optionId);
      const env: Record<string, string> = {};
      for (const [k, v] of Object.entries(values)) {
        if (typeof v === "string" && v.trim()) env[k] = v;
      }
      await cmdSaveVoiceSetup(section, provider, env);
      setMsg({ ok: true, text: zh ? "已保存，立即生效。" : "Saved and applied." });
    } catch (e) {
      setMsg({ ok: false, text: e instanceof Error ? e.message : String(e) });
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="hd-setting-card space-y-4 px-4 py-4">
      <div className="flex items-center gap-2">
        {section === "tts" ? (
          <AudioLines className="h-4 w-4 text-[var(--kq-color-primary)]" />
        ) : (
          <Mic className="h-4 w-4 text-[var(--kq-color-primary)]" />
        )}
        <h3 className="text-sm font-semibold text-[var(--kq-color-strong)]">{title}</h3>
      </div>
      <p className="text-xs leading-relaxed text-[var(--kq-color-muted)]">{hint}</p>

      <label className="block space-y-1.5">
        <span className="text-xs font-medium text-[var(--kq-color-ink)]">
          {zh ? "服务提供方" : "Provider"}
        </span>
        <select
          value={optionId}
          onChange={(e) => {
            setOptionId(e.target.value);
            setMsg(null);
          }}
          className="w-full rounded-[var(--radius-shell)] border border-[var(--kq-color-border)] bg-[var(--kq-input-surface)] px-4 py-3 text-sm"
        >
          {options.map((o) => (
            <option key={o.id} value={o.id}>
              {o.name[locale]}
            </option>
          ))}
        </select>
      </label>

      {selected?.defaultHint ? (
        <p className="text-xs text-[var(--kq-color-muted)]">{selected.defaultHint[locale]}</p>
      ) : null}

      {fields.map((f) => (
        <label key={f.id} className="block space-y-1.5">
          <span className="text-xs font-medium text-[var(--kq-color-ink)]">{f.label[locale]}</span>
          <input
            type={f.kind === "password" ? "password" : "text"}
            value={values[f.id] ?? ""}
            placeholder={f.placeholder[locale]}
            autoComplete="off"
            spellCheck={false}
            onChange={(e) => setField(f.id, e.target.value)}
            className="w-full rounded-[var(--radius-shell)] border border-[var(--kq-color-border)] bg-[var(--kq-input-surface)] px-4 py-3 text-sm"
          />
        </label>
      ))}

      <div className="flex items-center gap-3">
        <button
          type="button"
          disabled={saving}
          onClick={onSave}
          className="kq-btn-primary rounded-lg px-4 py-2 text-sm disabled:opacity-60"
        >
          {saving ? (zh ? "保存中…" : "Saving…") : zh ? "保存" : "Save"}
        </button>
        {msg ? (
          <span
            className={
              msg.ok ? "text-xs text-emerald-600 dark:text-emerald-400" : "text-xs text-red-600 dark:text-red-400"
            }
            role={msg.ok ? "status" : "alert"}
          >
            {msg.text}
          </span>
        ) : null}
      </div>
    </div>
  );
}

/**
 * Settings → 语音 tab: configure TTS (「朗读」) and STT (麦克风听写) providers and
 * their credentials. Writes via ``cmd_save_voice_setup`` (config.yaml provider +
 * hermes-home/.env keys, applied to the running process without a restart).
 */
export function SettingsVoice() {
  const { locale } = useI18n();
  const zh = locale === "zh";
  return (
    <div className="space-y-5">
      <VoiceSectionCard
        section="tts"
        title={zh ? "语音合成（朗读）" : "Text-to-Speech (Read aloud)"}
        hint={
          zh
            ? "聊天回复的「朗读」使用的合成服务。选「讯飞语音合成（在线）」并填入讯飞三件套即可用讯飞发音人。"
            : "The voice used by the chat “Read aloud” button. Pick iFlytek TTS and fill in the three keys to use iFlytek voices."
        }
        options={CATALOG_TTS}
      />
      <VoiceSectionCard
        section="stt"
        title={zh ? "语音识别（麦克风听写）" : "Speech-to-Text (Microphone)"}
        hint={
          zh
            ? "麦克风说话转文字使用的识别服务。选「讯飞语音听写（在线）」并填入讯飞三件套即可用讯飞听写。"
            : "The service used to transcribe microphone input. Pick iFlytek IAT and fill in the three keys to use iFlytek dictation."
        }
        options={CATALOG_STT}
      />
    </div>
  );
}
