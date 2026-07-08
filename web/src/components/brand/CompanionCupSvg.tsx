// Component code: Copyright 2026 Kabuqina Contributors — Apache-2.0.
// Embedded Kabuqina brand artwork (mascot design, vector geometry, palette):
// Copyright (c) 2026 ladylydia — All Rights Reserved, NOT Apache-2.0.
// See assets/brand/LICENSE. Unbranded forks must replace the artwork.
// SPDX-License-Identifier: Apache-2.0 AND LicenseRef-Kabuqina-Brand

import { useId } from "react";
import type { SVGProps } from "react";
import { kabuqinaBrandTokens } from "./kabuqinaBrandTokens";

export type CompanionCupSvgProps = Omit<SVGProps<SVGSVGElement>, "children" | "role"> & {
  className?: string;
  title?: string;
  steam?: boolean;
  shadow?: boolean;
  decorative?: boolean;
  embedded?: boolean;
};

function svgId(rawId: string, name: string): string {
  return `kq-cup-${rawId.replace(/[^a-zA-Z0-9_-]/g, "")}-${name}`;
}

export function CompanionCupSvg({
  className,
  title = "Kabuqina companion cup",
  steam = false,
  shadow = true,
  decorative = true,
  embedded = false,
  ...svgProps
}: CompanionCupSvgProps) {
  const rawId = useId();
  const bodyGradientId = svgId(rawId, "body");
  const rimGradientId = svgId(rawId, "rim");
  const latteGradientId = svgId(rawId, "latte");
  const cupShadowId = svgId(rawId, "shadow");
  const steamBlurId = svgId(rawId, "steam");
  const tokens = kabuqinaBrandTokens;

  const content = (
    <>
      <defs>
        <linearGradient id={bodyGradientId} x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor={tokens.cup.bodyTop} />
          <stop offset="45%" stopColor={tokens.cup.bodyMid} />
          <stop offset="100%" stopColor={tokens.cup.bodyBottom} />
        </linearGradient>
        <linearGradient id={rimGradientId} x1="0%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%" stopColor={tokens.cup.rimTop} />
          <stop offset="100%" stopColor={tokens.cup.rimBottom} />
        </linearGradient>
        <radialGradient id={latteGradientId} cx="50%" cy="32%" rx="46%" ry="58%">
          <stop offset="0%" stopColor={tokens.latte.center} />
          <stop offset="35%" stopColor={tokens.latte.mid} />
          <stop offset="68%" stopColor={tokens.latte.outer} />
          <stop offset="100%" stopColor={tokens.latte.edge} />
        </radialGradient>
        <filter id={cupShadowId} x="-18%" y="-18%" width="136%" height="138%">
          <feDropShadow
            dx="0"
            dy="2"
            stdDeviation="1.8"
            floodColor={tokens.shadow.ink}
            floodOpacity={tokens.shadow.cupOpacity}
          />
        </filter>
        <filter id={steamBlurId} x="-20%" y="-20%" width="140%" height="140%">
          <feGaussianBlur stdDeviation="0.45" />
        </filter>
      </defs>
      {steam ? (
        <g opacity={tokens.shadow.steamOpacity} filter={`url(#${steamBlurId})`}>
          <path
            d="M 31 17 C 25 9 36 5 30 -3"
            fill="none"
            stroke="#ffffff"
            strokeOpacity="0.66"
            strokeWidth="5"
            strokeLinecap="round"
          />
          <path
            d="M 51 18 C 45 10 57 6 51 -2"
            fill="none"
            stroke="#ffffff"
            strokeOpacity="0.58"
            strokeWidth="4.4"
            strokeLinecap="round"
          />
          <path
            d="M 69 17 C 63 9 75 5 69 -4"
            fill="none"
            stroke="#ffffff"
            strokeOpacity="0.62"
            strokeWidth="4.8"
            strokeLinecap="round"
          />
        </g>
      ) : null}
      <g filter={shadow ? `url(#${cupShadowId})` : undefined}>
        <path
          d="M 70 41.32 C 99 43.2 99 66.8 70 69.2"
          fill="none"
          stroke={tokens.cup.handle}
          strokeWidth="4.1"
          strokeLinecap="round"
        />
        <path
          d="M 14 27 L 14 55 Q 14 86 45 86 L 50.5 86 Q 81.5 86 81.5 55 L 81.5 27 Z"
          fill={`url(#${bodyGradientId})`}
          stroke={tokens.cup.border}
          strokeOpacity={tokens.cup.borderOpacity}
          strokeWidth="0.35"
        />
        <rect
          x="11.5"
          y="16"
          width="72.5"
          height="21"
          rx="10.5"
          fill={`url(#${rimGradientId})`}
          stroke={tokens.cup.border}
          strokeOpacity={tokens.cup.rimBorderOpacity}
          strokeWidth="0.3"
        />
        <ellipse cx="47.75" cy="34.21" rx="28.35" ry="5.31" fill={`url(#${latteGradientId})`} />
        <ellipse
          cx="21"
          cy="66"
          rx="7"
          ry="4"
          fill={tokens.cup.blush}
          fillOpacity={tokens.cup.blushOpacity}
        />
        <ellipse
          cx="56.5"
          cy="66"
          rx="7"
          ry="4"
          fill={tokens.cup.blush}
          fillOpacity={tokens.cup.blushOpacity}
        />
        <circle cx="31.5" cy="55.5" r="2.5" fill={tokens.cup.eye} />
        <circle cx="40.25" cy="55.5" r="2.5" fill={tokens.cup.eye} />
      </g>
    </>
  );

  if (embedded) {
    return <g>{content}</g>;
  }

  return (
    <svg
      {...svgProps}
      className={className}
      viewBox="0 0 100 100"
      role={decorative ? undefined : "img"}
      aria-hidden={decorative ? true : undefined}
      aria-label={!decorative && !title ? "Kabuqina companion cup" : undefined}
      xmlns="http://www.w3.org/2000/svg"
    >
      {!decorative && title ? <title>{title}</title> : null}
      {content}
    </svg>
  );
}
