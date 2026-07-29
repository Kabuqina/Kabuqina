// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useState } from "react";
import { ScrollText } from "lucide-react";
import { Section } from "../../components/ui/Section";
import { Toggle } from "../../components/ui/Toggle";
import { useI18n } from "../../lib/i18n";
import { getStudyIaEnabled, setStudyIaEnabled } from "../../study/iaEvents";

/** 本机学习交互计数属于 Study，而不是外观或工作区设置。 */
export function SettingsStudyImprovementCounts() {
  const { t } = useI18n();
  const [enabled, setEnabled] = useState(getStudyIaEnabled);
  const [saveError, setSaveError] = useState(false);

  return (
    <Section
      icon={ScrollText}
      title={t("settings.studyIaTitle")}
      desc={t("settings.studyIaDesc")}
      action={(
        <Toggle
          value={enabled}
          onChange={(next) => {
            const persisted = setStudyIaEnabled(next);
            setEnabled(next ? persisted : false);
            setSaveError(!persisted);
          }}
          aria-label={t("settings.studyIaTitle")}
        />
      )}
    >
      <p className="text-sm leading-relaxed text-[var(--kq-color-muted)]">
        {enabled ? t("settings.studyIaOn") : t("settings.studyIaOff")}
      </p>
      {saveError ? (
        <p role="alert" className="text-sm leading-relaxed text-red-600 dark:text-red-400">
          {t("settings.studyIaSaveError")}
        </p>
      ) : null}
    </Section>
  );
}
