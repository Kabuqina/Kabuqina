// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { CompanionCup } from "./CompanionCup";
import { cn } from "../lib/cn";

/** Floating cup-on-coaster pill used in companion window and boot screen. */
export function CompanionPillScene({ className }: { className?: string }) {
  return (
    <div className={cn("kq-companion-pill-scene", className)}>
      <div className="kq-companion-pill-mat">
        <div className="kq-companion-pill-cup">
          <CompanionCup variant="brand" steam />
        </div>
      </div>
    </div>
  );
}
