// Component code: Copyright 2026 Kabuqina Contributors — Apache-2.0.
// Embedded Kabuqina brand artwork (mascot design, vector geometry, palette):
// Copyright (c) 2026 ladylydia — All Rights Reserved, NOT Apache-2.0.
// See assets/brand/LICENSE. Unbranded forks must replace the artwork.
// SPDX-License-Identifier: Apache-2.0 AND LicenseRef-Kabuqina-Brand

import { useId } from "react";
import type { SVGProps } from "react";
import { kabuqinaBrandTokens } from "./kabuqinaBrandTokens";

export type KabuqinaCoasterVariant = "hero" | "pill" | "social";

export type KabuqinaCoasterSvgProps = Omit<SVGProps<SVGSVGElement>, "children" | "role"> & {
  className?: string;
  variant?: KabuqinaCoasterVariant;
  title?: string;
  decorative?: boolean;
  embedded?: boolean;
};

type CoasterLayout = {
  viewBox: string;
  size: number;
  radius: number;
  grid: number;
  center: number;
  yScale: number;
  zRotate: number;
  lineOpacity?: number;
  borderOpacity?: number;
  gridStrokeWidth?: number;
};

const coasterLayouts: Record<KabuqinaCoasterVariant, CoasterLayout> = {
  hero: {
    // Include -7° rotation padding so embedded letterbox does not push the mat past the scene clip.
    viewBox: "0 0 535 336",
    size: 535,
    radius: 115,
    grid: 82,
    center: 267.5,
    yScale: 0.52,
    zRotate: -7,
  },
  pill: {
    viewBox: "0 0 397 252",
    size: 397,
    radius: 83,
    grid: 60,
    center: 198.5,
    yScale: 0.52,
    zRotate: -7,
    lineOpacity: 0.78,
    borderOpacity: 0.79,
    gridStrokeWidth: 1.45,
  },
  social: {
    viewBox: "0 0 635 343",
    size: 635,
    radius: 136,
    grid: 97,
    center: 317.5,
    yScale: 0.54,
    zRotate: -6,
  },
};

function svgId(rawId: string, name: string): string {
  return `kq-coaster-${rawId.replace(/[^a-zA-Z0-9_-]/g, "")}-${name}`;
}

export function KabuqinaCoasterSvg({
  className,
  variant = "hero",
  title,
  decorative = true,
  embedded = false,
  width,
  height,
  ...svgProps
}: KabuqinaCoasterSvgProps) {
  const rawId = useId();
  const layout = coasterLayouts[variant];
  const patternId = svgId(rawId, "gingham");
  const tokens = kabuqinaBrandTokens;
  const label = title ?? `Kabuqina ${variant} gingham coaster`;
  const halfGrid = layout.grid / 2;
  const lineOpacity = layout.lineOpacity ?? tokens.coaster.lineOpacity;
  const borderOpacity = layout.borderOpacity ?? tokens.coaster.borderOpacity;
  const gridStrokeWidth = layout.gridStrokeWidth ?? 1.4;
  const viewportHeight = Number(layout.viewBox.split(" ")[3]);
  const targetHeight = Number(height ?? layout.size);
  const letterboxY = embedded ? (targetHeight - viewportHeight) / 2 : 0;

  const content = (
    <>
      <defs>
        <pattern id={patternId} width={layout.grid} height={layout.grid} patternUnits="userSpaceOnUse">
          <rect width={layout.grid} height={layout.grid} fill={tokens.coaster.background} />
          <path
            d={`M 0 0 H ${layout.grid}`}
            stroke={tokens.coaster.line}
            strokeOpacity={lineOpacity}
            strokeWidth={gridStrokeWidth}
          />
          <path
            d={`M 0 0 V ${layout.grid}`}
            stroke={tokens.coaster.line}
            strokeOpacity={lineOpacity}
            strokeWidth={gridStrokeWidth}
          />
          <path
            d={`M 0 ${halfGrid} H ${layout.grid}`}
            stroke={tokens.coaster.line}
            strokeOpacity={lineOpacity * 0.58}
            strokeWidth={gridStrokeWidth - 0.25}
          />
          <path
            d={`M ${halfGrid} 0 V ${layout.grid}`}
            stroke={tokens.coaster.line}
            strokeOpacity={lineOpacity * 0.58}
            strokeWidth={gridStrokeWidth - 0.25}
          />
        </pattern>
      </defs>
      {/* Smaller yScale = more Y compression = mat lying on the table, not facing the viewer. */}
      <g transform={`translate(${layout.center} ${layout.center * layout.yScale}) rotate(${layout.zRotate}) scale(1 ${layout.yScale})`}>
        <rect
          x={-layout.size / 2}
          y={-layout.size / 2}
          width={layout.size}
          height={layout.size}
          rx={layout.radius}
          fill={`url(#${patternId})`}
          stroke={tokens.coaster.border}
          strokeOpacity={borderOpacity}
          strokeWidth="1.05"
        />
      </g>
    </>
  );

  if (embedded) {
    return (
      <g transform={letterboxY ? `translate(0 ${letterboxY})` : undefined}>
        {content}
      </g>
    );
  }

  return (
    <svg
      {...svgProps}
      className={className}
      width={width}
      height={height}
      viewBox={layout.viewBox}
      role={decorative ? undefined : "img"}
      aria-hidden={decorative ? true : undefined}
      aria-label={!decorative && !title ? label : undefined}
      xmlns="http://www.w3.org/2000/svg"
    >
      {!decorative && title ? <title>{title}</title> : null}
      {content}
    </svg>
  );
}
