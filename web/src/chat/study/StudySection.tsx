// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

// STUDY module — the student learning-planning quick actions in the ACADEMY
// workspace panel, parallel to the report/PPT and math sections. Three ordered
// steps that build on each other: learning profile -> learning path ->
// learning resource pack. Each button injects a bounded, crafted prompt (see
// ./studyPrompts); the module owns nothing else, so new study actions are a
// one-line addition to STUDY_ACTIONS.

import { Layers3, Route, UserRoundCog, type LucideIcon } from "lucide-react";

import { useI18n } from "../../lib/i18n";
import { WorkspaceActionButton, WorkspaceSection } from "../workspaceSection";
import { STUDY_PROMPTS, type StudyActionId } from "./studyPrompts";

type StudyAction = {
  id: StudyActionId;
  icon: LucideIcon;
  labelKey: string;
  prompt: string;
};

const STUDY_ACTIONS: StudyAction[] = [
  {
    id: "learningProfile",
    icon: UserRoundCog,
    labelKey: "chat.workspaceBuildLearningProfile",
    prompt: STUDY_PROMPTS.learningProfile,
  },
  {
    id: "learningPath",
    icon: Route,
    labelKey: "chat.workspaceBuildLearningPath",
    prompt: STUDY_PROMPTS.learningPath,
  },
  {
    id: "learningResources",
    icon: Layers3,
    labelKey: "chat.workspaceBuildResourcePack",
    prompt: STUDY_PROMPTS.learningResources,
  },
];

export function StudySection({
  onStartPrompt,
}: {
  onStartPrompt?: (prompt: string) => void;
}) {
  const { t } = useI18n();
  return (
    <WorkspaceSection
      sectionId="workspace.study"
      title={t("chat.workspaceStudy")}
      dotColor="#2f9e8f"
    >
      <div className="mt-3 grid grid-cols-1 gap-2">
        {STUDY_ACTIONS.map((action) => {
          const Icon = action.icon;
          return (
            <WorkspaceActionButton
              key={action.id}
              onClick={() => onStartPrompt?.(action.prompt)}
              icon={<Icon className="kq-color-icon-course mr-2 inline h-4 w-4" aria-hidden />}
              label={t(action.labelKey)}
            />
          );
        })}
      </div>
    </WorkspaceSection>
  );
}
