// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

// STUDY module — learning-agent quick actions in the STUDY workspace panel.
// Each button injects a bounded, crafted prompt (see ./studyPrompts); the
// module owns nothing else, so new study actions are a one-line addition to
// STUDY_ACTIONS.

import {
  BookMarked,
  ClipboardCheck,
  Eraser,
  Layers3,
  MessagesSquare,
  Route,
  Save,
  ShieldCheck,
  UserRoundCog,
  type LucideIcon,
} from "lucide-react";
import { useEffect, useState } from "react";

import { useI18n } from "../../lib/i18n";
import { WorkspaceActionButton, WorkspaceSection } from "../workspaceSection";
import { STUDY_PROMPTS, type StudyActionId } from "./studyPrompts";
import {
  STUDY_CONTEXT_EVENT,
  clearStudyContext,
  emptyStudyContext,
  formatStudyContextForPrompt,
  loadStudyContext,
  saveStudyContext,
  type StudyContext,
} from "./studyStore";

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
    id: "courseKnowledgeBase",
    icon: BookMarked,
    labelKey: "chat.workspaceBuildCourseKnowledgeBase",
    prompt: STUDY_PROMPTS.courseKnowledgeBase,
  },
  {
    id: "learningResources",
    icon: Layers3,
    labelKey: "chat.workspaceBuildResourcePack",
    prompt: STUDY_PROMPTS.learningResources,
  },
  {
    id: "learningTutor",
    icon: MessagesSquare,
    labelKey: "chat.workspaceStartLearningTutor",
    prompt: STUDY_PROMPTS.learningTutor,
  },
  {
    id: "learningEvaluation",
    icon: ClipboardCheck,
    labelKey: "chat.workspaceEvaluateLearningEffect",
    prompt: STUDY_PROMPTS.learningEvaluation,
  },
  {
    id: "contentSafetyReview",
    icon: ShieldCheck,
    labelKey: "chat.workspaceReviewStudyContent",
    prompt: STUDY_PROMPTS.contentSafetyReview,
  },
];

export function StudySection({
  onStartPrompt,
}: {
  onStartPrompt?: (prompt: string) => void;
}) {
  const { t } = useI18n();
  const [context, setContext] = useState<StudyContext>(emptyStudyContext);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    const sync = () => setContext(loadStudyContext());
    sync();
    window.addEventListener("storage", sync);
    window.addEventListener(STUDY_CONTEXT_EVENT, sync);
    return () => {
      window.removeEventListener("storage", sync);
      window.removeEventListener(STUDY_CONTEXT_EVENT, sync);
    };
  }, []);

  const updateContext = (key: keyof StudyContext, value: string) => {
    setSaved(false);
    setContext((current) => ({ ...current, [key]: value }));
  };

  const persistContext = () => {
    setContext(saveStudyContext(context));
    setSaved(true);
  };

  const resetContext = () => {
    setContext(clearStudyContext());
    setSaved(false);
  };

  const startAction = (prompt: string) => {
    const savedContext = saveStudyContext(context);
    setContext(savedContext);
    const contextPrompt = formatStudyContextForPrompt(savedContext);
    onStartPrompt?.([contextPrompt, prompt].filter(Boolean).join("\n\n"));
  };

  const fields: Array<{ key: keyof StudyContext; label: string; placeholder: string }> = [
    {
      key: "course",
      label: t("chat.studyContextCourse"),
      placeholder: t("chat.studyContextCoursePlaceholder"),
    },
    {
      key: "goal",
      label: t("chat.studyContextGoal"),
      placeholder: t("chat.studyContextGoalPlaceholder"),
    },
    {
      key: "profileSummary",
      label: t("chat.studyContextProfile"),
      placeholder: t("chat.studyContextProfilePlaceholder"),
    },
    {
      key: "weakPoints",
      label: t("chat.studyContextWeakPoints"),
      placeholder: t("chat.studyContextWeakPointsPlaceholder"),
    },
    {
      key: "preferences",
      label: t("chat.studyContextPreferences"),
      placeholder: t("chat.studyContextPreferencesPlaceholder"),
    },
    {
      key: "progressNotes",
      label: t("chat.studyContextProgress"),
      placeholder: t("chat.studyContextProgressPlaceholder"),
    },
    {
      key: "assessmentEvidence",
      label: t("chat.studyContextEvidence"),
      placeholder: t("chat.studyContextEvidencePlaceholder"),
    },
    {
      key: "currentStage",
      label: t("chat.studyContextStage"),
      placeholder: t("chat.studyContextStagePlaceholder"),
    },
    {
      key: "generatedResources",
      label: t("chat.studyContextResources"),
      placeholder: t("chat.studyContextResourcesPlaceholder"),
    },
    {
      key: "tutoringNotes",
      label: t("chat.studyContextTutoring"),
      placeholder: t("chat.studyContextTutoringPlaceholder"),
    },
    {
      key: "evaluationSummary",
      label: t("chat.studyContextEvaluationSummary"),
      placeholder: t("chat.studyContextEvaluationSummaryPlaceholder"),
    },
    {
      key: "nextAdjustment",
      label: t("chat.studyContextNextAdjustment"),
      placeholder: t("chat.studyContextNextAdjustmentPlaceholder"),
    },
  ];

  return (
    <WorkspaceSection
      sectionId="workspace.study"
      title={t("chat.workspaceStudy")}
      dotColor="#2f9e8f"
    >
      <div className="mt-3 grid grid-cols-1 gap-2">
        {fields.map((field) => (
          <label key={field.key} className="grid gap-1 text-[12px] leading-snug text-[var(--kq-color-muted)]">
            <span className="font-medium text-[var(--kq-color-ink)]">{field.label}</span>
            <textarea
              value={context[field.key]}
              onChange={(event) => updateContext(field.key, event.currentTarget.value)}
              placeholder={field.placeholder}
              rows={field.key === "profileSummary" ? 3 : 2}
              className="kq-workspace-select min-h-[38px] resize-none rounded-md px-2 py-1.5 text-[12.5px] leading-snug text-[var(--kq-color-ink)] transition"
            />
          </label>
        ))}
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={persistContext}
            className="kq-quick-action inline-flex flex-1 items-center justify-center gap-1.5 rounded-[10px] px-2.5 py-2 text-[12.5px] leading-snug transition"
          >
            <Save className="h-3.5 w-3.5" aria-hidden />
            {saved ? t("chat.studyContextSaved") : t("chat.studyContextSave")}
          </button>
          <button
            type="button"
            onClick={resetContext}
            className="kq-soft-icon-btn inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-md transition"
            aria-label={t("chat.studyContextClear")}
            title={t("chat.studyContextClear")}
          >
            <Eraser className="h-3.5 w-3.5" aria-hidden />
          </button>
        </div>
      </div>

      <div className="mt-3 grid grid-cols-1 gap-2">
        {STUDY_ACTIONS.map((action) => {
          const Icon = action.icon;
          return (
            <WorkspaceActionButton
              key={action.id}
              onClick={() => startAction(action.prompt)}
              icon={<Icon className="kq-color-icon-course mr-2 inline h-4 w-4" aria-hidden />}
              label={t(action.labelKey)}
            />
          );
        })}
      </div>
    </WorkspaceSection>
  );
}
