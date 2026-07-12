// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

// STUDY module — learning-agent quick actions in the STUDY workspace panel.
// Each button injects a bounded, crafted prompt (see ./studyPrompts); the
// module owns nothing else, so new study actions are a one-line addition to
// STUDY_ACTIONS.

import {
  BookMarked,
  Layers3,
  MessagesSquare,
  ShieldCheck,
  SquareArrowOutUpRight,
  type LucideIcon,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";

import { useI18n } from "../../lib/i18n";
import { WorkspaceActionButton, WorkspaceSection } from "../workspaceSection";
import { cmdStudyMigrateBuiltinCourse } from "./study-api";
import { STUDY_LEARNING_EVENT } from "./flashcardLearningStore";
import { STUDY_PROMPTS, type StudyActionId } from "./studyPrompts";
import {
  STUDY_CONTEXT_EVENT,
  emptyStudyContext,
  formatStudyContextForPrompt,
  loadStudyContext,
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
    };
    sync();
    window.addEventListener("storage", sync);
    window.addEventListener(STUDY_CONTEXT_EVENT, sync);
    return () => {
      window.removeEventListener("storage", sync);
      window.removeEventListener(STUDY_CONTEXT_EVENT, sync);
    };
  }, []);

  const startAction = (prompt: string) => {
    const contextPrompt = formatStudyContextForPrompt(context);
    onStartPrompt?.([contextPrompt, prompt].filter(Boolean).join("\n\n"));
  };

  const fields: Array<{ key: keyof StudyContext; label: string }> = [
    {
      key: "course",
      label: t("chat.studyContextCourse"),
    },
    {
      key: "goal",
      label: t("chat.studyContextGoal"),
    },
    {
      key: "profileSummary",
      label: t("chat.studyContextProfile"),
    },
    {
      key: "preferences",
      label: t("chat.studyContextPreferences"),
    },
    {
      key: "progressNotes",
      label: t("chat.studyContextProgress"),
    },
    {
      key: "currentStage",
      label: t("chat.studyContextStage"),
    },
  ];

  const summaryRows = fields
    .filter((field) => STUDY_PROFILE_SUMMARY_KEYS.includes(field.key))
    .map((field) => ({ label: field.label, value: context[field.key].trim() }))
    .filter((row) => row.value.length > 0)
    .slice(0, 4);

  return (
    <>
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
            <Link
              to="/study"
              className="kq-soft-icon-btn inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-md transition"
              aria-label={t("study.openCurrentSpace")}
              title={t("study.openCurrentSpace")}
            >
              <SquareArrowOutUpRight className="h-3.5 w-3.5" aria-hidden />
            </Link>
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

      <OpenPracticeCard onAskNana={() => startAction(STUDY_PROMPTS.learningTutor)} />
    </>
  );
}

function OpenPracticeCard({ onAskNana }: { onAskNana: () => void }) {
  const { t } = useI18n();
  return (
    <WorkspaceSection sectionId="workspace.practice" title={t("study.pagePractice")} dotColor="#2f9e8f">
      <p className="mt-2 text-[12px] leading-snug text-[var(--kq-color-muted)]">
        {t("study.practiceSidebarHandoff")}
      </p>
      <div className="mt-3 grid grid-cols-1 gap-2">
        <Link
          to="/study"
          className="kq-quick-action justify-start rounded-[10px] px-2.5 py-2 text-left text-[13px] leading-snug transition"
        >
          <SquareArrowOutUpRight className="kq-color-icon-course mr-2 inline h-4 w-4" aria-hidden />
          {t("study.openCurrentSpace")}
        </Link>
        <WorkspaceActionButton
          onClick={onAskNana}
          icon={<MessagesSquare className="kq-color-icon-course mr-2 inline h-4 w-4" aria-hidden />}
          label={t("study.practiceAskNana")}
        />
      </div>
    </WorkspaceSection>
  );
}
