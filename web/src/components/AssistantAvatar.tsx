// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useI18n } from "../lib/i18n";
import { cn } from "../lib/cn";

/** Chat assistant avatar — Kabuqina mascot SVG (chat only). */
export const ASSISTANT_AVATAR_SRC = "/kabuqina_mascot.svg";

type Props = {
  className?: string;
  /** When false, the wrapper is aria-hidden (decorative). */
  labeled?: boolean;
};

export function AssistantAvatar({ className, labeled = true }: Props) {
  const { t } = useI18n();
  return (
    <div
      className={cn("kq-assistant-avatar", className)}
      aria-hidden={labeled ? undefined : true}
      aria-label={labeled ? t("brand") : undefined}
    >
      <img
        src={ASSISTANT_AVATAR_SRC}
        alt=""
        className="kq-assistant-avatar-image"
        width={46}
        height={46}
        decoding="async"
        draggable={false}
      />
    </div>
  );
}
