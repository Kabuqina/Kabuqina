// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useEffect, useRef } from "react";
import { Link } from "react-router-dom";
import { useI18n } from "../../lib/i18n";
import { pageLabelKey } from "../StudyLifecycleNav";
import type { StudyPageSlug } from "../routeModel";

export function PlaceholderPage({ page }: { page: StudyPageSlug }) {
  const { t } = useI18n();
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => heading.current?.focus(), [page]);
  return (
    <section className="kq-study-placeholder" aria-labelledby="study-page-title">
      <p className="kq-study-placeholder-kicker">{t("study.lifecycle")}</p>
      <h1 id="study-page-title" ref={heading} tabIndex={-1}>{t(pageLabelKey(page))}</h1>
      <p>{t("study.pageComing")}</p>
      <Link className="kq-study-secondary-link" to="/chat">{t("study.openLegacyStudy")}</Link>
    </section>
  );
}
