// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { NavLink } from "react-router-dom";
import { useI18n } from "../lib/i18n";
import { PAGE_SLUGS, studyPath, type StudyPageSlug } from "./routeModel";

const PAGE_KEYS: Record<StudyPageSlug, string> = {
  flyleaf: "study.pageFlyleaf",
  plan: "study.pagePlan",
  learn: "study.pageLearn",
  practice: "study.pagePractice",
  evaluate: "study.pageEvaluate",
};

export function pageLabelKey(page: StudyPageSlug): string {
  return PAGE_KEYS[page];
}

export function StudyLifecycleNav({ spaceId }: { spaceId: string }) {
  const { t } = useI18n();
  return (
    <nav className="kq-study-lifecycle" aria-label={t("study.lifecycle")}>
      {PAGE_SLUGS.map((page) => (
        <NavLink
          key={page}
          to={studyPath(spaceId, page)}
          className={({ isActive }) => `kq-study-lifecycle-link${isActive ? " is-active" : ""}`}
        >
          {t(PAGE_KEYS[page])}
        </NavLink>
      ))}
    </nav>
  );
}
