// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { ArrowLeft } from "lucide-react";
import { cn } from "../../lib/cn";

export function BackButton({
  children,
  onClick,
  /** Override spacing/layout — defaults to the in-body margin used by form pages. */
  className = "mb-5",
}: {
  children: React.ReactNode;
  onClick: () => void;
  className?: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "kq-btn-ghost inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium active:scale-[0.98] dark:text-[var(--kq-color-muted)] dark:hover:bg-[var(--kq-hover-bg-strong)] dark:hover:text-[var(--kq-color-strong)]",
        className
      )}
    >
      <ArrowLeft className="size-4" />
      {children}
    </button>
  );
}
