// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import type { StudyArtifact } from "./study-api";

function artifactTimestamp(artifact: StudyArtifact): number {
  const updated = Date.parse(artifact.updated_at || "");
  if (Number.isFinite(updated)) return updated;
  const created = Date.parse(artifact.created_at || "");
  return Number.isFinite(created) ? created : 0;
}

/**
 * Select the latest server snapshot, regardless of review status.
 *
 * A newly generated update is a draft while the previous snapshot remains
 * active. Preferring any active artifact would therefore hide the update and
 * make profile/path/evaluation refreshes appear broken.
 */
export function pickCurrentStudyArtifact(items: StudyArtifact[]): StudyArtifact | null {
  if (!Array.isArray(items) || items.length === 0) return null;
  return items.reduce((latest, candidate) => {
    const delta = artifactTimestamp(candidate) - artifactTimestamp(latest);
    if (delta > 0) return candidate;
    if (delta < 0) return latest;
    const versionDelta = Number(candidate.version || 0) - Number(latest.version || 0);
    return versionDelta > 0 ? candidate : latest;
  });
}
