// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

// STUDY module — learning-agent quick actions in the STUDY workspace panel.
// Each button injects a bounded, crafted prompt (see ./studyPrompts); the
// module owns nothing else, so new study actions are a one-line addition to
// STUDY_ACTIONS.

import {
  BookMarked,
  Eraser,
  Layers3,
  MessagesSquare,
  PencilLine,
  Save,
  ShieldCheck,
  type LucideIcon,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { useI18n } from "../../lib/i18n";
import { ShellModal } from "../../components/ShellModal";
import { WorkspaceActionButton, WorkspaceSection } from "../workspaceSection";
import { cmdStudyMigrateBuiltinCourse } from "./study-api";
import { STUDY_LEARNING_EVENT } from "./flashcardLearningStore";
import { EvaluationPanel } from "./EvaluationPanel";
import { FlashcardPanel } from "./FlashcardPanel";
import { LearningPathPanel } from "./LearningPathPanel";
import { QuizPanel } from "./QuizPanel";
import { ProfilePanel } from "./ProfilePanel";
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
  // 「构建学习画像」已由顶部「学习画像（6 维）」面板承载，此处不再重复。
  // 「学习路径」已由专属面板承载，此处不再重复。
  // 「学习效果评估」已由专属面板承载，此处不再重复。
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
    id: "contentSafetyReview",
    icon: ShieldCheck,
    labelKey: "chat.workspaceReviewStudyContent",
    prompt: STUDY_PROMPTS.contentSafetyReview,
  },
];

const STUDY_PROFILE_SUMMARY_KEYS: Array<keyof StudyContext> = [
  "course",
  "goal",
  "profileSummary",
  "weakPoints",
  "currentStage",
  "preferences",
  "progressNotes",
];

export function StudySection({
  onStartPrompt,
}: {
  onStartPrompt?: (prompt: string) => void;
}) {
  const { t } = useI18n();
  const [context, setContext] = useState<StudyContext>(emptyStudyContext);
  const [saveStatus, setSaveStatus] = useState<"idle" | "saved" | "failed">("idle");
  const [profileEditorOpen, setProfileEditorOpen] = useState(false);
  const builtinSeededRef = useRef(false);

  // Seed the built-in course once per session mount. The backend is idempotent
  // (guarded by a migration key), so this is a no-op after the first install.
  // On a fresh seed, notify the flashcard/quiz panels to refresh.
  useEffect(() => {
    if (builtinSeededRef.current) return;
    builtinSeededRef.current = true;
    void cmdStudyMigrateBuiltinCourse()
      .then((res) => {
        if (res?.seeded) window.dispatchEvent(new Event(STUDY_LEARNING_EVENT));
      })
      .catch((error) => console.debug("builtin course seed failed:", error));
  }, []);

  useEffect(() => {
    const sync = () => {
      setContext(loadStudyContext());
      setSaveStatus("idle");
    };
    sync();
    window.addEventListener("storage", sync);
    window.addEventListener(STUDY_CONTEXT_EVENT, sync);
    return () => {
      window.removeEventListener("storage", sync);
      window.removeEventListener(STUDY_CONTEXT_EVENT, sync);
    };
  }, []);

  const updateContext = (key: keyof StudyContext, value: string) => {
    setSaveStatus("idle");
    setContext((current) => ({ ...current, [key]: value }));
  };

  const persistContext = () => {
    const result = saveStudyContext(context);
    setContext(result.context);
    setSaveStatus(result.succeeded ? "saved" : "failed");
  };

  const resetContext = () => {
    const result = clearStudyContext();
    if (result.succeeded) setContext(result.context);
    setSaveStatus(result.succeeded ? "idle" : "failed");
  };

  const startAction = (prompt: string) => {
    const result = saveStudyContext(context);
    setContext(result.context);
    setSaveStatus(result.succeeded ? "saved" : "failed");
    const contextPrompt = formatStudyContextForPrompt(result.context);
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

  const summaryRows = fields
    .filter((field) => STUDY_PROFILE_SUMMARY_KEYS.includes(field.key))
    .map((field) => ({ label: field.label, value: context[field.key].trim() }))
    .filter((row) => row.value.length > 0)
    .slice(0, 4);

  return (
    <>
      <ProfilePanel onStartPrompt={onStartPrompt} />
      <LearningPathPanel onStartPrompt={onStartPrompt} />
      <EvaluationPanel onStartPrompt={onStartPrompt} />
      <WorkspaceSection
        sectionId="workspace.study"
        title={t("chat.workspaceStudy")}
        dotColor="#2f9e8f"
      >
        <div className="kq-study-profile-card mt-3 rounded-lg border border-[var(--kq-color-border)] bg-white/55 p-3 text-[12px] leading-snug shadow-[0_10px_24px_rgba(90,74,106,0.07)] dark:bg-white/[0.04]">
          <div className="flex items-center justify-between gap-2">
            <div className="min-w-0">
              <div className="text-[13px] font-semibold text-[var(--kq-color-strong)]">
                {t("chat.studyContextCardTitle")}
              </div>
            </div>
            <button
              type="button"
              onClick={() => setProfileEditorOpen(true)}
              className="kq-soft-icon-btn inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-md transition"
              aria-label={t("chat.studyContextEdit")}
              title={t("chat.studyContextEdit")}
            >
              <PencilLine className="h-3.5 w-3.5" aria-hidden />
            </button>
          </div>
          {summaryRows.length > 0 ? (
            <div className="mt-2 grid gap-1.5">
              {summaryRows.map((row) => (
                <div key={row.label} className="min-w-0 rounded-md bg-[var(--kq-hover-bg)] px-2 py-1">
                  <span className="mr-1 font-medium text-[var(--kq-color-muted)]">{row.label}</span>
                  <span className="text-[var(--kq-color-ink)]">{row.value}</span>
                </div>
              ))}
            </div>
          ) : (
            <p className="mt-2 text-[11px] text-[var(--kq-color-muted)]">
              {t("chat.studyContextEmpty")}
            </p>
          )}
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

      <ShellModal
        open={profileEditorOpen}
        title={t("chat.studyContextCardTitle")}
        onClose={() => setProfileEditorOpen(false)}
        size="lg"
      >
        <div className="grid grid-cols-1 gap-3">
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
          <div className="flex items-center justify-end gap-2 pt-1">
            <button
              type="button"
              onClick={resetContext}
              className="kq-soft-icon-btn inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-md transition"
              aria-label={t("chat.studyContextClear")}
              title={t("chat.studyContextClear")}
            >
              <Eraser className="h-3.5 w-3.5" aria-hidden />
            </button>
            <button
              type="button"
              onClick={() => setProfileEditorOpen(false)}
              className="rounded-lg px-3 py-2 text-sm text-[var(--kq-color-ink)]"
            >
              {t("chat.studyContextClose")}
            </button>
            <button
              type="button"
              onClick={persistContext}
              className="kq-quick-action inline-flex items-center justify-center gap-1.5 rounded-[10px] px-3 py-2 text-sm leading-snug transition"
            >
              <Save className="h-3.5 w-3.5" aria-hidden />
              {saveStatus === "saved"
                ? t("chat.studyContextSaved")
                : saveStatus === "failed"
                  ? t("chat.studyContextSaveFailed")
                  : t("chat.studyContextSave")}
            </button>
          </div>
        </div>
      </ShellModal>

      <FlashcardPanel onStartPrompt={onStartPrompt} />
      <QuizPanel onStartPrompt={onStartPrompt} />
    </>
  );
}
