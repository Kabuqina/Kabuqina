// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { invoke } from "@tauri-apps/api/core";
import { LlmConfigEditor } from "../../components/LlmConfigEditor";
import { clearAllowChatWithoutApi } from "../../lib/apiKeyGate";
import { CHAT_FROM_ONBOARDING_STATE } from "../../lib/chatLocationState";
import { useI18n } from "../../lib/i18n";
import { updateDraft, useDraft } from "../../lib/store";
import { getBackPath, getNextPathAfterPass } from "../flowConfig";
import { WizardFooter, WizardFooterActions, WizardPrimaryButton } from "../wizard-ui";

export function GetAccessPass() {
  const { t } = useI18n();
  const nav = useNavigate();
  const draft = useDraft();

  useEffect(() => {
    if (draft.setupMode !== "quick" || !draft.useRecommendedDefaults) {
      updateDraft({ setupMode: "quick", useRecommendedDefaults: true });
    }
  }, [draft.setupMode, draft.useRecommendedDefaults]);

  useEffect(() => {
    if (!draft.providerId) nav("/onboarding/brain", { replace: true });
  }, [draft.providerId, nav]);

  if (!draft.providerId) return null;

  async function afterSaved() {
    try {
      await invoke("cmd_set_personality", { name: draft.personality });
    } catch {
      /* optional */
    }
    clearAllowChatWithoutApi();
    // `pass` is now the last first-run step, so this finishes onboarding.
    nav(getNextPathAfterPass("quick"), { replace: true, state: CHAT_FROM_ONBOARDING_STATE });
  }

  return (
    <div className="space-y-8">
      <div className="space-y-3">
        <h1 className="hd-wizard-title">{t("pass.title")}</h1>
      </div>

      {draft.providerId !== "custom" ? (
        <ol className="hd-glass-subtle list-decimal space-y-2.5 pl-6 pr-4 py-4 hd-wizard-body">
          <li>{t("pass.steps.s1", { label: "DeepSeek" })}</li>
          <li>{t("pass.steps.s2")}</li>
          <li>{t("pass.steps.s3")}</li>
        </ol>
      ) : null}

      <LlmConfigEditor
        mode="onboarding"
        initialProviderId={draft.providerId}
        initialBaseUrl={draft.customBaseUrl}
        initialModel={draft.customModel}
        initialCustomProviderId={draft.customProviderId}
        onDraftChange={updateDraft}
        onSaved={afterSaved}
        renderActions={({ onSave, disabled, label }) => (
          <WizardFooter>
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <WizardPrimaryButton onClick={() => nav(getBackPath("pass", draft.setupMode)!)}>
                {t("onboarding.back")}
              </WizardPrimaryButton>
              <WizardFooterActions>
                <WizardPrimaryButton onClick={onSave} disabled={disabled}>
                  {label}
                </WizardPrimaryButton>
              </WizardFooterActions>
            </div>
          </WizardFooter>
        )}
      />
    </div>
  );
}
