// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useState } from "react";
import { ShellModal } from "../components/ShellModal";
import { useI18n } from "../lib/i18n";
import { cn } from "../lib/cn";
import { updateDraft, useDraft, type SectionSelection } from "../lib/store";
import { ConfigModalBody } from "./components/ConfigModalBody";
import { usePlatformEnvStatus } from "./hooks/usePlatformEnvStatus";
import type {
  LocaleKey,
  SetupCatalogOption,
} from "./setupCatalog/optionTypes";
import {
  getInitialSectionSelection,
  SECTION_SELECTION_MODE,
  type PostPassSelectionMode,
} from "./sectionSelection";
import { pick, getSlice, hasConfigFieldsOrRouteC } from "./utils";

type Props = {
  section: string;
  items: SetupCatalogOption[];
  className?: string;
  modalSize?: "md" | "lg";
  /** Omitted = infer from `section` if tts/terminal/… else `none`. */
  selectionMode?: PostPassSelectionMode;
  /** `false` for rosters that are only informational. */
  showSkipRow?: boolean;
  /** When `section` is a post-pass id, use this until `wizardSelection[section]` is persisted. */
  defaultSelection?: SectionSelection;
};

function inferMode(section: string, explicit?: PostPassSelectionMode): PostPassSelectionMode {
  if (explicit) return explicit;
  if (section in SECTION_SELECTION_MODE) {
    return SECTION_SELECTION_MODE[section as keyof typeof SECTION_SELECTION_MODE];
  }
  return "none";
}

/**
 * Roster: optional skip (keep defaults), then single- or multi-select, default/recommended badging, and per-row configure modals.
 */
