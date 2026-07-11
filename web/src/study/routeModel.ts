// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

export const PAGE_SLUGS = ["flyleaf", "plan", "learn", "practice", "evaluate"] as const;
export type StudyPageSlug = (typeof PAGE_SLUGS)[number];

export type StudyRouteModel =
  | { kind: "root" }
  | { kind: "space"; spaceId: string }
  | { kind: "page"; spaceId: string; page: StudyPageSlug }
  | { kind: "not-found"; spaceId?: string };

function isPageSlug(value: string): value is StudyPageSlug {
  return PAGE_SLUGS.includes(value as StudyPageSlug);
}

// A hand-typed URL can carry a malformed percent-escape (e.g. /study/100%);
// there is no error boundary above StudyRoute, so decoding must never throw.
function safeDecode(segment: string): string | null {
  try {
    return decodeURIComponent(segment);
  } catch {
    return null;
  }
}

export function parseStudyPath(pathname: string): StudyRouteModel {
  const parts = pathname.split("/").filter(Boolean);
  if (parts[0] !== "study" || parts.length > 3) return { kind: "not-found" };
  if (parts.length === 1) return { kind: "root" };
  const spaceId = safeDecode(parts[1]);
  if (!spaceId) return { kind: "not-found" };
  if (parts.length === 2) return { kind: "space", spaceId };
  return isPageSlug(parts[2])
    ? { kind: "page", spaceId, page: parts[2] }
    : { kind: "not-found", spaceId };
}

export function studyPath(spaceId: string, page: StudyPageSlug = "flyleaf"): string {
  return `/study/${encodeURIComponent(spaceId)}/${page}`;
}
