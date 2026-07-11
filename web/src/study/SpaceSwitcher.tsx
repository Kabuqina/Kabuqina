// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { BookOpen, ChevronDown, Plus, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useI18n } from "../lib/i18n";
import type { StudySpaceSummary } from "./repository";

export function SpaceSwitcher({ spaces, currentSpaceId, pending, error, onSelect }: {
  spaces: StudySpaceSummary[];
  currentSpaceId: string;
  pending: boolean;
  error: boolean;
  onSelect: (spaceId: string) => void;
}) {
  const { t } = useI18n();
  const root = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const firstOption = useRef<HTMLButtonElement>(null);
  const [open, setOpen] = useState(false);
  const [narrow, setNarrow] = useState(false);
  const current = spaces.find((space) => space.id === currentSpaceId);

  useEffect(() => {
    if (!root.current || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(([entry]) => setNarrow(entry.contentRect.width < 640));
    observer.observe(root.current);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (open) firstOption.current?.focus();
  }, [open]);

  const close = () => {
    setOpen(false);
    requestAnimationFrame(() => trigger.current?.focus());
  };

  const onKeyDown = (event: React.KeyboardEvent) => {
    if (event.key === "Escape") close();
    if (narrow && event.key === "Tab") {
      const focusable = root.current?.querySelectorAll<HTMLElement>("[data-study-focus]");
      if (!focusable?.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    }
  };

  return (
    <div className="kq-study-switcher" ref={root} onKeyDown={onKeyDown}>
      <button
        ref={trigger}
        type="button"
        className="kq-study-space-trigger"
        aria-expanded={open}
        aria-haspopup={narrow ? "dialog" : "listbox"}
        onClick={() => setOpen((value) => !value)}
      >
        <BookOpen aria-hidden />
        <span>{current?.title ?? t("study.openSpace")}</span>
        <ChevronDown aria-hidden />
      </button>
      {open ? (
        <div
          className={narrow ? "kq-study-dialog-backdrop" : "kq-study-popover"}
          role={narrow ? "dialog" : undefined}
          aria-modal={narrow || undefined}
          aria-label={t("study.openSpace")}
        >
          <div className={narrow ? "kq-study-dialog" : undefined}>
            {narrow ? <button data-study-focus type="button" className="kq-study-dialog-close" onClick={close} aria-label={t("dialog.cancel")}><X aria-hidden /></button> : null}
            <div role="listbox" aria-label={t("study.openSpace")}>
              {spaces.map((space, index) => (
                <button
                  data-study-focus
                  ref={index === 0 ? firstOption : undefined}
                  key={space.id}
                  type="button"
                  role="option"
                  aria-selected={space.id === currentSpaceId}
                  disabled={pending || space.id === currentSpaceId}
                  onClick={() => { onSelect(space.id); setOpen(false); }}
                >
                  <span>{space.title}</span>{space.id === currentSpaceId ? <span aria-hidden>·</span> : null}
                </button>
              ))}
            </div>
            <Link data-study-focus className="kq-study-new-notebook" to="/chat" title={t("study.newNotebookHint")}>
              <Plus aria-hidden />{t("study.newNotebook")}
            </Link>
          </div>
        </div>
      ) : null}
      {pending ? <span className="kq-study-muted" role="status">{t("study.switching")}</span> : null}
      {error ? <span className="kq-study-error" role="alert">{t("study.switchFailed")}</span> : null}
    </div>
  );
}
