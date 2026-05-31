import { forwardRef } from "react";
import { cn } from "../lib/cn";

type Props = {
  children: React.ReactNode;
  className?: string;
  /** Narrow column for forms / onboarding (max-width + horizontal padding) */
  variant?: "full" | "narrow";
  /** Chat shell: flat white canvas (Kimi-style) instead of gradient. */
  surface?: "default" | "chat";
};

const narrowInner = "mx-auto w-full max-w-[var(--hd-content-max)] px-[var(--hd-page-pad-x)] py-[var(--hd-page-pad-y)]";

export const AppScaffold = forwardRef<HTMLDivElement, Props>(
  ({ children, className, variant = "full", surface: _surface = "default" }, ref) => {
    return (
      <div
        ref={ref}
        className={cn(
          "min-h-full w-full kq-chat-shell text-[var(--kq-color-ink)]",
          variant === "narrow" && "flex flex-col",
          className
        )}
      >
        {variant === "narrow" ? <div className={cn(narrowInner, "flex-1")}>{children}</div> : children}
      </div>
    );
  }
);

AppScaffold.displayName = "AppScaffold";
