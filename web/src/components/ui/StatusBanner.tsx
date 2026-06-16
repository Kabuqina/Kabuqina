// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import type { ReactNode } from "react";
import {
  CheckCircle2,
  AlertTriangle,
  Info,
  XCircle,
  type LucideIcon,
} from "lucide-react";
import { cn } from "../../lib/cn";

type Variant = "success" | "warning" | "info" | "error" | "neutral";

const variantMeta: Record<
  Variant,
  { icon: LucideIcon; border: string; bg: string; text: string; iconColor: string }
> = {
  success: {
    icon: CheckCircle2,
    border: "border-emerald-200/90 dark:border-emerald-800/70",
    bg: "bg-emerald-50/70 dark:bg-emerald-950/30",
    text: "text-emerald-950 dark:text-emerald-100",
    iconColor: "text-emerald-600 dark:text-emerald-400",
  },
  warning: {
    icon: AlertTriangle,
    border: "border-amber-200/90 dark:border-amber-800/60",
    bg: "bg-amber-50/70 dark:bg-amber-950/30",
    text: "text-amber-950 dark:text-amber-100",
    iconColor: "text-amber-600 dark:text-amber-400",
  },
  info: {
    icon: Info,
    border: "border-[var(--kq-color-border)] dark:border-[var(--kq-color-primary-light)]/30",
    bg: "bg-[var(--kq-color-primary-pale)]/70 dark:bg-[var(--kq-color-primary-light)]/10",
    text: "text-[var(--kq-color-strong)] dark:text-[var(--kq-color-strong)]",
    iconColor: "text-[var(--kq-color-primary)] dark:text-[var(--kq-color-primary-light)]",
  },
  error: {
    icon: XCircle,
    border: "border-red-200/90 dark:border-red-800/60",
    bg: "bg-red-50/70 dark:bg-red-950/30",
    text: "text-red-950 dark:text-red-100",
    iconColor: "text-red-600 dark:text-red-400",
  },
  neutral: {
    icon: Info,
    border: "border-[var(--kq-color-border)] dark:border-[var(--kq-color-border)]",
    bg: "bg-[var(--kq-color-primary-pale)]/45 dark:bg-[var(--kq-glass-bg)]",
    text: "text-[var(--kq-color-ink)] dark:text-[var(--kq-color-ink)]",
    iconColor: "text-[var(--kq-color-muted)] dark:text-[var(--kq-color-muted)]",
  },
};

type Props = {
  variant: Variant;
  title?: string;
  children?: ReactNode;
  className?: string;
};

export function StatusBanner({ variant, title, children, className }: Props) {
  const meta = variantMeta[variant];
  const Icon = meta.icon;
  return (
    <div
      className={cn(
        "flex items-start gap-2.5 rounded-[var(--radius-shell-lg)] border px-3.5 py-2.5 text-sm",
        meta.border,
        meta.bg,
        meta.text,
        className
      )}
    >
      <Icon className={cn("mt-0.5 h-4 w-4 shrink-0", meta.iconColor)} strokeWidth={2.25} />
      <div className="min-w-0 flex-1 leading-relaxed">
        {title ? <p className="font-medium">{title}</p> : null}
        {children ? (
          <div className={cn(title && "mt-1 text-xs opacity-90")}>{children}</div>
        ) : null}
      </div>
    </div>
  );
}
