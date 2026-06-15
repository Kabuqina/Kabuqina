// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useEffect, useId, useState, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { useI18n } from "../../lib/i18n";
import { updateDraft, useDraft } from "../../lib/store";
import type { ProviderId } from "../../lib/providers";
import { cn } from "../../lib/cn";
import { getBackPath } from "../flowConfig";
import {
  WizardFooter,
  WizardFooterActions,
  WizardPrimaryButton,
  WizardSecondaryButton,
} from "../wizard-ui";

type BrainChoice = "deepseek" | "custom";

export function PickBrain() {
  const { t } = useI18n();
  const nav = useNavigate();
  const draft = useDraft();
  const groupId = useId();

  const [choice, setChoice] = useState<BrainChoice | null>(() => {
    if (draft.providerId === "deepseek") return "deepseek";
    if (draft.providerId === "custom") return "custom";
    return null;
  });

  useEffect(() => {
    if (draft.setupMode !== "quick" || !draft.useRecommendedDefaults) {
      updateDraft({ setupMode: "quick", useRecommendedDefaults: true });
    }
  }, [draft.setupMode, draft.useRecommendedDefaults]);

  useEffect(() => {
    if (draft.providerId === "deepseek") setChoice("deepseek");
    else if (draft.providerId === "custom") setChoice("custom");
  }, [draft.providerId]);

  function applyAndGo(providerId: ProviderId, customBaseUrl: string) {
    updateDraft({ providerId, customBaseUrl, customModel: "" });
    nav("/onboarding/pass");
  }

  function onNext() {
    if (!choice) return;
    if (choice === "deepseek") applyAndGo("deepseek", "");
    else applyAndGo("custom", "");
  }

  return (
    <div className="space-y-8">
      <div className="space-y-3">
        <h1 className="hd-wizard-title" id={`${groupId}-label`}>
          {t("brain.title")}
        </h1>
      </div>

      <div className="space-y-3" role="radiogroup" aria-labelledby={`${groupId}-label`}>
        <BrainOption
          selected={choice === "deepseek"}
          onSelect={() => setChoice("deepseek")}
          title={
            <div className="flex items-baseline justify-between gap-3">
              <div className="hd-wizard-card-title">DeepSeek</div>
              <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800 dark:bg-amber-900/50 dark:text-amber-200">
                {t("brain.recommended")}
              </span>
            </div>
          }
          description={t("brain.starter.title")}
          recommendedHover
        />

        <BrainOption
          selected={choice === "custom"}
          onSelect={() => setChoice("custom")}
          title={<div className="hd-wizard-card-title">{t("brain.customTitle")}</div>}
          description={t("brain.customBody")}
        />
      </div>

      <WizardFooter>
        <WizardFooterActions className="w-full sm:justify-between">
          <WizardSecondaryButton onClick={() => nav(getBackPath("brain", draft.setupMode)!)}>
            {t("onboarding.back")}
          </WizardSecondaryButton>
          <WizardPrimaryButton disabled={choice == null} onClick={onNext}>
            {t("onboarding.next")}
          </WizardPrimaryButton>
        </WizardFooterActions>
      </WizardFooter>
    </div>
  );
}

function BrainOption({
  selected,
  onSelect,
  title,
  description,
  recommendedHover,
}: {
  selected: boolean;
  onSelect: () => void;
  title: ReactNode;
  description: string;
  recommendedHover?: boolean;
}) {
  return (
    <button
      type="button"
      role="radio"
      aria-checked={selected}
      onClick={onSelect}
      className={cn(
        "hd-glass-subtle flex w-full gap-3 p-5 text-left transition",
        recommendedHover
          ? selected
            ? "border-amber-400/90 bg-amber-50/70 ring-2 ring-amber-400/35 dark:border-amber-700/70 dark:bg-amber-950/35 dark:ring-amber-600/35"
            : "hover:border-amber-300/80 hover:bg-amber-50/40 dark:hover:border-amber-700/50 dark:hover:bg-amber-950/20"
          : selected
            ? "border-[var(--kq-color-primary)]/70 bg-[var(--kq-color-primary-pale)]/60 ring-2 ring-[var(--kq-color-primary)]/30"
            : "hover:border-[var(--kq-color-primary)]/40",
        "active:scale-[0.99]"
      )}
    >
      <span
        className={cn(
          "mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full border-2 transition-colors",
          selected
            ? recommendedHover
              ? "border-amber-600 dark:border-amber-400"
              : "border-[var(--kq-color-primary)]"
            : "border-[var(--kq-color-muted)]/50"
        )}
        aria-hidden
      >
        {selected ? (
          <span
            className={cn(
              "h-2.5 w-2.5 rounded-full",
              recommendedHover ? "bg-amber-600 dark:bg-amber-400" : "bg-[var(--kq-color-primary)]"
            )}
          />
        ) : null}
      </span>
      <div className="min-w-0 flex-1">
        {title}
        <p className="hd-wizard-muted mt-2">{description}</p>
      </div>
    </button>
  );
}
