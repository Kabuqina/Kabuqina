// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useEffect, useRef, useState } from "react";
import { X } from "lucide-react";
import { invoke } from "@tauri-apps/api/core";
import { LogicalSize } from "@tauri-apps/api/dpi";
import { getCurrentWindow } from "@tauri-apps/api/window";
import { CompanionPillScene } from "../components/CompanionPillScene";
import { cn } from "../lib/cn";
import { useI18n } from "../lib/i18n";
import {
  clearCustomCompanionImage,
  setCustomCompanionImage,
  validateCustomCompanionImageFile,
} from "../lib/ui-prefs";

/** Pixels²: move more than sqrt(this) before we call `startDragging`, so plain double‑clicks open main. */
const COMPACT_DRAG_SQ_THRESHOLD = 7 * 7;
/** Match `.kq-companion-pill-scene` (5rem × 5.56rem); extra height protects the floating art from top-edge clipping. */
const PILL_REM_W = 5;
const PILL_REM_H = 5.56;
const MENU_REM_W = 20.25;
const MENU_REM_H = 8.75;

function rootFontPx(): number {
  const px = parseFloat(getComputedStyle(document.documentElement).fontSize);
  return Number.isFinite(px) && px > 0 ? px : 16;
}

function pillLogicalSize(): { w: number; h: number } {
  const rootPx = rootFontPx();
  return {
    w: Math.ceil(PILL_REM_W * rootPx),
    h: Math.ceil(PILL_REM_H * rootPx),
  };
}

function menuLogicalSize(): { w: number; h: number } {
  const rootPx = rootFontPx();
  return {
    w: Math.ceil(MENU_REM_W * rootPx),
    h: Math.ceil(MENU_REM_H * rootPx),
  };
}

async function resizeCompanionWindow(width: number, height: number): Promise<void> {
  try {
    await invoke("cmd_resize_companion", { width, height });
  } catch (error) {
    console.error("cmd_resize_companion failed:", error);
    try {
      await getCurrentWindow().setSize(new LogicalSize(width, height));
    } catch (fallbackError) {
      console.error("companion setSize fallback failed:", fallbackError);
    }
  }
}

async function placeCompanionWindow(): Promise<void> {
  try {
    await invoke("cmd_ensure_companion_position");
  } catch (error) {
    console.error("cmd_ensure_companion_position failed:", error);
  }
}