export function SetupOptionsTable({
  section,
  items,
  className,
  modalSize = "md",
  selectionMode: selectionModeProp,
  showSkipRow = true,
  defaultSelection: defaultSelectionProp,
}: Props) {
  const { t, locale } = useI18n();
  const loc = (locale === "en" ? "en" : "zh") as LocaleKey;
  const draft = useDraft();
  const wizard = draft.wizardConfig ?? {};
  const selectionMode = inferMode(section, selectionModeProp);
  const defaultSelectionForMode =
    section in SECTION_SELECTION_MODE
      ? (getInitialSectionSelection as (s: string) => SectionSelection | undefined)(section)
      : undefined;
  const defaultSelection: SectionSelection | undefined =
    defaultSelectionProp ?? defaultSelectionForMode;

  const [editing, setEditing] = useState<SetupCatalogOption | null>(null);
  const [form, setForm] = useState<Record<string, string>>({});
  const { weixinEnv, qqEnv, feishuEnv, wecomEnv } = usePlatformEnvStatus(items);

  const selRaw = draft.wizardSelection?.[section];
  const sel: SectionSelection | undefined =
    selRaw ?? (selectionMode !== "none" && defaultSelection ? defaultSelection : undefined);
  const isSkip = sel?.kind === "skip";
  const singleId = sel?.kind === "single" ? sel.optionId : null;
  const multiSet = new Set(sel?.kind === "multi" ? sel.optionIds : []);

  function setSelection(next: SectionSelection) {
    const prev = draft.wizardSelection ?? {};
    updateDraft({ wizardSelection: { ...prev, [section]: next } });
  }

  function openConfig(row: SetupCatalogOption) {
    if (!rowAllowsConfig(row)) return;
    setForm(getSlice(wizard, section, row.id));
    setEditing(row);
  }

  function rowAllowsConfig(row: SetupCatalogOption): boolean {
    if (!hasConfigFieldsOrRouteC(row.configFields, row.configUi)) return false;
    if (isSkip) return false;
    if (selectionMode === "single") return singleId === row.id;
    if (selectionMode === "multi") return multiSet.has(row.id);
    return true;
  }

  function hasAnyValue(optionId: string): boolean {
    const slice = getSlice(wizard, section, optionId);
    return Object.values(slice).some((v) => v.trim().length > 0);
  }

  function isEnvConfigured(row: SetupCatalogOption): boolean {
    if (row.configUi === "weixin_route_c") return weixinEnv?.configured ?? false;
    if (row.configUi === "qqbot_route_c") return qqEnv?.configured ?? false;
    if (row.configUi === "feishu_route_c") return feishuEnv?.configured ?? false;
    if (row.configUi === "wecom_route_c") return wecomEnv?.configured ?? false;
    return false;
  }

  function persistForm(option: SetupCatalogOption, next: Record<string, string>) {
    const prevSec = wizard[section] ?? {};
    updateDraft({
      wizardConfig: {
        ...wizard,
        [section]: {
          ...prevSec,
          [option.id]: next,
        },
      },
    });
  }

  const hasChoiceUi = selectionMode === "single" || selectionMode === "multi";
  const showSkip = showSkipRow && hasChoiceUi;
  const skipTitle = section === "gateway" ? t("setupOptions.skipTitle") : t("setupOptions.skipKeepTitle");
  const skipBody = section === "gateway" ? t("setupOptions.skipBody") : t("setupOptions.skipKeepBody");

  return (
    <div className={cn("space-y-3", className)}>
      {showSkip ? (
        <div className="mb-3 space-y-1.5 rounded-[var(--radius-shell-lg)] border border-amber-200/80 bg-amber-50/60 px-4 py-3 dark:border-amber-800/50 dark:bg-amber-950/30">
          <label className="flex cursor-pointer items-start gap-3 hd-wizard-body">
            <input
              type="checkbox"
              className="mt-1 h-4 w-4 rounded border-zinc-400"
              checked={isSkip}
              onChange={(e) => {
                if (e.target.checked) {
                  setSelection({ kind: "skip" });
                } else {
                  if (selectionMode === "single") {
                    const firstD = items.find((x) => x.isDefault)?.id ?? items[0]?.id;
                    if (firstD) setSelection({ kind: "single", optionId: firstD });
                  } else {
                    setSelection({ kind: "multi", optionIds: [] });
                  }
                }
              }}
            />
            <span>
              <span className="font-medium">{skipTitle}</span>
              <span className="hd-wizard-hint mt-1 block font-normal">
                {skipBody}
              </span>
            </span>
          </label>
        </div>
      ) : null}

      <div
        className={cn(
          "hd-glass-subtle overflow-x-auto p-0",
          isSkip && hasChoiceUi && "pointer-events-none opacity-45"
        )}
      >
        <table className="w-full min-w-[min(100%,480px)] border-collapse text-left text-sm">
          <thead>
            <tr className="border-b border-zinc-200/80 dark:border-zinc-700/80">
              {hasChoiceUi && !isSkip ? (
                <th className="w-10 px-2 py-2.5 text-center font-medium text-zinc-800 dark:text-zinc-200">
                  {t("setupOptions.colPick")}
                </th>
              ) : null}
              <th className="px-4 py-2.5 font-medium text-zinc-800 dark:text-zinc-200">{t("setupOptions.colOption")}</th>
              <th className="px-4 py-2.5 font-medium text-zinc-800 dark:text-zinc-200">
                {t("setupOptions.colDefault")}
              </th>
              <th className="w-0 whitespace-nowrap px-4 py-2.5 text-right font-medium text-zinc-800 dark:text-zinc-200">
                {t("setupOptions.colConfigure")}
              </th>
            </tr>
          </thead>
          <tbody>
            {items.map((row) => {
              const hasFields = hasConfigFieldsOrRouteC(row.configFields, row.configUi);
              const envOk = isEnvConfigured(row);
              return (
                <tr
                  key={row.id}
                  className="border-b border-zinc-100/90 last:border-0 dark:border-zinc-800/80"
                >
                  {hasChoiceUi && !isSkip ? (
                    <td className="px-2 py-2.5 text-center align-top">
                      {selectionMode === "single" ? (
                        <input
                          type="radio"
                          name={`wizard-${section}`}
                          className="h-4 w-4"
                          checked={singleId === row.id}
                          onChange={() => setSelection({ kind: "single", optionId: row.id })}
                        />
                      ) : (
                        <input
                          type="checkbox"
                          className="h-4 w-4 rounded"
                          checked={multiSet.has(row.id)}
                          onChange={(e) => {
                            const next = new Set(sel?.kind === "multi" ? sel.optionIds : []);
                            if (e.target.checked) {
                              next.add(row.id);
                            } else {
                              next.delete(row.id);
                            }
                            setSelection({ kind: "multi", optionIds: [...next] });
                          }}
                        />
                      )}
                    </td>
                  ) : null}
                  <td className="px-4 py-2.5 align-top text-zinc-800 dark:text-zinc-200">
                    <div className="flex flex-wrap items-baseline gap-2">
                      <span>{pick(row.name, loc)}</span>
                      {row.isDefault ? (
                        <span className="rounded bg-violet-500/15 px-1.5 py-0.5 text-[0.7rem] font-medium text-violet-800 dark:text-violet-200">
                          {t("setupOptions.recommendedBadge")}
                        </span>
                      ) : null}
                      {hasAnyValue(row.id) ? (
                        <span className="text-[0.7rem] text-[var(--kq-color-strong)] dark:text-[#D4C5E2]">{t("setupOptions.hasPrefill")}</span>
                      ) : null}
                      {envOk ? (
                        <span className="rounded bg-emerald-500/15 px-1.5 py-0.5 text-[0.7rem] font-medium text-emerald-800 dark:text-emerald-200">
                          {t("setupOptions.configured")}
                        </span>
                      ) : null}
                    </div>
                  </td>
                  <td className="px-4 py-2.5 align-top text-zinc-600 dark:text-zinc-400">
                    {pick(row.defaultHint, loc)}
                  </td>
                  <td className="px-4 py-2.5 align-top text-right">
                    {hasFields ? (
                      <button
                        type="button"
                        disabled={!rowAllowsConfig(row)}
                        onClick={() => openConfig(row)}
                        className={cn(
                          "whitespace-nowrap",
                          rowAllowsConfig(row)
                            ? "text-[var(--kq-color-strong)] underline-offset-2 hover:underline dark:text-[#D4C5E2]"
                            : "cursor-not-allowed text-zinc-300 dark:text-zinc-600"
                        )}
                      >
                        {t("setupOptions.configure")}
                      </button>
                    ) : (
                      <span className="text-zinc-300 dark:text-zinc-600">—</span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <ShellModal
        open={editing !== null}
        onClose={() => setEditing(null)}
        title={editing ? pick(editing.name, loc) : ""}
        size={modalSize}
      >
        <ConfigModalBody
          editing={editing}
          section={section}
          loc={loc}
          form={form}
          setForm={setForm}
          onClose={() => setEditing(null)}
          onPersist={persistForm}
        />
      </ShellModal>
    </div>
  );
}
