// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import type { ButtonHTMLAttributes } from "react";
import { cn } from "../../lib/cn";

type Props = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost";
  size?: "sm" | "md";
};

export function Button({ variant = "primary", size = "md", className, ...rest }: Props) {
  return (
    <button
      className={cn(
        "inline-flex items-center justify-center gap-1.5 rounded-[var(--radius-shell-lg)] font-medium transition select-none",
        "disabled:cursor-not-allowed disabled:opacity-50",
        variant === "primary" && "kq-btn-primary text-white dark:text-white",
        variant === "secondary" && "kq-btn-secondary",
        variant === "ghost" && "kq-btn-ghost",
        size === "sm" && "px-3 py-1.5 text-xs",
        size === "md" && "px-4 py-2 text-sm",
        className,
      )}
      {...rest}
    />
  );
}
