// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

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
