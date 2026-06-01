// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useNavigate } from "react-router-dom";
import { useI18n } from "../../lib/i18n";
import { updateDraft, useDraft } from "../../lib/store";
import { ArrowRight } from "lucide-react";
import { cn } from "../../lib/cn";

/** Quick vs full setup path 鈥?cards are the buttons. */
export function SetupMode() {
  const { t } = useI18n();
  const nav = useNavigate();
  const draft = useDraft();

  function chooseQuick() {
    updateDraft({ setupMode: "quick", useRecommendedDefaults: true });
    nav("/onboarding/brain");
  }

  function chooseFull() {
    updateDraft({ setupMode: "full", useRecommendedDefaults: false });
    nav("/onboarding/brain");
  }

  return (
    <div className="space-y-8">
      <div className="space-y-3">
        <h1 className="hd-wizard-title">{t("setupMode.title")}</h1>
        <p className="hd-wizard-lead">{t("setupMode.lead")}</p>
      </div>

      {draft.setupMode ? (
        <p className="hd-wizard-hint text-amber-800/90 dark:text-amber-200/90">{t("setupMode.againHint")}</p>
      ) : null}

      <div className="space-y-3">
        <ModeCard
          title={t("setupMode.quickTitle")}
          body={t("setupMode.quickBody")}
          onClick={chooseQuick}
          recommended
          recommendedLabel={t("brain.recommended")}
        />
        <ModeCard
          title={t("setupMode.fullTitle")}
          body={t("setupMode.fullBody")}
          onClick={chooseFull}
        />
      </div>

    </div>
  );
}

function ModeCard({
  title,
  body,
  onClick,
  recommended,
  recommendedLabel,
}: {
  title: string;
  body: string;
  onClick: () => void;
  recommended?: boolean;
  recommendedLabel?: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "hd-glass-subtle w-full p-5 text-left transition",
        recommended
          ? "border-amber-200/80 bg-amber-50/60 hover:border-amber-300/90 hover:bg-amber-50/80 dark:border-amber-800/40 dark:bg-amber-950/20 dark:hover:border-amber-700/60 dark:hover:bg-amber-950/30"
          : "hover:border-[var(--kq-color-primary-light)]/70 hover:bg-[var(--kq-color-primary-pale)]/30 dark:hover:border-[#D4C5E2]/40 dark:hover:bg-[#D4C5E2]/10",
        "active:scale-[0.99]"
      )}
    >
      <div className="flex items-start gap-3">
        <div className="min-w-0 flex-1 space-y-1">
          <div className="flex items-baseline justify-between gap-3">
            <h2 className="hd-wizard-card-title">{title}</h2>
            {recommended && recommendedLabel ? (
              <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800 dark:bg-amber-900/50 dark:text-amber-200">
                {recommendedLabel}
              </span>
            ) : null}
          </div>
          <p className="hd-wizard-muted">{body}</p>
        </div>
        <ArrowRight
          className={cn(
            "mt-0.5 h-5 w-5 shrink-0 transition",
            recommended
              ? "text-amber-400 dark:text-amber-600"
              : "text-zinc-400 group-hover:text-[var(--kq-color-primary)] dark:text-zinc-500"
          )}
          strokeWidth={2}
        />
      </div>
    </button>
  );
}