export function CompanionWindow() {
  const { locale, t } = useI18n();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const [imageError, setImageError] = useState<string | null>(null);
  const compactDragRef = useRef<{
    down: boolean;
    startX: number;
    startY: number;
    started: boolean;
  }>({ down: false, startX: 0, startY: 0, started: false });

  useEffect(() => {
    void getCurrentWindow().setShadow(false).catch((error) => {
      console.error("companion setShadow(false) failed:", error);
    });
  }, []);

  useEffect(() => {
    const sync = () => {
      const { w, h } = menuOpen ? menuLogicalSize() : pillLogicalSize();
      void resizeCompanionWindow(w, h).then(() => placeCompanionWindow());
    };
    sync();
    const observer = new ResizeObserver(sync);
    observer.observe(document.documentElement);
    return () => observer.disconnect();
  }, [menuOpen]);

  useEffect(() => {
    const root = document.getElementById("root");
    const previous = {
      htmlOverflow: document.documentElement.style.overflow,
      bodyOverflow: document.body.style.overflow,
      rootOverflow: root?.style.overflow,
    };

    document.documentElement.style.overflow = "hidden";
    document.body.style.overflow = "hidden";
    if (root) {
      root.style.overflow = "hidden";
    }

    return () => {
      document.documentElement.style.overflow = previous.htmlOverflow;
      document.body.style.overflow = previous.bodyOverflow;
      if (root && previous.rootOverflow !== undefined) {
        root.style.overflow = previous.rootOverflow;
      }
    };
  }, []);

  const openMain = () => {
    void invoke("cmd_focus_main_window");
  };

  const openCompanionMenu = (event: React.MouseEvent<HTMLDivElement>) => {
    event.preventDefault();
    event.stopPropagation();
    compactDragRef.current = {
      down: false,
      startX: 0,
      startY: 0,
      started: false,
    };
    setImageError(null);
    setMenuOpen(true);
  };

  const closeCompanionMenu = () => {
    setMenuOpen(false);
    setImageError(null);
  };

  const handleCompanionImagePicked = (file: File | undefined) => {
    if (!file) return;
    const validation = validateCustomCompanionImageFile(file);
    if (!validation.ok) {
      setImageError(
        validation.reason === "size"
          ? t("settings.companionImageErrSize")
          : t("settings.companionImageErrType")
      );
      return;
    }
    const reader = new FileReader();
    reader.onload = () => {
      const dataUrl = typeof reader.result === "string" ? reader.result : "";
      if (!dataUrl.startsWith("data:image/")) {
        setImageError(t("settings.companionImageErrType"));
        return;
      }
      setCustomCompanionImage(dataUrl);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
      closeCompanionMenu();
    };
    reader.onerror = () => setImageError(t("settings.companionImageErrRead"));
    reader.readAsDataURL(file);
  };

  const resetCompanionImage = () => {
    clearCustomCompanionImage();
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
    closeCompanionMenu();
  };

  const onCompactPointerDown = (event: React.PointerEvent<HTMLDivElement>) => {
    if (event.pointerType === "mouse" && event.button !== 0) {
      return;
    }
    event.currentTarget.setPointerCapture(event.pointerId);
    compactDragRef.current = {
      down: true,
      startX: event.clientX,
      startY: event.clientY,
      started: false,
    };
  };

  const onCompactPointerMove = (event: React.PointerEvent<HTMLDivElement>) => {
    const s = compactDragRef.current;
    if (!s.down || s.started) {
      return;
    }
    const dx = event.clientX - s.startX;
    const dy = event.clientY - s.startY;
    if (dx * dx + dy * dy >= COMPACT_DRAG_SQ_THRESHOLD) {
      s.started = true;
      void getCurrentWindow().startDragging().catch((error) => {
        console.error("companion compact startDragging failed:", error);
      });
    }
  };

  const resetCompactDrag = (
    target: HTMLDivElement,
    event: React.PointerEvent<HTMLDivElement>,
  ) => {
    if (compactDragRef.current.down) {
      try {
        target.releasePointerCapture(event.pointerId);
      } catch {
        /* capture already released after OS drag */
      }
    }
    compactDragRef.current = {
      down: false,
      startX: 0,
      startY: 0,
      started: false,
    };
  };

  const onCompactPointerUp = (event: React.PointerEvent<HTMLDivElement>) => {
    resetCompactDrag(event.currentTarget, event);
  };

  const onCompactPointerCancel = (event: React.PointerEvent<HTMLDivElement>) => {
    resetCompactDrag(event.currentTarget, event);
  };

  return (
    <div
      role="button"
      tabIndex={0}
      className={cn(
        "hermes-titlebar-nodrag flex h-screen w-screen cursor-pointer touch-manipulation select-none items-center justify-center overflow-visible",
        "rounded-none border-0 bg-transparent shadow-none outline-none focus:outline-none focus-visible:outline-none",
        menuOpen && "items-end justify-start px-3 pb-2",
      )}
      aria-label={
        locale === "zh"
          ? "卡布奇娜小娜：双击打开主窗口，拖拽可移动"
          : "Kabuqina Nana: double-click to open main window, drag to move"
      }
      title={
        locale === "zh"
          ? "拖拽移动 · 双击打开主窗口"
          : "Drag to move · Double-click to open main window"
      }
      onPointerDown={onCompactPointerDown}
      onPointerMove={onCompactPointerMove}
      onPointerUp={onCompactPointerUp}
      onPointerCancel={onCompactPointerCancel}
      onContextMenu={openCompanionMenu}
      onLostPointerCapture={() => {
        compactDragRef.current = {
          down: false,
          startX: 0,
          startY: 0,
          started: false,
        };
      }}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          openMain();
        }
      }}
      onDoubleClick={openMain}
    >
      <CompanionPillScene className="pointer-events-none" />
      {menuOpen ? (
        <div
          className="kq-companion-context-menu hermes-titlebar-nodrag"
          role="menu"
          onClick={(event) => event.stopPropagation()}
          onPointerDown={(event) => event.stopPropagation()}
          onPointerMove={(event) => event.stopPropagation()}
          onPointerUp={(event) => event.stopPropagation()}
          onContextMenu={(event) => event.preventDefault()}
        >
          <button
            type="button"
            className="kq-companion-context-close"
            onClick={closeCompanionMenu}
            aria-label={locale === "zh" ? "关闭" : "Close"}
          >
            <X className="h-3.5 w-3.5" aria-hidden />
          </button>
          <p className="kq-companion-context-spec">{t("settings.companionImageSpec")}</p>
          {imageError ? <p className="kq-companion-context-error">{imageError}</p> : null}
          <input
            ref={fileInputRef}
            type="file"
            accept="image/png,image/webp,image/svg+xml"
            className="hidden"
            onChange={(event) => handleCompanionImagePicked(event.currentTarget.files?.[0])}
          />
          <div className="kq-companion-context-actions">
            <button
              type="button"
              className="kq-companion-context-primary"
              onClick={() => fileInputRef.current?.click()}
            >
              {t("settings.companionImageReplace")}
            </button>
            <button
              type="button"
              className="kq-companion-context-secondary"
              onClick={resetCompanionImage}
            >
              {t("settings.companionImageReset")}
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
