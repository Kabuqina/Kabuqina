// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { WeixinQrRouteCBlock } from "../../components/WeixinQrRouteCBlock";
import { QqbotQrRouteBlock } from "../../components/QqbotQrRouteBlock";
import { getDraftSnapshot, updateDraft } from "../../lib/store";
import { useI18n } from "../../lib/i18n";
import type { LocaleKey, OptionConfigField, SetupCatalogOption } from "../setupCatalog/optionTypes";
import { pick, getSlice } from "../utils";

interface Props {
  editing: SetupCatalogOption | null;
  section: string;
  loc: LocaleKey;
  form: Record<string, string>;
  setForm: React.Dispatch<React.SetStateAction<Record<string, string>>>;
  onClose: () => void;
  onPersist: (option: SetupCatalogOption, next: Record<string, string>) => void;
}

export function ConfigModalBody({ editing, section, loc, form, setForm, onClose, onPersist }: Props) {
  const { t } = useI18n();

  if (!editing) return null;

  if (editing.configUi === "weixin_route_c") {
    return (
      <div className="space-y-4">
        <p className="text-xs leading-relaxed text-[var(--kq-color-muted)]">{t("settings.weixinLead")}</p>
        <WeixinQrRouteCBlock
          key={editing.id}
          onSuccess={({ accountId }) => {
            const d = getDraftSnapshot();
            const w = d.wizardConfig ?? {};
            const prevSec = w[section] ?? {};
            const slice = getSlice(w, section, editing.id);
            updateDraft({
              wizardConfig: {
                ...w,
                [section]: {
                  ...prevSec,
                  [editing.id]: { ...slice, WEIXIN_ACCOUNT_ID: accountId },
                },
              },
            });
          }}
        />
        <div className="flex flex-wrap justify-end gap-2 border-t border-[var(--kq-color-border)] pt-4">
          <button
            type="button"
            className="kq-btn-secondary rounded-[var(--radius-shell-lg)] px-4 py-2 text-sm"
            onClick={onClose}
          >
            {t("setupOptions.cancelConfig")}
          </button>
        </div>
      </div>
    );
  }

  if (editing.configUi === "qqbot_route_c") {
    return (
      <div className="space-y-4">
        <p className="text-xs leading-relaxed text-[var(--kq-color-muted)]">{t("settings.qqLead")}</p>
        <QqbotQrRouteBlock
          key={editing.id}
          onSuccess={({ appId }) => {
            const d = getDraftSnapshot();
            const w = d.wizardConfig ?? {};
            const prevSec = w[section] ?? {};
            const slice = getSlice(w, section, editing.id);
            updateDraft({
              wizardConfig: {
                ...w,
                [section]: {
                  ...prevSec,
                  [editing.id]: { ...slice, QQ_APP_ID: appId },
                },
              },
            });
          }}
        />
        <div className="flex flex-wrap justify-end gap-2 border-t border-[var(--kq-color-border)] pt-4">
          <button
            type="button"
            className="kq-btn-secondary rounded-[var(--radius-shell-lg)] px-4 py-2 text-sm"
            onClick={onClose}
          >
            {t("setupOptions.cancelConfig")}
          </button>
        </div>
      </div>
    );
  }

  if (editing.configFields?.length) {
    return (
      <form
        className="space-y-4"
        onSubmit={(e) => {
          e.preventDefault();
          onPersist(editing, form);
          onClose();
        }}
      >
        <p className="text-xs text-[var(--kq-color-muted)]">{t("setupOptions.configLead")}</p>
        {editing.configFields.map((fld: OptionConfigField) => (
          <div key={fld.id} className="space-y-1.5">
            <label className="flex flex-wrap items-baseline gap-2 text-sm font-medium text-[var(--kq-color-strong)]">
              <span>{pick(fld.label, loc)}</span>
              {fld.optional ? (
                <span className="text-xs font-normal text-[var(--kq-color-muted)]">({t("setupOptions.optional")})</span>
              ) : null}
            </label>
            <p className="text-[0.7rem] font-mono text-[var(--kq-color-muted)]">{fld.id}</p>
            <input
              className="w-full rounded-[var(--radius-shell)] border border-[var(--kq-color-border)] bg-[var(--kq-input-surface)] px-3 py-2.5 font-mono text-sm"
              type={fld.kind === "password" ? "password" : fld.kind === "url" ? "url" : "text"}
              name={fld.id}
              value={form[fld.id] ?? ""}
              placeholder={pick(fld.placeholder, loc)}
              autoComplete="off"
              spellCheck={false}
              onChange={(e) => setForm((prev) => ({ ...prev, [fld.id]: e.target.value }))}
            />
          </div>
        ))}
        <div className="flex flex-wrap justify-end gap-2 border-t border-[var(--kq-color-border)] pt-4">
          <button
            type="button"
            className="kq-btn-secondary rounded-[var(--radius-shell-lg)] px-4 py-2 text-sm"
            onClick={onClose}
          >
            {t("setupOptions.cancelConfig")}
          </button>
          <button
            type="submit"
            className="kq-btn-primary rounded-lg px-4 py-2 text-sm text-white"
          >
            {t("setupOptions.saveConfig")}
          </button>
        </div>
      </form>
    );
  }

  return null;
}
