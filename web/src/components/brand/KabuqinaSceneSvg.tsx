// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import type { SVGProps } from "react";
import { CompanionCupSvg } from "./CompanionCupSvg";
import { KabuqinaCoasterSvg } from "./KabuqinaCoasterSvg";
import { kabuqinaBrandTokens } from "./kabuqinaBrandTokens";

export type KabuqinaSceneVariant = "hero" | "pill" | "social";

export type KabuqinaSceneSvgProps = Omit<SVGProps<SVGSVGElement>, "children" | "role"> & {
  className?: string;
  variant?: KabuqinaSceneVariant;
  title?: string;
  decorative?: boolean;
  embedded?: boolean;
};

type SceneLayout = {
  viewBox: string;
  width: number;
  height: number;
  showCoaster: boolean;
  showGroundShadow: boolean;
  coasterSize: number;
  coasterX: number;
  coasterY: number;
  groundCx: number;
  groundCy: number;
  groundRx: number;
  groundRy: number;
  contactCx: number;
  contactCy: number;
  contactRx: number;
  contactRy: number;
  cupX: number;
  cupY: number;
  cupSize: number;
  steam: boolean;
};

const sceneLayouts: Record<KabuqinaSceneVariant, SceneLayout> = {
  hero: {
    viewBox: "0 0 775 685",
    width: 775,
    height: 685,
    showCoaster: true,
    showGroundShadow: true,
    coasterSize: 535,
    coasterX: 387.5,
    coasterY: 538,
    groundCx: 387.5,
    groundCy: 635,
    groundRx: 230,
    groundRy: 35,
    contactCx: 388,
    contactCy: 547.7,
    contactRx: 124,
    contactRy: 21,
    cupX: 197,
    cupY: 204,
    cupSize: 400,
    steam: true,
  },
  pill: {
    viewBox: "0 0 620 548",
    width: 620,
    height: 548,
    showCoaster: false,
    showGroundShadow: false,
    coasterSize: 0,
    coasterX: 0,
    coasterY: 0,
    groundCx: 0,
    groundCy: 0,
    groundRx: 0,
    groundRy: 0,
    contactCx: 310,
    contactCy: 530,
    contactRx: 88,
    contactRy: 16,
    cupX: 0,
    cupY: 0,
    cupSize: 620,
    steam: true,
  },
  social: {
    viewBox: "0 0 1280 640",
    width: 1280,
    height: 640,
    showCoaster: true,
    showGroundShadow: true,
    coasterSize: 635,
    coasterX: 640,
    coasterY: 430.2,
    groundCx: 640,
    groundCy: 554.5,
    groundRx: 267.5,
    groundRy: 47.5,
    contactCx: 640,
    contactCy: 397.8,
    contactRx: 147.5,
    contactRy: 29,
    cupX: 387.5,
    cupY: -24,
    cupSize: 505,
    steam: false,
  },
};

export function KabuqinaSceneSvg({
  className,
  variant = "hero",
  title,
  decorative = true,
  embedded = false,
  "aria-label": ariaLabel,
  ...svgProps
}: KabuqinaSceneSvgProps) {
  const layout = sceneLayouts[variant];
  const tokens = kabuqinaBrandTokens;
  const label = title ?? ariaLabel ?? `Kabuqina ${variant} companion scene`;

  return (
    <svg
      {...svgProps}
      className={className}
      viewBox={layout.viewBox}
      role={decorative ? undefined : "img"}
      aria-hidden={decorative ? true : undefined}
      aria-label={decorative ? undefined : ariaLabel ?? (!title ? label : undefined)}
      xmlns="http://www.w3.org/2000/svg"
    >
      {!decorative && title ? <title>{title}</title> : null}
      {variant === "social" ? <rect x="0" y="0" width={layout.width} height={layout.height} fill="#ffffff" /> : null}
      {layout.showGroundShadow ? (
        <ellipse
          cx={layout.groundCx}
          cy={layout.groundCy}
          rx={layout.groundRx}
          ry={layout.groundRy}
          fill={tokens.shadow.ink}
          fillOpacity="0.18"
        />
      ) : null}
      {layout.showCoaster ? (
        <g transform={`translate(${layout.coasterX - layout.coasterSize / 2} ${layout.coasterY - layout.coasterSize / 2})`}>
          <KabuqinaCoasterSvg
            variant={variant}
            width={layout.coasterSize}
            height={layout.coasterSize}
            decorative
            embedded={embedded}
          />
        </g>
      ) : null}
      <ellipse
        cx={layout.contactCx}
        cy={layout.contactCy}
        rx={layout.contactRx}
        ry={layout.contactRy}
        fill={tokens.shadow.deep}
        fillOpacity={tokens.shadow.contactOpacity}
      />
      <g transform={`translate(${layout.cupX} ${layout.cupY}) scale(${layout.cupSize / 100})`}>
        <CompanionCupSvg width={100} height={100} steam={layout.steam} shadow={false} decorative embedded={embedded} />
      </g>
    </svg>
  );
}
