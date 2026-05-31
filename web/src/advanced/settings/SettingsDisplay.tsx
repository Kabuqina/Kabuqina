import { useI18n } from "../../lib/i18n";
import {
  FolderOpen,
  Languages,
  Moon,
  Shield,
  Type,
} from "lucide-react";
import { invoke } from "@tauri-apps/api/core";
import { Section } from "../../components/ui/Section";
import { Button } from "../../components/ui/Button";
import { Toggle } from "../../components/ui/Toggle";
import { cn } from "../../lib/cn";
import { LanguageToggle } from "../../components/LanguageToggle";
import type { ThemeMode } from "../../lib/ui-prefs";
import type { Status } from "../Settings";

interface Props {
  status: Status | null;
  powerUser: boolean;
  onTogglePowerUser: (next: boolean) => void;
  fontSize: "small" | "medium" | "large";
  onSetFontSize: (size: "small" | "medium" | "large") => void;
  themeMode: ThemeMode;
  onSetThemeMode: (mode: ThemeMode) => void;
}

export function SettingsDisplay({
  status,
  powerUser,
  onTogglePowerUser,
  fontSize,
  onSetFontSize,
  themeMode,
  onSetThemeMode,
}: Props) {
  const { t } = useI18n();

  return (
    <>
      <Section icon={Type} title={t("settings.fontTitle")} desc={t("settings.fontDesc")}>
        <div className="inline-flex w-full max-w-md rounded-[var(--radius-shell-lg)] border border-[var(--kq-color-border)] bg-[var(--kq-color-primary-pale)]/45 p-0.5 dark:border-zinc-700 dark:bg-zinc-800/50 sm:w-auto">
          {(
            [
              { id: "small" as const, label: t("settings.fontSmall") },
              { id: "medium" as const, label: t("settings.fontMedium") },
              { id: "large" as const, label: t("settings.fontLarge") },
            ] as const
          ).map(({ id, label }) => (
            <button
              key={id}
              type="button"
              onClick={() => {
                onSetFontSize(id);
              }}
              className={cn(
                "min-h-[2.25rem] flex-1 rounded-md px-3 py-1.5 text-sm font-medium transition sm:flex-initial",
                "active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-50",
                fontSize === id
                  ? "hd-btn-segment-active shadow-sm"
                  : "hd-btn-segment-idle"
              )}
            >
              {label}
            </button>
          ))}
        </div>
      </Section>

      <Section icon={Moon} title={t("settings.themeTitle")} desc={t("settings.themeDesc")}>
        <div className="inline-flex w-full max-w-md rounded-[var(--radius-shell-lg)] border border-[var(--kq-color-border)] bg-[var(--kq-color-primary-pale)]/45 p-0.5 dark:border-zinc-700 dark:bg-zinc-800/50 sm:w-auto">
          {(
            [
              { id: "system" as const, label: t("settings.themeSystem") },
              { id: "light" as const, label: t("settings.themeLight") },
              { id: "dark" as const, label: t("settings.themeDark") },
            ] as const
          ).map(({ id, label }) => (
            <button
              key={id}
              type="button"
              onClick={() => {
                onSetThemeMode(id);
              }}
              className={cn(
                "min-h-[2.25rem] flex-1 rounded-md px-3 py-1.5 text-sm font-medium transition sm:flex-initial",
                "active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-50",
                themeMode === id
                  ? "hd-btn-segment-active shadow-sm"
                  : "hd-btn-segment-idle"
              )}
            >
              {label}
            </button>
          ))}
        </div>
      </Section>

      <Section icon={Languages} title={t("settings.langTitle")} desc={t("settings.langDesc")} action={<LanguageToggle />} />

      <Section
        icon={FolderOpen}
        title={t("settings.secWorkspace")}
        desc={powerUser ? t("settings.secWorkspaceDescPower") : t("settings.secWorkspaceDescSimple")}
        action={powerUser ? <Button onClick={() => invoke("cmd_open_workspace")}>{t("settings.openFolder")}</Button> : undefined}
      >
        {powerUser ? (
          <p className="w-full break-all font-mono text-xs leading-relaxed text-zinc-800 dark:text-zinc-200">
            <span className="inline-block max-w-full rounded-md bg-zinc-100 px-2 py-1.5 dark:bg-zinc-800/90">
              {status?.workspace ?? "…"}
            </span>
          </p>
        ) : null}
      </Section>

      <Section icon={Shield} title={t("settings.powerTitle")} desc={t("settings.powerDesc")} action={<Toggle value={powerUser} onChange={(v) => onTogglePowerUser(v)} />} />
    </>
  );
}
