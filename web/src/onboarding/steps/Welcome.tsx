// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { invoke } from "@tauri-apps/api/core";
import { useI18n } from "../../lib/i18n";
import { ART_ASSETS } from "../../lib/artAssets";
import { updateDraft } from "../../lib/store";
import { setPowerUser } from "../../lib/powerUser";
import { Toggle } from "../../components/ui/Toggle";
import { WizardFooter, WizardPrimaryButton } from "../wizard-ui";

export function Welcome() {
  const { t } = useI18n();
  const nav = useNavigate();
  // Default ON: science/engineering students get terminal/code/community skills
  // without hunting through Settings. Persisted explicitly so users who skip
  // onboarding stay on the safe (off) default.
  const [advanced, setAdvanced] = useState(true);

  function startQuickSetup() {
    updateDraft({ setupMode: "quick", useRecommendedDefaults: true });
    // Persist the choice and let the embedded Python respawn pick it up in the
    // background (fire-and-forget so onboarding stays snappy; the Settings
    // toggle is the fallback if this fails).
    setPowerUser(advanced);
    void invoke("cmd_set_power_user", { enabled: advanced }).catch(() => {});
    nav("/onboarding/brain");
  }

  return (
    <div className="space-y-10">
      <div className="space-y-4">
        <img
          src={ART_ASSETS.mascot}
          alt=""
          className="h-24 w-24 drop-shadow-[0_8px_24px_rgba(90,74,106,0.18)]"
          draggable={false}
        />
        <h1 className="hd-wizard-title">{t("welcome.title")}</h1>
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

      <label className="hd-glass-subtle flex items-center gap-4 p-4">
        <Toggle
          value={advanced}
          onChange={setAdvanced}
          aria-label={t("welcome.advancedLabel")}
        />
        <span className="min-w-0">
          <span className="block hd-wizard-body font-medium">{t("welcome.advancedLabel")}</span>
          <span className="block text-sm text-[var(--kq-color-muted)]">{t("welcome.advancedDesc")}</span>
        </span>
      </label>

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
      className="mt-1.5 inline-block h-2 w-2 shrink-0 rounded-full bg-[var(--kq-color-primary)]"
    />
  );
}
