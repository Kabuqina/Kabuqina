// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useCallback, useEffect, useState } from "react";
import { BookOpenCheck, Gauge } from "lucide-react";
import { Section } from "../../components/ui/Section";
import { useI18n } from "../../lib/i18n";
import { cn } from "../../lib/cn";
import {
  cmdStudyPreferencesGet,
  cmdStudyPreferencesPut,
  type StudyImportReadMode,
  type StudyPreferences,
} from "../../chat/study/study-api";

const MODES: StudyImportReadMode[] = ["auto", "precise", "math"];

function useStudyPreferences() {
  const [prefs, setPrefs] = useState<StudyPreferences | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    cmdStudyPreferencesGet()
      .then((value) => {
        setPrefs(value);
        setState("ready");
      })
      .catch(() => setState("error"));
  }, []);

  const save = useCallback(
    (patch: Parameters<typeof cmdStudyPreferencesPut>[0]) => {
      setSaving(true);
      cmdStudyPreferencesPut(patch)
        .then(setPrefs)
        .catch(() => setState("error"))
        .finally(() => setSaving(false));
    },
    [],
  );

  return { prefs, state, saving, save };
}

/**
 * 导入精读档位（账本 B-2）。
 *
 * auto 是秒级的 pypdf，precise/math 是 CPU 推理，差一个数量级——学生导一本 300 页教材
 * 撞上 precise 会以为程序卡死。这里设的既是**导入默认值**，也是该路径的**计算上限**；
 * 普通对话里明确要求精读不受它影响（后端只把作用域限制在可信的 Study 材料读取命令）。
 */
export function SettingsImportReadMode() {
  const { t } = useI18n();
  const { prefs, state, saving, save } = useStudyPreferences();

  return (
    <Section icon={BookOpenCheck} title={t("settings.readModeTitle")} desc={t("settings.readModeDesc")}>
      {state === "error" ? (
        <p className="text-sm text-[var(--kq-color-muted)]" role="status">
          {t("settings.prefsUnavailable")}
        </p>
      ) : null}
      {state === "ready" && prefs ? (
        <div className="space-y-2">
          <div
            role="radiogroup"
            aria-label={t("settings.readModeTitle")}
            className="inline-flex flex-wrap rounded-2xl border border-[var(--kq-color-border)] bg-[var(--kq-color-primary-pale)]/45 p-1 dark:border-[var(--kq-color-border)] dark:bg-[var(--kq-glass-bg-subtle)]"
          >
            {MODES.map((mode) => (
              <button
                key={mode}
                type="button"
                role="radio"
                aria-checked={prefs.importReadMode === mode}
                disabled={saving}
                onClick={() => save({ importReadMode: mode })}
                className={cn(
                  "min-h-[2rem] rounded-xl px-3 py-1 text-sm font-medium transition",
                  prefs.importReadMode === mode ? "hd-btn-segment-active shadow-sm" : "hd-btn-segment-idle",
                )}
              >
                {t(`settings.readMode.${mode}`)}
              </button>
            ))}
          </div>
          <p className="text-sm leading-relaxed text-[var(--kq-color-muted)]">
            {t(`settings.readModeHint.${prefs.importReadMode}`)}
          </p>
        </div>
      ) : null}
    </Section>
  );
}

/**
 * 复习每日上限（账本 B-3）。
 *
 * **这是保护，不是成就。**所以这里只有两个数字和一句说明——不显示连续天数、
 * 完成率或任何达标徽章。一旦变成打卡指标，就把"走遍"伪装成"学会"。
 */
export function SettingsReviewLimits() {
  const { t } = useI18n();
  const { prefs, state, saving, save } = useStudyPreferences();

  return (
    <Section icon={Gauge} title={t("settings.reviewLimitTitle")} desc={t("settings.reviewLimitDesc")}>
      {state === "error" ? (
        <p className="text-sm text-[var(--kq-color-muted)]" role="status">
          {t("settings.prefsUnavailable")}
        </p>
      ) : null}
      {state === "ready" && prefs ? (
        <div className="space-y-3">
          <LimitField
            label={t("settings.reviewLimitNew")}
            value={prefs.dailyNewCardLimit}
            max={100}
            disabled={saving}
            onCommit={(next) => save({ dailyNewCardLimit: next })}
          />
          <LimitField
            label={t("settings.reviewLimitReview")}
            value={prefs.dailyReviewCardLimit}
            max={1000}
            disabled={saving}
            onCommit={(next) => save({ dailyReviewCardLimit: next })}
          />
          <p className="text-sm leading-relaxed text-[var(--kq-color-muted)]">
            {t("settings.reviewLimitZero")}
          </p>
        </div>
      ) : null}
    </Section>
  );
}

function LimitField({
  label,
  value,
  max,
  disabled,
  onCommit,
}: {
  label: string;
  value: number;
  max: number;
  disabled: boolean;
  onCommit: (next: number) => void;
}) {
  const [draft, setDraft] = useState(String(value));
  useEffect(() => setDraft(String(value)), [value]);

  const commit = () => {
    const parsed = Number.parseInt(draft, 10);
    if (Number.isNaN(parsed)) {
      setDraft(String(value));
      return;
    }
    const clamped = Math.min(Math.max(parsed, 0), max);
    setDraft(String(clamped));
    if (clamped !== value) onCommit(clamped);
  };

  return (
    <label className="flex flex-wrap items-center gap-3 text-sm text-[var(--kq-color-ink)]">
      <span className="min-w-[7rem]">{label}</span>
      <input
        type="number"
        min={0}
        max={max}
        inputMode="numeric"
        value={draft}
        disabled={disabled}
        onChange={(event) => setDraft(event.currentTarget.value)}
        onBlur={commit}
        onKeyDown={(event) => {
          if (event.key === "Enter") event.currentTarget.blur();
        }}
        className="w-24 rounded-[var(--radius-shell-lg)] border border-[var(--kq-color-border)] bg-[var(--kq-input-surface)] px-3 py-1.5 text-sm tabular-nums text-[var(--kq-color-ink)] outline-none focus:border-[var(--kq-color-primary)]"
      />
    </label>
  );
}
