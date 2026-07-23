// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

// Replaceable icon seam. The frozen prototype uses Lucide's 2px stroke
// language, and the production app already depends on lucide-react. Keeping
// the mapping here lets later art passes replace individual icons without
// coupling scene components to a particular icon package.

import {
  Archive,
  ArrowRight,
  BookOpen,
  Bookmark,
  Check,
  Circle,
  CircleCheck,
  CircleDot,
  Coffee,
  FolderPlus,
  Layers,
  Library,
  Plus,
  Settings,
  type LucideIcon,
} from "lucide-react";

export type DeskIcon = LucideIcon;

export interface DeskArtAssets {
  bookmark: DeskIcon;
  archive: DeskIcon;
  library: DeskIcon;
  layers: DeskIcon;
  plus: DeskIcon;
  book: DeskIcon;
  check: DeskIcon;
  circle: DeskIcon;
  arrowRight: DeskIcon;
  coffee: DeskIcon;
  folderPlus: DeskIcon;
  settings: DeskIcon;
  circleCheck: DeskIcon;
  circleDot: DeskIcon;
}

/** Default glyphs match the frozen prototype's Lucide icon language. */
export const defaultDeskArtAssets: DeskArtAssets = {
  bookmark: Bookmark,
  archive: Archive,
  library: Library,
  layers: Layers,
  plus: Plus,
  book: BookOpen,
  check: Check,
  circle: Circle,
  arrowRight: ArrowRight,
  coffee: Coffee,
  folderPlus: FolderPlus,
  settings: Settings,
  circleCheck: CircleCheck,
  circleDot: CircleDot,
};
