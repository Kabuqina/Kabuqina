// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useCallback, useEffect, useMemo, useState } from "react";
import { isWorkbenchNarrow } from "./workbenchLayoutLogic";

export const WORKBENCH_LAYOUT_KEY = "kabuqina.workbench.layout";

/** Right workspace panel width bounds (px). */
export const RIGHT_PANEL_MIN_WIDTH = 240;
export const RIGHT_PANEL_MAX_WIDTH = 680;
export const RIGHT_PANEL_DEFAULT_WIDTH = 264;

function clampRightWidth(value: number): number {
  if (!Number.isFinite(value)) return RIGHT_PANEL_DEFAULT_WIDTH;
  return Math.max(RIGHT_PANEL_MIN_WIDTH, Math.min(RIGHT_PANEL_MAX_WIDTH, Math.round(value)));
}

type StoredWorkbenchLayout = {
  leftOpen?: boolean;
  rightOpen?: boolean;
  focusMode?: boolean;
  rightWidth?: number;
};

export type WorkbenchLayout = {
  leftOpen: boolean;
  rightOpen: boolean;
  focusMode: boolean;
  isNarrow: boolean;
  showLeftRail: boolean;
  showRightPanel: boolean;
  rightWidth: number;
  toggleLeft: () => void;
  toggleRight: () => void;
  toggleFocusMode: () => void;
  setRightWidth: (width: number) => void;
};

function readStoredLayout(): StoredWorkbenchLayout {
  if (typeof window === "undefined") return {};
  try {
    const raw = window.localStorage.getItem(WORKBENCH_LAYOUT_KEY);
    return raw ? JSON.parse(raw) : {};
  } catch {
    return {};
  }
}

function writeStoredLayout(layout: StoredWorkbenchLayout): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(WORKBENCH_LAYOUT_KEY, JSON.stringify(layout));
  } catch {
    /* localStorage can be unavailable in restricted webviews */
  }
}

export function useWorkbenchLayout(): WorkbenchLayout {
  const stored = useMemo(readStoredLayout, []);
  const [leftOpen, setLeftOpen] = useState(stored.leftOpen ?? true);
  const [rightOpen, setRightOpen] = useState(stored.rightOpen ?? true);
  const [focusMode, setFocusMode] = useState(stored.focusMode ?? false);
  const [isNarrow, setIsNarrow] = useState(false);
  const [rightWidth, setRightWidthState] = useState(() =>
    clampRightWidth(stored.rightWidth ?? RIGHT_PANEL_DEFAULT_WIDTH),
  );

  useEffect(() => {
    const update = () => setIsNarrow(isWorkbenchNarrow(window.innerWidth));
    update();
    window.addEventListener("resize", update);
    return () => window.removeEventListener("resize", update);
  }, []);

  useEffect(() => {
    writeStoredLayout({ leftOpen, rightOpen, focusMode, rightWidth });
  }, [leftOpen, rightOpen, focusMode, rightWidth]);

  const setRightWidth = useCallback((width: number) => {
    setRightWidthState(clampRightWidth(width));
  }, []);

  const toggleLeft = useCallback(() => {
    setFocusMode(false);
    setLeftOpen((value) => !value);
  }, []);

  const toggleRight = useCallback(() => {
    setFocusMode(false);
    setRightOpen((value) => !value);
  }, []);

  const toggleFocusMode = useCallback(() => {
    setFocusMode((value) => !value);
  }, []);

  return {
    leftOpen,
    rightOpen,
    focusMode,
    isNarrow,
    showLeftRail: !focusMode && (leftOpen || isNarrow),
    showRightPanel: !focusMode && rightOpen && !isNarrow,
    rightWidth,
    toggleLeft,
    toggleRight,
    toggleFocusMode,
    setRightWidth,
  };
}
