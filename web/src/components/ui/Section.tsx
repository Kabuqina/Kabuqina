// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import type { LucideIcon } from "lucide-react";

type Props = {
  icon?: LucideIcon;
  title: string;
  desc?: string;
  children?: React.ReactNode;
  className?: string;
  action?: React.ReactNode;
};

export function Section({ icon: Icon, title, desc, children, className, action }: Props) {
  return (
    <section
      className={`hd-glass-subtle p-5 sm:p-6 ${className ?? ""}`}
    >
      <div className="flex items-start gap-3.5">
        {Icon && (
          <div className="kq-icon-well mt-0.5 flex size-10 shrink-0 items-center justify-center rounded-[var(--radius-shell-lg)]">
            <Icon className="size-[1.125rem]" strokeWidth={2} />
          </div>
        )}
        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0">
              <h2 className="text-[0.9375rem] font-semibold leading-5 text-[var(--kq-color-strong)] dark:text-zinc-100">
                {title}
              </h2>
              {desc && (
                <p className="mt-1 text-sm leading-relaxed text-[var(--kq-color-muted)] dark:text-zinc-400">
                  {desc}
                </p>
              )}
            </div>
            {action && (
              <div className="mt-0.5 shrink-0">{action}</div>
            )}
          </div>
        </div>
      </div>
      {children && <div className="mt-5">{children}</div>}
    </section>
  );
}
