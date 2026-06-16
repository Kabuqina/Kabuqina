// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { cn } from "../../lib/cn";

type Props = {
  value: boolean;
  onChange: (v: boolean) => void;
  disabled?: boolean;
  tone?: "default" | "kabuqina";
  "aria-label"?: string;
};

export function Toggle({ value, onChange, disabled, tone = "kabuqina", "aria-label": ariaLabel }: Props) {
  const activeClass =
    tone === "kabuqina"
      ? "bg-[var(--kq-color-primary)] dark:bg-[var(--kq-color-primary-light)]"
      : "bg-[var(--kq-color-primary)] dark:bg-[var(--kq-color-primary-light)]";
  const idleClass =
    tone === "kabuqina"
      ? "bg-[#d9cde3] dark:bg-[var(--kq-hover-bg-strong)]"
      : "bg-[#d9cde3] dark:bg-[var(--kq-hover-bg-strong)]";
  const focusClass = "focus-visible:ring-[var(--kq-color-primary)] dark:focus-visible:ring-[var(--kq-color-primary-light)]";

  return (
    <button
      type="button"
      role="switch"
      aria-label={ariaLabel}
      aria-checked={value}
      disabled={disabled}
      onClick={() => onChange(!value)}
      className={cn(
        "relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2",
        focusClass,
        "disabled:cursor-not-allowed disabled:opacity-50",
        value ? activeClass : idleClass,
      )}
    >
      <span
        className={cn(
          "pointer-events-none block h-5 w-5 translate-y-0 rounded-full bg-white shadow-sm ring-0 transition-transform dark:bg-[var(--kq-glass-bg)]",
          value ? "translate-x-5" : "translate-x-0",
        )}
      />
    </button>
  );
}
