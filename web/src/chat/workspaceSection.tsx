// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

// Shared presentational primitives for the workspace panel's quick-action
// sections. Extracted from WorkspacePanel so feature modules (e.g. ./study)
// can render their own sections without a circular import back into the panel.

import { type ReactNode } from "react";

export function WorkspaceSectionHeading({
  children,
  dotColor = "var(--kq-color-primary-dark)",
}: {
  children: ReactNode;
  dotColor?: string;
}) {
  return (
    <h3 className="workspace-section-heading kq-section-heading inline-flex items-center gap-1.5 px-0 py-0 text-[12.5px] font-bold leading-snug tracking-normal">
      <span
        className="inline-block h-1.5 w-1.5 shrink-0 rounded-full"
        style={{ background: dotColor }}
      />
      {children}
    </h3>
  );
}

export function WorkspaceSection({
  sectionId,
  title,
  dotColor,
  children,
}: {
  sectionId: string;
  title: string;
  dotColor?: string;
  children?: ReactNode;
}) {
  return (
    <section data-workspace-section={sectionId} className="kq-workspace-card">
      <WorkspaceSectionHeading dotColor={dotColor}>{title}</WorkspaceSectionHeading>
      {children}
    </section>
  );
}

export function WorkspaceActionButton({
  icon,
  label,
  onClick,
}: {
  icon: ReactNode;
  label: string;
  onClick?: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="kq-quick-action justify-start rounded-[10px] px-2.5 py-2 text-left text-[13px] leading-snug transition"
    >
      {icon}
      {label}
    </button>
  );
}
