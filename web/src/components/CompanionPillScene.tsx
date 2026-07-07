// Component code: Copyright 2026 Kabuqina Contributors — Apache-2.0.
// Embedded Kabuqina brand artwork (mascot scene composition):
// Copyright (c) 2026 ladylydia — All Rights Reserved, NOT Apache-2.0.
// See assets/brand/LICENSE. Unbranded forks must replace the artwork.
// SPDX-License-Identifier: Apache-2.0 AND LicenseRef-Kabuqina-Brand

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
