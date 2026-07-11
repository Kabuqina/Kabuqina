// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import type { StudySpaces } from "./repository";
import type { StudyPageSlug } from "./routeModel";

/** D-1 route scaffold; Task 4 fills the visual shell without changing route semantics. */
export function StudyShell({ spaces, spaceId, page }: {
  spaces: StudySpaces;
  spaceId?: string;
  page?: StudyPageSlug;
}) {
  const current = spaces.spaces.find((space) => space.id === spaceId);
  return (
    <main data-testid="study-shell">
      <h1 tabIndex={-1}>{current?.title ?? "Study"}</h1>
      {page ? <p>{page}</p> : <p>No study space yet.</p>}
    </main>
  );
}
