// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { Key } from "lucide-react";
import { LlmConfigEditor } from "../../components/LlmConfigEditor";
import { Section } from "../../components/ui/Section";
import { useI18n } from "../../lib/i18n";

export function SettingsLlmConfig() {
  const { t } = useI18n();

  return (
    <Section icon={Key} title={t("settings.llmConfigTitle")} desc={t("settings.llmConfigDesc")}>
      <LlmConfigEditor mode="settings" onSaved={() => undefined} />
    </Section>
  );
}
