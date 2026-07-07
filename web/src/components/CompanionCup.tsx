// Component code: Copyright 2026 Kabuqina Contributors — Apache-2.0.
// Embedded Kabuqina brand artwork (mascot design as rendered in CSS/markup):
// Copyright (c) 2026 ladylydia — All Rights Reserved, NOT Apache-2.0.
// See assets/brand/LICENSE. Unbranded forks must replace the artwork.
// SPDX-License-Identifier: Apache-2.0 AND LicenseRef-Kabuqina-Brand

import { cn } from "../lib/cn";

type CompanionCupVariant = "default" | "brand";

export interface CompanionCupProps {
  className?: string;
  /** Brand cup: 3D ceramic body + latte fill (hero, pill, avatar). */
  variant?: CompanionCupVariant;
  /** Wispy steam — hero and compact pill only. */
  steam?: boolean;
}

/** Kabuqina mascot — CSS coffee cup used in chat, hero, pill, and avatar. */
export function CompanionCup({
  className,
  variant = "default",
  steam = false,
}: CompanionCupProps) {
  return (
    <div
      className={cn(
        "kq-companion-cup",
        variant === "brand" && "kq-companion-cup--brand",
        className,
      )}
      aria-hidden
    >
      <div className="kq-companion-cup-handle" />
      <div className="kq-companion-cup-body" />
      <div className="kq-companion-cup-face">
        <div className="kq-companion-cup-eye" />
        <div className="kq-companion-cup-eye" />
      </div>
      <div className="kq-companion-cup-blush left" />
      <div className="kq-companion-cup-blush right" />
      {steam ? <span className="kq-companion-cup-steam" aria-hidden /> : null}
    </div>
  );
}
