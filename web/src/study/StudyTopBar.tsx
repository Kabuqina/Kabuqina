// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { FilePlus2 } from "lucide-react";
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
  onImport: () => void;
}) {
  const { t } = useI18n();
  return (
    <header className="kq-study-topbar">
      {/* 去 Chat 与去 Studio 都在全局页眉上（架构 §5.1）；这条只留课程本自己的东西。 */}
      <SpaceSwitcher
        spaces={props.spaces}
        currentSpaceId={props.currentSpaceId}
        pending={props.switching}
        error={props.switchError}
        onSelect={props.onSelectSpace}
        onNavigateAway={props.onNavigateAway}
      />
      <div className="kq-study-topbar-actions">
        {/* 学生自己导入是默认路径（架构 §2.1.1），所以入口常驻而不是藏在菜单里。 */}
        <button type="button" className="kq-study-top-action" onClick={props.onImport}>
          <FilePlus2 aria-hidden />
          <span>{t("study.importPick")}</span>
        </button>
        <DraftInboxButton />
      </div>
    </header>
  );
}
