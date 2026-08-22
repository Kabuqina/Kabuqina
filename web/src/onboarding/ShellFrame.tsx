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
    <AppScaffold className="flex h-full min-h-0 w-full flex-col">
      <div className="kq-chat-desk">
        <section className="kq-chat-paper kq-utility-paper kq-onboarding-paper">
          <header className="kq-utility-paper-head kq-onboarding-progress">
            <p className="hd-wizard-progress truncate" aria-live="polite">
              {progressText}
            </p>
            <ProgressDots index={idx} total={stepList.length} />
          </header>
          <main className="kq-utility-paper-body">
            <div className="mx-auto max-w-[var(--hd-content-max)] space-y-[var(--hd-stack-gap)]">
              {children}
            </div>
          </main>
        </section>
      </div>
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
