// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useCallback, useEffect, useMemo, useState } from "react";

export const WORKBENCH_LAYOUT_KEY = "kabuqina.workbench.layout";

type StoredWorkbenchLayout = {
  leftOpen?: boolean;
  rightOpen?: boolean;
  focusMode?: boolean;
};

export type WorkbenchLayout = {
  leftOpen: boolean;
  rightOpen: boolean;
  focusMode: boolean;
  isNarrow: boolean;
  showLeftRail: boolean;
  showRightPanel: boolean;
  toggleLeft: () => void;
  toggleRight: () => void;
  toggleFocusMode: () => void;
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

  useEffect(() => {
    const update = () => setIsNarrow(window.innerWidth < 768);
    update();
    window.addEventListener("resize", update);
    return () => window.removeEventListener("resize", update);
  }, []);

  useEffect(() => {
    writeStoredLayout({ leftOpen, rightOpen, focusMode });
  }, [leftOpen, rightOpen, focusMode]);

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
    toggleLeft,
    toggleRight,
    toggleFocusMode,
  };
}
