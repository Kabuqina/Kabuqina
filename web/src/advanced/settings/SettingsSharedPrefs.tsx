// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useEffect, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { FileText } from "lucide-react";
import { Section } from "../../components/ui/Section";
import { Button } from "../../components/ui/Button";
import { useI18n } from "../../lib/i18n";

export function SettingsSharedPrefs() {
  const { t } = useI18n();
  const [content, setContent] = useState("");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    invoke<string>("cmd_read_shared_prefs")
      .then(setContent)
      .catch(console.error);
  }, []);

  async function save() {
    setSaving(true);
    setSaved(false);
    try {
      await invoke("cmd_save_shared_prefs", { content });
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (e) {
      console.error(e);
    } finally {
      setSaving(false);
    }
  }

  return (
    <Section
      icon={FileText}
      title={t("settings.sharedPrefsTitle")}
      desc={t("settings.sharedPrefsLead")}
    >
      <textarea
        value={content}
        onChange={(e) => setContent(e.target.value)}
        rows={8}
        className="w-full resize-y rounded-md border border-zinc-300 bg-white p-3 font-mono text-sm dark:border-[var(--kq-color-border)] dark:bg-[var(--kq-glass-bg-subtle)] dark:text-[var(--kq-color-ink)]"
        placeholder={t("settings.sharedPrefsPlaceholder")}
      />
      <div className="mt-3 flex items-center justify-end gap-3">
        {saving && (
          <span className="text-sm text-zinc-500">{t("settings.saving")}</span>
        )}
        <Button onClick={save} disabled={saving || saved}>
          {saved ? t("settings.sharedPrefsSaved") : t("settings.sharedPrefsSave")}
        </Button>
      </div>
    </Section>
  );
}
