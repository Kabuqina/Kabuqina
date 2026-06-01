// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { ArrowLeft } from "lucide-react";

export function BackButton({
  children,
  onClick,
}: {
  children: React.ReactNode;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="kq-btn-ghost mb-5 inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium active:scale-[0.98] dark:text-zinc-400 dark:hover:bg-zinc-800/60 dark:hover:text-zinc-200"
    >
      <ArrowLeft className="size-4" />
      {children}
    </button>
  );
}
