// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { cn } from "../lib/cn";
import { useCustomCompanionImage } from "../lib/ui-prefs";

/** Floating cup-on-coaster pill used in companion window and boot screen. */
export function CompanionPillScene({ className }: { className?: string }) {
  const customImage = useCustomCompanionImage();

  return (
    <div className={cn("kq-companion-pill-scene", className)}>
      <img
        src={customImage ?? "/kabuqina_pill_scene.svg"}
        alt=""
        className="kq-companion-pill-svg"
        draggable={false}
      />
    </div>
  );
}
