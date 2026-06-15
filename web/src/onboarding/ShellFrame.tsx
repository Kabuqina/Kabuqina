// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { ReactNode, useMemo } from "react";
import { useLocation } from "react-router-dom";
import { AppScaffold } from "../components/AppScaffold";
import { useI18n } from "../lib/i18n";
import { useDraft } from "../lib/store";
import { getIndexInFlow, getStepsForMode, slugFromPathname, type ShellWizardStepId } from "./flowConfig";

export function ShellFrame({ children }: { children: ReactNode }) {
  const loc = useLocation();
  const { t } = useI18n();
  const draft = useDraft();

  const slug = useMemo((): ShellWizardStepId => slugFromPathname(loc.pathname), [loc.pathname]);
  const stepList = getStepsForMode(draft.setupMode);
  const idx = getIndexInFlow(slug, draft.setupMode);
  const stepLabel = t(`onboarding.step.${slug}`);
  const progressText = t("onboarding.progress", {
    current: String(idx + 1),
    total: String(stepList.length),
    step: stepLabel,
  });

  return (
    <AppScaffold className="flex h-full w-full flex-col">
      <header className="kq-chat-topbar shrink-0 border-b px-[var(--hd-page-pad-x)] py-3.5">
        <div className="mx-auto flex max-w-[var(--hd-content-max)] items-center justify-between gap-3">
          <div className="flex shrink-0 items-center gap-2">
            <img src="/kabuqina_mascot.svg" alt="" className="h-7 w-7 shrink-0" draggable={false} />
            <span className="hd-wizard-card-title">{t("productName")}</span>
          </div>
          <div className="flex min-w-0 flex-col items-end gap-1.5 sm:flex-row sm:items-center sm:gap-3">
            <p className="hd-wizard-progress truncate" aria-live="polite">
              {progressText}
            </p>
            <ProgressDots index={idx} total={stepList.length} />
          </div>
        </div>
      </header>
      <main className="min-h-0 flex-1 overflow-y-auto">
        <div className="mx-auto max-w-[var(--hd-content-max)] space-y-[var(--hd-stack-gap)] px-[var(--hd-page-pad-x)] py-10 sm:py-12">
          {children}
        </div>
      </main>
    </AppScaffold>
  );
}

function ProgressDots({ index, total }: { index: number; total: number }) {
  return (
    <div className="flex shrink-0 items-center gap-1.5" aria-hidden>
      {Array.from({ length: total }).map((_, i) => (
        <span
          key={i}
          className={
            "h-1.5 rounded-full transition-all " +
            (i <= index
              ? "w-6 bg-[var(--kq-color-primary)]"
              : "w-1.5 bg-[var(--kq-color-primary)]/30")
          }
        />
      ))}
    </div>
  );
}
