// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useCallback, useEffect, useLayoutEffect, useMemo, useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { useI18n } from "../../lib/i18n";
import { getDraftSnapshot, updateDraft, useDraft } from "../../lib/store";
import { CHAT_FROM_ONBOARDING_STATE } from "../../lib/chatLocationState";
import { cmdSaveVoiceSetup, type VoiceSetupSection } from "../../lib/voice-setup-api";
import { CATALOG_BY_SECTION } from "../setupCatalog/optionData";
import { SetupOptionsTable } from "../SetupOptionsTable";
import { getBackPath, getNextPath, getRedirectForInvalidUrlStep, isLastStep } from "../flowConfig";
import type { PostPassSectionId } from "../setupCatalog/optionTypes";
import {
  getInitialSectionSelection,
  SECTION_SELECTION_MODE,
  selectionSatisfied,
} from "../sectionSelection";
import { WizardFooter, WizardFooterActions, WizardPrimaryButton } from "../wizard-ui";

export type { PostPassSectionId };

/**
 * Map a UI catalog row id to the canonical ``tts.provider`` string Hermes
 * expects in ``config.yaml`` (see ``hermes_cli/config.py`` DEFAULT_CONFIG.tts).
 * Rows that don't correspond to a writable ``tts.provider`` value (e.g. the
 * Nous-subscription routing row, which is handled via subscription state, not
 * by writing a provider string) map to ``null`` so we only persist env vars
 * and leave the existing config alone.
 */
const TTS_UI_TO_PROVIDER: Record<string, string | null> = {
  edge: "edge",
  openai_tts: "openai",
  elevenlabs: "elevenlabs",
  minimax: "minimax",
  mistral_tts: "mistral",
  gemini_tts: "gemini",
  xai: "xai",
  neutts: "neutts",
  nous_openai_tts: null,
};

/**
 * STT row ids mostly match canonical ``stt.provider`` strings 1:1, except for
 * ``local_whisper_cpp`` — a UI-only label for the bundled whisper.cpp
 * wrapper. The desktop_entrypoint wires ``HERMES_LOCAL_STT_COMMAND`` to that
 * wrapper, so the wizard just needs to set the provider to ``local_command``
 * for Hermes to take the wrapper path.
 */
const STT_UI_TO_PROVIDER: Record<string, string | null> = {
  local_whisper_cpp: "local_command",
};

function uiIdToProvider(section: PostPassSectionId, optionId: string): string | null {
  if (section === "stt") return STT_UI_TO_PROVIDER[optionId] ?? optionId;
  if (section === "tts") return TTS_UI_TO_PROVIDER[optionId] ?? null;
  return null;
}

export function SectionPlaceholderStep({ id }: { id: PostPassSectionId }) {
  const { t } = useI18n();
  const nav = useNavigate();
  const draft = useDraft();
  const mode = draft.setupMode;
  const redirect = getRedirectForInvalidUrlStep(id, mode);

  const next = getNextPath(id, mode);
  const last = isLastStep(id, mode);
  const catalog = CATALOG_BY_SECTION[id];
  const selMode = SECTION_SELECTION_MODE[id];
  const initialSel = useMemo(() => getInitialSectionSelection(id), [id]);
  const rowSel = draft.wizardSelection?.[id] ?? initialSel;

  useLayoutEffect(() => {
    if (draft.wizardSelection?.[id] != null) return;
    updateDraft({
      wizardSelection: {
        ...(draft.wizardSelection ?? {}),
        [id]: initialSel,
      },
    });
  }, [id, initialSel, draft.wizardSelection]);

  const canProceed = useMemo(() => selectionSatisfied(rowSel, selMode), [rowSel, selMode]);

  const isVoiceSection = id === "tts" || id === "stt";
  const [saveErr, setSaveErr] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (draft.setupMode !== "quick" || !draft.useRecommendedDefaults) {
      updateDraft({ setupMode: "quick", useRecommendedDefaults: true });
    }
  }, [draft.setupMode, draft.useRecommendedDefaults]);

  const persistVoiceSection = useCallback(async (): Promise<boolean> => {
    if (!isVoiceSection) return true;
    const draftNow = getDraftSnapshot();
    const sel = draftNow.wizardSelection?.[id];
    if (!sel || sel.kind === "skip") {
      // User chose "skip — keep defaults": don't touch config or .env.
      return true;
    }
    if (sel.kind !== "single" || !sel.optionId) return true;
    const provider = uiIdToProvider(id as PostPassSectionId, sel.optionId);
    const slice = draftNow.wizardConfig?.[id]?.[sel.optionId] ?? {};
    const env: Record<string, string> = {};
    for (const [k, v] of Object.entries(slice)) {
      if (typeof v === "string" && v.trim()) env[k] = v;
    }
    setSaveErr(null);
    setSaving(true);
    try {
      await cmdSaveVoiceSetup(id as VoiceSetupSection, provider, env);
      return true;
    } catch (e) {
      setSaveErr(e instanceof Error ? e.message : String(e));
      return false;
    } finally {
      setSaving(false);
    }
  }, [id, isVoiceSection]);

  if (redirect) {
    return <Navigate to={redirect} replace />;
  }

  return (
    <div className="space-y-8">
      <div className="space-y-3">
        <h1 className="hd-wizard-title">{t(`setupSection.${id}.title`)}</h1>
        <p className="hd-wizard-lead">{t(`setupSection.${id}.lead`)}</p>
      </div>
      <div className="space-y-2">
        <SetupOptionsTable
          section={id}
          items={catalog}
          selectionMode={selMode}
          defaultSelection={initialSel}
          modalSize={id === "gateway" ? "lg" : "md"}
        />
        {!canProceed ? (
          <p className="hd-wizard-hint text-amber-800 dark:text-amber-200" role="status">
            {t("setupOptions.mustChoose")}
          </p>
        ) : null}
      </div>
      {saveErr ? (
        <p className="hd-wizard-body text-red-600 dark:text-red-400" role="alert">
          {t("setupOptions.errSave")} {saveErr}
        </p>
      ) : null}
      <WizardFooter>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <WizardPrimaryButton onClick={() => nav(getBackPath(id, mode)!)}>
            {t("onboarding.back")}
          </WizardPrimaryButton>
          <WizardFooterActions>
            {last ? (
              <WizardPrimaryButton
                disabled={!canProceed || saving}
                onClick={async () => {
                  if (!canProceed) return;
                  const ok = await persistVoiceSection();
                  if (!ok) return;
                  // Avoid clearDraft() here: it clears setupMode and this step re-renders
                  // `<Navigate to …/mode>` before `/chat` is applied. ChatPage clears draft
                  // when it receives CHAT_FROM_ONBOARDING_STATE.
                  nav("/chat", { replace: true, state: CHAT_FROM_ONBOARDING_STATE });
                }}
              >
                {saving ? t("setupOptions.saving") : t("onboarding.finishToChat")}
              </WizardPrimaryButton>
            ) : (
              <WizardPrimaryButton
                disabled={!canProceed || saving}
                onClick={async () => {
                  if (!canProceed || next === "complete") return;
                  const ok = await persistVoiceSection();
                  if (!ok) return;
                  nav(next, { replace: true });
                }}
              >
                {saving ? t("setupOptions.saving") : t("onboarding.next")}
              </WizardPrimaryButton>
            )}
          </WizardFooterActions>
        </div>
      </WizardFooter>
    </div>
  );
}
