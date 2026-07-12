// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { BookOpen, ChevronDown, Plus, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
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
  const dialog = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const firstFocusable = useRef<HTMLButtonElement>(null);
  const [open, setOpen] = useState(false);
  const [narrow, setNarrow] = useState(false);
  const current = spaces.find((space) => space.id === currentSpaceId);
  const firstSelectableSpaceId = spaces.find((space) => space.id !== currentSpaceId)?.id;

  useEffect(() => {
    if (!root.current || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(([entry]) => setNarrow(entry.contentRect.width < 640));
    observer.observe(root.current);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (open) firstFocusable.current?.focus();
  }, [open]);

  useEffect(() => {
    if (!open || narrow) return;
    const onPointerDown = (event: PointerEvent) => {
      if (event.target instanceof Node && !root.current?.contains(event.target)) {
        setOpen(false);
      }
    };
    document.addEventListener("pointerdown", onPointerDown);
    return () => document.removeEventListener("pointerdown", onPointerDown);
  }, [narrow, open]);

  const close = () => {
    setOpen(false);
    requestAnimationFrame(() => trigger.current?.focus());
  };

  const onKeyDown = (event: React.KeyboardEvent) => {
    if (event.key === "Escape") close();
    if (narrow && event.key === "Tab") {
      const focusable = [...(dialog.current?.querySelectorAll<HTMLElement>("[data-study-focus]") ?? [])]
        .filter((element) => !element.hasAttribute("disabled"));
      if (!focusable.length) return;
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
      {open && !narrow ? (
        <div
          className="kq-study-popover"
          aria-label={t("study.openSpace")}
        >
          <div role="listbox" aria-label={t("study.openSpace")}>
            {spaces.map((space) => (
              <button
                data-study-focus
                ref={space.id === firstSelectableSpaceId ? firstFocusable : undefined}
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
      ) : null}
      {open && narrow ? createPortal(
        <div
          className="kq-study-dialog-backdrop"
          role="dialog"
          aria-modal="true"
          aria-label={t("study.openSpace")}
        >
          <div className="kq-study-dialog" ref={dialog}>
            <button ref={firstFocusable} data-study-focus type="button" className="kq-study-dialog-close" onClick={close} aria-label={t("dialog.cancel")}><X aria-hidden /></button>
            <div role="listbox" aria-label={t("study.openSpace")}>
              {spaces.map((space) => (
                <button
                  data-study-focus
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
        </div>,
        document.body,
      ) : null}
      {pending ? <span className="kq-study-muted" role="status">{t("study.switching")}</span> : null}
      {error ? <span className="kq-study-error" role="alert">{t("study.switchFailed")}</span> : null}
    </div>
  );
}
