// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useNavigate } from "react-router-dom";
import { useI18n } from "../../lib/i18n";
import { updateDraft } from "../../lib/store";
import { WizardFooter, WizardPrimaryButton } from "../wizard-ui";

export function Welcome() {
  const { t } = useI18n();
  const nav = useNavigate();

  function startQuickSetup() {
    updateDraft({ setupMode: "quick", useRecommendedDefaults: true });
    nav("/onboarding/brain");
  }

  return (
    <div className="space-y-10">
      <div className="space-y-4">
        <h1 className="hd-wizard-title">{t("welcome.title")}</h1>
        <p className="hd-wizard-lead">{t("welcome.lead")}</p>
      </div>

      <ul className="hd-glass-subtle space-y-3.5 p-5">
        <li className="flex gap-3">
          <Bullet />
          <span className="hd-wizard-body">{t("welcome.li1")}</span>
        </li>
        <li className="flex gap-3">
          <Bullet />
          <span className="hd-wizard-body">{t("welcome.li2")}</span>
        </li>
        <li className="flex gap-3">
          <Bullet />
          <span className="hd-wizard-body">{t("welcome.li3")}</span>
        </li>
      </ul>

      <WizardFooter>
        <div className="flex justify-end">
          <WizardPrimaryButton onClick={startQuickSetup}>
            {t("welcome.cta")}
          </WizardPrimaryButton>
        </div>
      </WizardFooter>
    </div>
  );
}

function Bullet() {
  return (
    <span
      aria-hidden
      className="mt-1.5 inline-block h-2 w-2 shrink-0 rounded-full bg-[var(--kq-color-primary)] dark:bg-[#D4C5E2]"
    />
  );
}
