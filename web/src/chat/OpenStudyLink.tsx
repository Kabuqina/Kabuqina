// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { BookOpen } from "lucide-react";
import { Link } from "react-router-dom";
import { useI18n } from "../lib/i18n";

export function OpenStudyLink() {
  const { t } = useI18n();
  return (
    <Link className="kq-open-study-link" to="/study">
      <BookOpen aria-hidden />
      <span>{t("study.openCurrentSpace")}</span>
    </Link>
  );
}
