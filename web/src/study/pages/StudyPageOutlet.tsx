// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import type { StudyPageSlug } from "../routeModel";
import { EvaluatePage } from "./EvaluatePage";
import { FlyleafPage } from "./FlyleafPage";
import { PlanPage } from "./PlanPage";
import { PlaceholderPage } from "./PlaceholderPage";

export function StudyPageOutlet({ spaceId, page }: { spaceId: string; page: StudyPageSlug }) {
  if (page === "flyleaf") return <FlyleafPage spaceId={spaceId} />;
  if (page === "plan") return <PlanPage spaceId={spaceId} />;
  if (page === "evaluate") return <EvaluatePage spaceId={spaceId} />;
  return <PlaceholderPage page={page} />;
}
