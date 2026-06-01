// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { cn } from "../../lib/cn";

type Variant = "primary" | "secondary" | "danger" | "ghost";

type Props = {
  variant?: Variant;
  children: React.ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  type?: "button" | "submit";
  className?: string;
  title?: string;
};

const base =
  "inline-flex items-center justify-center gap-1.5 rounded-lg px-3.5 py-1.5 text-sm font-medium transition select-none";

const variantStyles: Record<Variant, string> = {
  primary: "kq-btn-primary text-white dark:text-white active:scale-[0.98]",
  secondary: "kq-btn-secondary active:scale-[0.98]",
  danger:
    "border border-red-200/90 bg-red-50 text-red-700 hover:bg-red-100 active:scale-[0.98] dark:border-red-900/50 dark:bg-red-950/30 dark:text-red-300 dark:hover:bg-red-950/50",
  ghost: "kq-btn-ghost active:scale-[0.98]",
};

export function PlatformButton({
  variant = "secondary",
  children,
  onClick,
  disabled,
  type = "button",
  className,
  title,
}: Props) {
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      title={title}
      className={cn(
        base,
        variantStyles[variant],
        "disabled:cursor-not-allowed disabled:opacity-50 disabled:active:scale-100",
        className
      )}
    >
      {children}
    </button>
  );
}
