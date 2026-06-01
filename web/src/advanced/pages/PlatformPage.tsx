// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import type { ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { AppScaffold } from "../../components/AppScaffold";
import { BackButton } from "../../components/ui/BackButton";
import { useI18n } from "../../lib/i18n";

export function PlatformPage({
  title,
  desc,
  children,
}: {
  title: string;
  desc?: string;
  children: ReactNode;
}) {
  const nav = useNavigate();
  const { t } = useI18n();

  return (
    <AppScaffold className="h-full overflow-y-auto">
      <div className="mx-auto max-w-2xl space-y-5 px-[var(--hd-page-pad-x)] py-8 sm:py-10">
        <div>
          <BackButton onClick={() => nav("/settings")}>
            {t("settings.backToSettings")}
          </BackButton>
          <h1 className="hd-page-title">{title}</h1>
          {desc && (
            <p className="mt-1.5 max-w-xl text-sm leading-relaxed text-zinc-500 dark:text-zinc-400">
              {desc}
            </p>
          )}
        </div>
        {children}
      </div>
    </AppScaffold>
  );
}
