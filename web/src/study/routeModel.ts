// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

/** v0.5.0 canonical surfaces. The desk is no longer organized as five tabs. */
export const SURFACE_SLUGS = ["notebook", "cards", "bookend"] as const;
export type StudySurfaceSlug = (typeof SURFACE_SLUGS)[number];

/** Pre-v0.5.0 page slugs. These are kept for redirect compatibility during the migration. */
export const LEGACY_PAGE_SLUGS = ["flyleaf", "plan", "learn", "practice", "evaluate"] as const;
export type StudyLegacyPageSlug = (typeof LEGACY_PAGE_SLUGS)[number];

/** Transition union: any code still passing legacy slugs to `studyPath` will get the canonical URL. */
export type StudyPageSlug = StudySurfaceSlug | StudyLegacyPageSlug;

export type StudyRouteModel =
  | { kind: "root" }
  | { kind: "space"; spaceId: string }
  | { kind: "surface"; spaceId: string; surface: StudySurfaceSlug }
  | { kind: "legacy"; spaceId: string; page: StudyLegacyPageSlug }
  | { kind: "not-found"; spaceId?: string };

export function isSurfaceSlug(value: string): value is StudySurfaceSlug {
  return SURFACE_SLUGS.includes(value as StudySurfaceSlug);
}

export function isLegacyPageSlug(value: string): value is StudyLegacyPageSlug {
  return LEGACY_PAGE_SLUGS.includes(value as StudyLegacyPageSlug);
}

export function isStudyPageSlug(value: string): value is StudyPageSlug {
  return isSurfaceSlug(value) || isLegacyPageSlug(value);
}

/** Map a legacy page to its canonical surface + search params. */
export function legacyToCanonical(spaceId: string, page: StudyLegacyPageSlug): {
  pathname: string;
  search: string;
} {
  const base = `/study/${encodeURIComponent(spaceId)}`;
  switch (page) {
    case "flyleaf":
      return { pathname: `${base}/notebook`, search: "?view=flyleaf" };
    case "plan":
      return { pathname: `${base}/bookend`, search: "?view=plan" };
    case "learn":
      return { pathname: `${base}/notebook`, search: "?mode=learn" };
    case "practice":
      return { pathname: `${base}/notebook`, search: "?mode=practice" };
    case "evaluate":
      return { pathname: `${base}/bookend`, search: "?view=evaluate" };
  }
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
  const segment = parts[2];
  if (isSurfaceSlug(segment)) return { kind: "surface", spaceId, surface: segment };
  if (isLegacyPageSlug(segment)) return { kind: "legacy", spaceId, page: segment };
  return { kind: "not-found", spaceId };
}

/**
 * Build a canonical study URL.
 *
 * Passing a legacy page slug is supported as a migration aid: the returned path
 * will be the canonical surface with the equivalent search params. New code
 * should pass a `StudySurfaceSlug` directly.
 */
export function studyPath(
  spaceId: string,
  pageOrSurface: StudyPageSlug = "notebook",
  search?: string,
): string {
  if (isSurfaceSlug(pageOrSurface)) {
    return `/study/${encodeURIComponent(spaceId)}/${pageOrSurface}${search ?? ""}`;
  }
  const canonical = legacyToCanonical(spaceId, pageOrSurface);
  if (!search) return canonical.pathname + canonical.search;
  const separator = canonical.search ? "&" : "?";
  return `${canonical.pathname}${canonical.search}${separator}${search.slice(1)}`;
}
