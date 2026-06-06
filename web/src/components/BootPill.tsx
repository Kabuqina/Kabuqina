// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useI18n } from "../lib/i18n";

/** Unified in-window boot indicator (Splash + Chat warm-up). */
export function BootPill() {
  const { t } = useI18n();

  return (
    <div className="kq-boot-pill flex flex-col items-center justify-center" role="status" aria-live="polite">
      <img
        src="/kabuqina_boot.svg"
        alt=""
        className="w-72 h-auto select-none"
        draggable={false}
      />
      <p className="kq-boot-pill-label mt-6 text-sm font-medium tracking-wide text-[var(--kq-color-muted)]">
        {t("boot.starting")}
      </p>
    </div>
  );
}
