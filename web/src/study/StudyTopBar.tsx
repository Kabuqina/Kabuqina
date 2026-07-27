// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { ArrowLeft, MessageCircle } from "lucide-react";
import { Link } from "react-router-dom";
import { useI18n } from "../lib/i18n";
import type { StudySpaceSummary } from "./repository";
import { DraftInboxButton } from "./DraftInboxButton";
import { SpaceSwitcher } from "./SpaceSwitcher";

export function StudyTopBar(props: {
  spaces: StudySpaceSummary[];
  currentSpaceId: string;
  switching: boolean;
  switchError: boolean;
  onSelectSpace: (spaceId: string) => void;
  onNavigateAway?: (to: string) => void;
}) {
  const { t } = useI18n();
  return (
    <header className="kq-study-topbar">
      <Link className="kq-study-icon-link" to="/chat" aria-label={t("study.backToChat")} onClick={(event) => { if (props.onNavigateAway) { event.preventDefault(); props.onNavigateAway("/chat"); } }}><ArrowLeft aria-hidden /></Link>
      <SpaceSwitcher
        spaces={props.spaces}
        currentSpaceId={props.currentSpaceId}
        pending={props.switching}
        error={props.switchError}
        onSelect={props.onSelectSpace}
        onNavigateAway={props.onNavigateAway}
      />
      <div className="kq-study-topbar-actions">
        <DraftInboxButton />
        <Link className="kq-study-top-action" to="/chat" onClick={(event) => { if (props.onNavigateAway) { event.preventDefault(); props.onNavigateAway("/chat"); } }}><MessageCircle aria-hidden /><span>{t("study.askNana")}</span></Link>
      </div>
    </header>
  );
}
