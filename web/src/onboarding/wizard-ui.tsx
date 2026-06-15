// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import type { ButtonHTMLAttributes, ReactNode } from "react";
import { cn } from "../lib/cn";

const btnRow =
  "flex flex-col gap-3 sm:flex-row sm:items-stretch sm:justify-end sm:gap-3";

/** Sticks to the bottom of the shell scroll area so long wizard steps keep actions reachable. */
export function WizardFooter({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div
      className={cn(
        "sticky bottom-0 z-20 -mx-[var(--hd-page-pad-x)] border-t border-[var(--kq-color-border)]/80 bg-[var(--kq-color-surface)]/95 px-[var(--hd-page-pad-x)] pt-4 sm:mx-0",
        "pb-[max(1rem,env(safe-area-inset-bottom,0px))]",
        className
      )}
    >
      {children}
    </div>
  );
}

export function WizardFooterActions({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cn(btnRow, className)}>{children}</div>;
}

const primaryBase =
  "inline-flex w-full min-h-[3rem] items-center justify-center rounded-[var(--radius-shell-lg)] px-6 py-3.5 text-base font-medium transition sm:w-auto sm:min-w-[12rem]";

export function WizardPrimaryButton({
  className,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      type="button"
      className={cn(
        primaryBase,
        "kq-btn-primary text-white active:scale-[0.99] disabled:cursor-not-allowed disabled:opacity-50",
        className
      )}
      {...props}
    />
  );
}

const secondaryBase =
  "inline-flex w-full min-h-[3rem] items-center justify-center rounded-[var(--radius-shell-lg)] border px-6 py-3.5 text-base font-medium transition sm:w-auto sm:min-w-[12rem]";

export function WizardSecondaryButton({
  className,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      type="button"
      className={cn(
        secondaryBase,
        "kq-btn-secondary text-[var(--kq-color-ink)] active:scale-[0.99] disabled:cursor-not-allowed disabled:opacity-50",
        className
      )}
      {...props}
    />
  );
}

export function WizardFooterHint({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <p
      className={cn(
        "hd-wizard-hint mt-3 text-center sm:text-left",
        className
      )}
    >
      {children}
    </p>
  );
}
