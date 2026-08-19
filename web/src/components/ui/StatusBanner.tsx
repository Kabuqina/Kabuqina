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

/**
 * 语义色全部来自组件 Sheet 的四组已校验配色（见 index.css 的 .kq-banner--*），
 * 不再用 Tailwind 的 emerald/amber/red 原生色——那套和桌面世界不同族，
 * 也没走过对比度校验。这里只留图标，颜色交给令牌类。
 */
const variantIcon: Record<Variant, LucideIcon> = {
  success: CheckCircle2,
  warning: AlertTriangle,
  info: Info,
  error: XCircle,
  neutral: Info,
};

type Props = {
  variant: Variant;
  title?: string;
  children?: ReactNode;
  className?: string;
};

export function StatusBanner({ variant, title, children, className }: Props) {
  const Icon = variantIcon[variant];
  return (
    <div
      className={cn(
        "kq-banner flex items-start gap-2.5 rounded-[var(--radius-shell-lg)] px-3.5 py-2.5 text-sm",
        `kq-banner--${variant}`,
        className
      )}
    >
      {/* 图标继承横幅的语义前景色，不再各自指定。 */}
      <Icon className="mt-0.5 h-4 w-4 shrink-0" strokeWidth={2.25} />
      <div className="min-w-0 flex-1 leading-relaxed">
        {title ? <p className="font-medium">{title}</p> : null}
        {children ? (
          <div className={cn(title && "mt-1 text-xs opacity-90")}>{children}</div>
        ) : null}
      </div>
    </div>
  );
}
