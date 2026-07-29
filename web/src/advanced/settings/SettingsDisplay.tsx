// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useRef, useState } from "react";
import { useI18n } from "../../lib/i18n";
import {
  FolderOpen,
  ImageIcon,
  Languages,
  Moon,
  RotateCcw,
  Type,
  Upload,
} from "lucide-react";
import { invoke } from "@tauri-apps/api/core";
import { open } from "@tauri-apps/plugin-dialog";
import { Section } from "../../components/ui/Section";
import { Button } from "../../components/ui/Button";
import { Toggle } from "../../components/ui/Toggle";
import { ART_ASSETS } from "../../lib/artAssets";
import { cn } from "../../lib/cn";
import { LanguageToggle } from "../../components/LanguageToggle";
import {
  clearCustomCompanionImage,
  getCustomCompanionImage,
  setCustomCompanionImage,
  validateCustomCompanionImageFile,
  type ThemeMode,
} from "../../lib/ui-prefs";
import type { Status } from "../Settings";

interface Props {
  status: Status | null;
  fontSize: "small" | "medium" | "large";
  onSetFontSize: (size: "small" | "medium" | "large") => void;
  themeMode: ThemeMode;
  onSetThemeMode: (mode: ThemeMode) => void;
  onWorkspaceChanged: () => void | Promise<void>;
}

type WorkspaceUpdateResult = {
  workspace: string;
  migrated: boolean;
  copiedFiles: number;
  copiedDirs: number;
  conflicts: number;
  skippedEntries: number;
};

function ipcErr(e: unknown): string {
  return e instanceof Error ? e.message : String(e);
}

