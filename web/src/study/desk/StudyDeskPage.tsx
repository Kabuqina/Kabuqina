// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useMemo } from "react";
import { useStudyRepository } from "../repositoryContext";
import { studyPath, type StudyPageSlug } from "../routeModel";
import type { StudySpaceSummary } from "../repository";
import DeskScene from "./DeskScene";
import { createStudyDeskAdapter } from "./studyDeskAdapter";

export function StudyDeskPage({
  spaceId,
  spaces,
  onDirtyChange,
  onNavigateAway,
  onSelectSpace,
}: {
  spaceId: string;
  spaces: StudySpaceSummary[];
  onDirtyChange: (dirty: boolean) => void;
  onNavigateAway: (to: string) => void;
  onSelectSpace: (spaceId: string) => void;
}) {
  const repository = useStudyRepository();
  const spacesKey = JSON.stringify(spaces);
  const adapter = useMemo(
    () => createStudyDeskAdapter({
      repository,
      spaceId,
      spaces: JSON.parse(spacesKey) as StudySpaceSummary[],
    }),
    [repository, spaceId, spacesKey],
  );
  const navigatePage = (page: StudyPageSlug) => onNavigateAway(studyPath(spaceId, page));

  return (
    <DeskScene
      adapter={adapter}
      currentPage="practice"
      onDirtyChange={onDirtyChange}
      onNavigatePage={navigatePage}
      onOpenChat={() => onNavigateAway("/chat")}
      onOpenActivity={() => navigatePage("evaluate")}
      onOpenSettings={() => onNavigateAway("/settings")}
      onSelectSpace={onSelectSpace}
      onOpenMaterials={() => navigatePage("learn")}
      onNewBook={() => onNavigateAway("/chat")}
    />
  );
}
