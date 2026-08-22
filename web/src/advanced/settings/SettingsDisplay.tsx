// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useRef, useState } from "react";
import { useI18n } from "../../lib/i18n";
import {
  ImageIcon,
  Languages,
  Moon,
  Type,
  Upload,
} from "lucide-react";
import { Section } from "../../components/ui/Section";
import { Button } from "../../components/ui/Button";
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

interface Props {
  fontSize: "small" | "medium" | "large";
  onSetFontSize: (size: "small" | "medium" | "large") => void;
  themeMode: ThemeMode;
  onSetThemeMode: (mode: ThemeMode) => void;
}

export function SettingsDisplay({
  fontSize,
  onSetFontSize,
  themeMode,
  onSetThemeMode,
}: Props) {
  const { t } = useI18n();
  const companionImageInputRef = useRef<HTMLInputElement>(null);
  const [customCompanionImage, setCustomCompanionImageState] = useState<string | null>(
    getCustomCompanionImage
  );
  const [companionImageError, setCompanionImageError] = useState<string | null>(null);

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

  return (
    <>
      <Section icon={Type} title={t("settings.fontTitle")} desc={t("settings.fontDesc")}>
        <div className="kq-segment inline-flex w-full max-w-md p-1 sm:w-auto">
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
        <div className="kq-segment inline-flex w-full max-w-md p-1 sm:w-auto">
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
          <div className="kq-thumb-well grid h-28 w-28 shrink-0 place-items-center p-2">
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
              <p className="text-sm leading-relaxed text-[var(--danger)]">
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
    </>
  );
}