export function SettingsDisplay({
  status,
  fontSize,
  onSetFontSize,
  themeMode,
  onSetThemeMode,
  onWorkspaceChanged,
}: Props) {
  const { t } = useI18n();
  const companionImageInputRef = useRef<HTMLInputElement>(null);
  const [customCompanionImage, setCustomCompanionImageState] = useState<string | null>(
    getCustomCompanionImage
  );
  const [companionImageError, setCompanionImageError] = useState<string | null>(null);
  const [workspaceMigrateFiles, setWorkspaceMigrateFiles] = useState(true);
  const [workspaceBusy, setWorkspaceBusy] = useState(false);
  const [workspaceNotice, setWorkspaceNotice] = useState<string | null>(null);
  const [workspaceError, setWorkspaceError] = useState<string | null>(null);

  const handleCompanionImagePicked = (file: File | undefined) => {
    if (!file) return;
    const validation = validateCustomCompanionImageFile(file);
    if (!validation.ok) {
      setCompanionImageError(
        validation.reason === "size"
          ? t("settings.companionImageErrSize")
          : t("settings.companionImageErrType")
      );
      return;
    }
    const reader = new FileReader();
    reader.onload = () => {
      const dataUrl = typeof reader.result === "string" ? reader.result : "";
      if (!dataUrl.startsWith("data:image/")) {
        setCompanionImageError(t("settings.companionImageErrType"));
        return;
      }
      setCustomCompanionImage(dataUrl);
      setCustomCompanionImageState(dataUrl);
      setCompanionImageError(null);
    };
    reader.onerror = () => {
      setCompanionImageError(t("settings.companionImageErrRead"));
    };
    reader.readAsDataURL(file);
  };

  const resetCompanionImage = () => {
    clearCustomCompanionImage();
    setCustomCompanionImageState(null);
    setCompanionImageError(null);
    if (companionImageInputRef.current) {
      companionImageInputRef.current.value = "";
    }
  };

  const applyWorkspace = async (path: string) => {
    setWorkspaceBusy(true);
    setWorkspaceNotice(null);
    setWorkspaceError(null);
    try {
      const result = await invoke<WorkspaceUpdateResult>("cmd_set_workspace", {
        path,
        migrateFiles: workspaceMigrateFiles,
      });
      setWorkspaceNotice(
        result.migrated
          ? t("settings.workspaceChangedMigrated", {
              files: result.copiedFiles,
              conflicts: result.conflicts,
            })
          : t("settings.workspaceChanged")
      );
      await onWorkspaceChanged();
    } catch (e) {
      setWorkspaceError(t("settings.workspaceChangeFailed", { msg: ipcErr(e) }));
    } finally {
      setWorkspaceBusy(false);
    }
  };

  const chooseWorkspace = async () => {
    const selected = await open({
      directory: true,
      multiple: false,
      title: t("settings.workspaceChooseTitle"),
    });
    if (!selected || Array.isArray(selected)) return;
    await applyWorkspace(selected);
  };

  const resetWorkspace = async () => {
    await applyWorkspace("");
  };

  return (
    <>
      <Section icon={Type} title={t("settings.fontTitle")} desc={t("settings.fontDesc")}>
        <div className="inline-flex w-full max-w-md rounded-2xl border border-[var(--kq-color-border)] bg-[var(--kq-color-primary-pale)]/45 p-1 dark:border-[var(--kq-color-border)] dark:bg-[var(--kq-glass-bg-subtle)] sm:w-auto">
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
                "min-h-[2.25rem] flex-1 rounded-xl px-3 py-1.5 text-sm font-medium transition sm:flex-initial",
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
        <div className="inline-flex w-full max-w-md rounded-2xl border border-[var(--kq-color-border)] bg-[var(--kq-color-primary-pale)]/45 p-1 dark:border-[var(--kq-color-border)] dark:bg-[var(--kq-glass-bg-subtle)] sm:w-auto">
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
                "min-h-[2.25rem] flex-1 rounded-xl px-3 py-1.5 text-sm font-medium transition sm:flex-initial",
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
        icon={ImageIcon}
        title={t("settings.companionImageTitle")}
        desc={t("settings.companionImageDesc")}
      >
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
          <div className="grid h-28 w-28 shrink-0 place-items-center rounded-[var(--radius-shell-lg)] border border-[var(--kq-color-border)] bg-[var(--kq-color-primary-pale)]/35 p-2 dark:border-[var(--kq-color-border)] dark:bg-[var(--kq-glass-bg-subtle)]">
            <img
              src={customCompanionImage ?? ART_ASSETS.companionPill}
              alt=""
              className="max-h-full max-w-full object-contain"
              draggable={false}
            />
          </div>
          <div className="min-w-0 flex-1 space-y-3">
            <p className="text-sm leading-relaxed text-[var(--kq-color-ink)] dark:text-[var(--kq-color-ink)]">
              {t("settings.companionImageSpec")}
            </p>
            {companionImageError ? (
              <p className="text-sm leading-relaxed text-red-600 dark:text-red-400">
                {companionImageError}
              </p>
            ) : null}
            <div className="flex flex-wrap items-center gap-2">
              <input
                ref={companionImageInputRef}
                type="file"
                accept="image/png,image/webp,image/svg+xml"
                className="hidden"
                onChange={(event) => handleCompanionImagePicked(event.currentTarget.files?.[0])}
              />
              <Button onClick={() => companionImageInputRef.current?.click()}>
                <Upload className="mr-2 h-4 w-4" aria-hidden />
                {t("settings.companionImageUpload")}
              </Button>
              <Button variant="secondary" onClick={resetCompanionImage} disabled={!customCompanionImage}>
                {t("settings.companionImageReset")}
              </Button>
            </div>
          </div>
        </div>
      </Section>

      {/* v0.5.0 起不再分权限层（owner 2026-07-27）：路径、打开文件夹、改位置全部常驻。 */}
      <Section
        icon={FolderOpen}
        title={t("settings.secWorkspace")}
        desc={t("settings.secWorkspaceDescPower")}
        action={<Button onClick={() => invoke("cmd_open_workspace")}>{t("settings.openFolder")}</Button>}
      >
        <p className="w-full break-all font-mono text-xs leading-relaxed text-[var(--kq-color-strong)]">
          <span className="inline-block max-w-full rounded-md bg-zinc-100 px-2 py-1.5 dark:bg-[var(--kq-glass-bg-subtle)]">
            {status?.workspace ?? "…"}
          </span>
        </p>
        <div className="mt-3 space-y-3">
            <label className="flex flex-wrap items-center gap-3 text-sm text-[var(--kq-color-ink)] dark:text-[var(--kq-color-ink)]">
              <Toggle
                value={workspaceMigrateFiles}
                onChange={setWorkspaceMigrateFiles}
                disabled={workspaceBusy}
                aria-label={t("settings.workspaceMigrateFiles")}
              />
              <span>{t("settings.workspaceMigrateFiles")}</span>
            </label>
            <div className="flex flex-wrap gap-2">
              <Button onClick={() => void chooseWorkspace()} disabled={workspaceBusy}>
                <FolderOpen className="h-4 w-4" aria-hidden />
                {workspaceBusy ? t("settings.workspaceChanging") : t("settings.workspaceChoose")}
              </Button>
              <Button variant="secondary" onClick={() => void resetWorkspace()} disabled={workspaceBusy}>
                <RotateCcw className="h-4 w-4" aria-hidden />
                {t("settings.workspaceResetDefault")}
              </Button>
            </div>
            {workspaceNotice ? (
              <p className="text-sm leading-relaxed text-emerald-700 dark:text-emerald-300">
                {workspaceNotice}
              </p>
            ) : null}
            {workspaceError ? (
              <p className="text-sm leading-relaxed text-red-600 dark:text-red-400">
                {workspaceError}
              </p>
            ) : null}
        </div>
      </Section>
    </>
  );
}
