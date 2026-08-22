// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useI18n } from "../lib/i18n";
import { cn } from "../lib/cn";
import { ART_ASSETS } from "../lib/artAssets";

/** Chat assistant avatar — voxel cup-on-coaster app icon (chat only). */
export const ASSISTANT_AVATAR_SRC = ART_ASSETS.assistantAvatar;
export const ASSISTANT_AVATAR_NIGHT_SRC = ART_ASSETS.assistantAvatarNight;

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
        className="kq-assistant-avatar-image kq-assistant-avatar-image--day"
        width={48}
        height={48}
        decoding="async"
        draggable={false}
      />
      <img
        src={ASSISTANT_AVATAR_NIGHT_SRC}
        alt=""
        className="kq-assistant-avatar-image kq-assistant-avatar-image--night"
        width={48}
        height={48}
        decoding="async"
        draggable={false}
      />
    </div>
  );
}
