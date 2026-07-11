// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { Inbox } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useI18n } from "../lib/i18n";

export function DraftInboxButton({ counts }: { counts: Readonly<Record<string, number>> }) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const button = useRef<HTMLButtonElement>(null);
  const total = Object.values(counts).reduce((sum, count) => sum + count, 0);
  const displayCount = total > 99 ? "99+" : String(total);

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setOpen(false);
        button.current?.focus();
      }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (event: PointerEvent) => {
      if (event.target instanceof Node && !root.current?.contains(event.target)) {
        setOpen(false);
      }
    };
    document.addEventListener("pointerdown", onPointerDown);
    return () => document.removeEventListener("pointerdown", onPointerDown);
  }, [open]);

  return (
    <div className="kq-study-menu-root" ref={root}>
      <button
        ref={button}
        type="button"
        className="kq-study-top-action"
        aria-expanded={open}
        aria-haspopup="dialog"
        onClick={() => setOpen((value) => !value)}
      >
        <Inbox aria-hidden />
        <span>{t("study.drafts")}</span>
        <span className="kq-study-count" aria-label={t("study.draftCount", { count: total })}>{displayCount}</span>
      </button>
      {open ? (
        <div className="kq-study-popover" role="dialog" aria-label={t("study.drafts")}>
          {total === 0 ? <p>{t("study.noDrafts")}</p> : (
            <ul>
              {Object.entries(counts).sort(([a], [b]) => a.localeCompare(b)).map(([kind, count]) => (
                <li key={kind}><span>{kind.replaceAll("_", " ")}</span><strong>{count}</strong></li>
              ))}
            </ul>
          )}
          <p className="kq-study-muted">{t("study.draftReviewHint")}</p>
        </div>
      ) : null}
    </div>
  );
}
