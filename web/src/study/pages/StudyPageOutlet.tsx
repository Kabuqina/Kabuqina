// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import type { StudyPageSlug } from "../routeModel";
import { EvaluatePage } from "./EvaluatePage";
import { FlyleafPage } from "./FlyleafPage";
import { PlanPage } from "./PlanPage";
import { PracticePage } from "./PracticePage";
import { PlaceholderPage } from "./PlaceholderPage";

export function StudyPageOutlet({ spaceId, page, onPracticeDirtyChange, onPracticeNavigateAway }: { spaceId: string; page: StudyPageSlug; onPracticeDirtyChange?: (dirty: boolean) => void; onPracticeNavigateAway?: (to: string) => void }) {
  if (page === "flyleaf") return <FlyleafPage spaceId={spaceId} />;
  if (page === "plan") return <PlanPage spaceId={spaceId} />;
  if (page === "evaluate") return <EvaluatePage spaceId={spaceId} />;
  if (page === "practice") return <PracticePage key={spaceId} spaceId={spaceId} onDirtyChange={onPracticeDirtyChange} onNavigateAway={onPracticeNavigateAway} />;
  return <PlaceholderPage page={page} />;
}
