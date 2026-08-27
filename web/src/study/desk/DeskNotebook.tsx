// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { lazy, Suspense, type ReactNode, type RefObject } from "react";
import type { StudyPageSlug, StudySurfaceSlug } from "../routeModel";
import type { DeskArtAssets } from "./artAssets";
import type {
  CheckResult,
  DeskDensity,
  DeskOverview,
  StudyActivity,
  StudyStep,
} from "./types";

const CodePracticeSurface = lazy(async () => ({
  default: (await import("../pages/CodePracticeSurface")).CodePracticeSurface,
}));
const DerivationPracticeSurface = lazy(async () => ({
  default: (await import("../pages/DerivationPracticeSurface")).DerivationPracticeSurface,
}));

export type NotebookMode = "learn" | "practice";

export interface DeskNotebookProps {
  art: DeskArtAssets;
  /** 练习专用；没有可用测验时缺席，本子仍然照常打开。 */
  overview?: DeskOverview;
  step?: StudyStep;
  density: DeskDensity;
  activity: StudyActivity;
  answer: string;
  saveStatusText: string;
  operationError: string | null;
  checkResult: CheckResult | null;
  currentPage?: StudyPageSlug;
  /** v0.5.0 canonical surface. */
  surface?: StudySurfaceSlug;
  /** Notebook work mode: learn or practice. */
  mode?: NotebookMode;
  /** Whether the flyleaf (first page) is open. */
  flyleafOpen?: boolean;
  /** Title shown on the notebook cover label. */
  spaceTitle?: string;
  /**
   * 非练习分页的正文。笔记本的五个分页共用同一本本子（原型 `StudyNotebook`）——
   * 扉页 / 计划 / 学习 / 评估 由 `StudyPageOutlet` 铺在这里，练习仍由本组件自己画，
   * 因为只有它带着作答面、检查反馈和小娜批注。
   */
  pageBody?: ReactNode;
  /** Right-page content: paper capture flow, empty state, or flyleaf back note. */
  rightPage?: ReactNode;
  continueTitle?: string;
  continueMeta?: string;
  continueLabel?: string;
  pageNotice?: string;
  knowledgeCoreTitle?: string;
  knowledgeCoreIndex?: number;
  knowledgeCoreTotal?: number;
  hasPreviousStep?: boolean;
  hasNextStep: boolean;
  taskSurfaceRef: RefObject<HTMLElement | null>;
  answerRef: RefObject<HTMLDivElement | null>;
  feedbackRef: RefObject<HTMLDivElement | null>;
  onResume: () => void;
  onStartWriting: () => void;
  onAnswerChange: (value: string) => void;
  onCheck: () => void;
  onSaveAnswer: () => void;
  onPreviousStep?: () => void;
  onNextStep: () => void;
  onPreviousKnowledgeCore?: () => void;
  onNextKnowledgeCore?: () => void;
  onBackToLearn?: () => void;
  onNavigatePage?: (page: StudyPageSlug) => void;
  onModeChange?: (mode: NotebookMode) => void;
  onToggleFlyleaf?: () => void;
  onFutureFeature: () => void;
}

function readChoice(answer: string): number[] {
  try {
    const parsed: unknown = JSON.parse(answer);
    return Array.isArray(parsed)
      ? parsed.filter((value): value is number => Number.isInteger(value))
      : [];
  } catch {
    return [];
  }
}

function readDerivation(answer: string): Record<string, {
  expr?: string;
  expr_py?: string;
  justification?: string;
}> {
  try {
    const parsed: unknown = JSON.parse(answer);
    return parsed && typeof parsed === "object" && !Array.isArray(parsed)
      ? parsed as Record<string, { expr?: string; expr_py?: string; justification?: string }>
      : {};
  } catch {
    return {};
  }
}

function AnswerSurface({
  step,
  answer,
  readOnly,
  answerRef,
  onAnswerChange,
}: {
  step: StudyStep;
  answer: string;
  readOnly: boolean;
  answerRef: RefObject<HTMLDivElement | null>;
  onAnswerChange: (value: string) => void;
}) {
  const kind = step.answerKind ?? "short_answer";
  if (kind === "choice") {
    const selected = readChoice(answer);
    return (
      <div ref={answerRef} className="kd-answer-surface kd-answer-options" aria-label="我的答案">
        {(step.options ?? []).map((option, index) => {
          const active = selected.includes(index);
          return (
            <button
              key={`${index}:${option}`}
              type="button"
              disabled={readOnly}
              aria-pressed={active}
              onClick={() => {
                const next = step.multiple
                  ? active
                    ? selected.filter((value) => value !== index)
                    : [...selected, index]
                  : [index];
                onAnswerChange(JSON.stringify(next));
              }}
            >
              <span aria-hidden="true">{String.fromCharCode(65 + index)}</span>
              {option}
            </button>
          );
        })}
      </div>
    );
  }

  if (kind === "true_false") {
    return (
      <div ref={answerRef} className="kd-answer-surface kd-answer-options kd-answer-binary" aria-label="我的答案">
        {[
          { value: "true", label: "正确" },
          { value: "false", label: "错误" },
        ].map((option) => (
          <button
            key={option.value}
            type="button"
            disabled={readOnly}
            aria-pressed={answer === option.value}
            onClick={() => onAnswerChange(option.value)}
          >
            {option.label}
          </button>
        ))}
      </div>
    );
  }

  if (kind === "code") {
    return (
      <div
        ref={answerRef}
        className="kd-answer-surface kd-answer-editor"
        aria-label="我的答案"
        aria-disabled={readOnly}
        data-readonly={readOnly || undefined}
      >
        <Suspense fallback={<p role="status">正在铺开代码纸…</p>}>
          <CodePracticeSurface
            starter={step.starter ?? ""}
            targetCode={step.mode === "transcribe" ? step.targetCode : undefined}
            value={answer}
            onChange={(value) => {
              if (!readOnly) onAnswerChange(value);
            }}
          />
        </Suspense>
      </div>
    );
  }

  if (kind === "derivation") {
    return (
      <div ref={answerRef} className="kd-answer-surface kd-answer-derivation">
        <fieldset aria-label="我的答案" disabled={readOnly}>
          <Suspense fallback={<p role="status">正在铺开推导纸…</p>}>
            <DerivationPracticeSurface
              steps={step.derivationSteps ?? []}
              targetSteps={step.mode === "transcribe" ? step.targetSteps : undefined}
              check={step.check}
              value={readDerivation(answer)}
              onChange={(value) => onAnswerChange(JSON.stringify(value))}
            />
          </Suspense>
        </fieldset>
      </div>
    );
  }

  return (
    <div ref={answerRef} className="kd-answer-surface">
      <textarea
        id="kd-answer"
        aria-label="我的答案"
        className="kd-answer"
        value={answer}
        readOnly={readOnly}
        onChange={(event) => onAnswerChange(event.target.value)}
      />
    </div>
  );
}

function resolveMarginAnnotation(result: CheckResult): {
  kind: "confirmed" | "revision" | "next_step";
  label: string;
  body: string;
} {
  const kind = result.annotationKind
    ?? (result.verdict === "completed" ? "confirmed" : result.gap ? "revision" : "next_step");
  if (kind === "confirmed") {
    return { kind, label: result.goodLabel || "已经说明清楚", body: result.good };
  }
  if (kind === "next_step") {
    return { kind, label: "接下来试试", body: result.next || result.gap };
  }
  return { kind, label: "还差一步", body: result.gap || result.next };
}

function exerciseOriginLabel(step: StudyStep): string | null {
  if (step.origin === "source") return "资料原题";
  if (step.origin === "adapted") return "根据资料改编";
  if (step.origin === "generated") return "小娜生成";
  return null;
}

function ModeSwitch({ mode, onModeChange }: { mode: NotebookMode; onModeChange?: (mode: NotebookMode) => void }) {
  return (
    <div className="kd-modes" role="group" aria-label="学习模式">
      <button
        type="button"
        aria-pressed={mode === "learn"}
        onClick={() => onModeChange?.("learn")}
      >
        学
      </button>
      <button
        type="button"
        aria-pressed={mode === "practice"}
        onClick={() => onModeChange?.("practice")}
      >
        练
      </button>
    </div>
  );
}

export function DeskNotebook({
  art,
  overview,
  step,
  density,
  activity,
  answer,
  saveStatusText,
  operationError,
  checkResult,
  surface = "notebook",
  mode = "practice",
  flyleafOpen = false,
  spaceTitle = "我的本子",
  pageBody,
  rightPage,
  continueTitle,
  continueMeta,
  continueLabel = "继续",
  pageNotice,
  knowledgeCoreTitle,
  knowledgeCoreIndex = 0,
  knowledgeCoreTotal = 0,
  hasPreviousStep = false,
  hasNextStep,
  taskSurfaceRef,
  answerRef,
  feedbackRef,
  onResume,
  onStartWriting,
  onAnswerChange,
  onCheck,
  onSaveAnswer,
  onPreviousStep,
  onNextStep,
  onPreviousKnowledgeCore,
  onNextKnowledgeCore,
  onBackToLearn,
  onModeChange,
  onToggleFlyleaf,
  onFutureFeature,
}: DeskNotebookProps) {
  const Bookmark = art.bookmark;
  const ArrowRight = art.arrowRight;
  const Check = art.check;
  const Circle = art.circle;
  const CircleCheck = art.circleCheck;
  const CircleDot = art.circleDot;

  const isOverview = density === "overview";
  const hasDraft = answer.trim() !== "";
  const readOnly = activity !== "dirty" && activity !== "needs_revision";
  const showFeedback =
    (activity === "needs_revision" || activity === "completed") && checkResult !== null;
  const marginAnnotation = checkResult ? resolveMarginAnnotation(checkResult) : null;

  const practiceContent = !(step && overview) ? (
    <section className="kd-overview-copy">
      <p className="kd-page-kicker">当前知识核的练习</p>
      <h2>{knowledgeCoreTitle ? `“${knowledgeCoreTitle}”还没有可用练习` : "当前范围还没有知识核"}</h2>
      <p>{knowledgeCoreTitle ? "仍停留在这一步，不会偷换到别的知识核。可以回学习，或请小娜基于材料拟一组待审核练习。" : "先在计划页确认范围，再整理这一段的知识核。"}</p>
      <div className="kd-inline-actions">
        {onBackToLearn ? <button type="button" className="kd-primary" onClick={onBackToLearn}>回到这个知识核的学习页</button> : null}
      </div>
      {knowledgeCoreTitle ? (
        <nav className="kd-core-navigation" aria-label="知识核导航">
          <button type="button" disabled={knowledgeCoreIndex === 0} onClick={onPreviousKnowledgeCore}>上一个知识核</button>
          <button type="button" disabled={knowledgeCoreIndex + 1 >= knowledgeCoreTotal} onClick={onNextKnowledgeCore}>下一个知识核</button>
        </nav>
      ) : null}
    </section>
  ) : isOverview ? (
    <section className="kd-overview-copy">
      <p className="kd-page-kicker">{overview.kicker}</p>
      <h2>{overview.heading}</h2>
      <p>{overview.body}</p>
      <ul className="kd-resume-list">
        {overview.resume.map((item) => (
          <li key={item.text}>
            {item.icon === "circleCheck" ? <CircleCheck /> : <CircleDot />} {item.text}
          </li>
        ))}
      </ul>
      <button type="button" className="kd-primary" onClick={onResume}>
        继续这一步 <ArrowRight />
      </button>
    </section>
  ) : (
    <section className="kd-page-main" tabIndex={-1} ref={taskSurfaceRef}>
      <div className="kd-task-scroll">
        {knowledgeCoreTitle ? (
          <div className="kd-core-context">
            <div>
              <p>正在练习这个知识核</p>
              <strong>{knowledgeCoreTitle}</strong>
            </div>
            <span>{knowledgeCoreIndex + 1} / {knowledgeCoreTotal}</span>
          </div>
        ) : null}
        <p className="kd-page-kicker">{step.kicker}</p>
        {exerciseOriginLabel(step) ? (
          <p className="kd-exercise-origin" data-origin={step.origin}>
            <strong>{exerciseOriginLabel(step)}</strong>
            {step.sourceLabel ? <span>{step.sourceLabel}</span> : null}
          </p>
        ) : null}
        <h2 className="kd-practice-question">{step.prompt}</h2>

        <div className="kd-answer-label">
          <strong id="kd-answer-heading">我的答案</strong>
        </div>
        <AnswerSurface
          step={step}
          answer={answer}
          readOnly={readOnly}
          answerRef={answerRef}
          onAnswerChange={onAnswerChange}
        />
        <p className="kd-save-status" role="status">{saveStatusText}</p>
        {operationError ? <p className="kd-operation-error" role="alert">{operationError}</p> : null}

        {showFeedback && marginAnnotation ? (
          <aside
            className="kd-feedback"
            data-annotation={marginAnnotation.kind}
            aria-label={`小娜批注：${marginAnnotation.label}`}
            tabIndex={-1}
            ref={feedbackRef}
          >
            <h3>小娜批注</h3>
            <div className="kd-feedback-row">
              {marginAnnotation.kind === "confirmed" ? <Check /> : marginAnnotation.kind === "revision" ? <Circle /> : <ArrowRight />}
              <p><strong>{marginAnnotation.label}</strong>{marginAnnotation.body}</p>
            </div>
          </aside>
        ) : null}
      </div>

      <div className="kd-inline-actions kd-task-actions">
        {activity === "ready" && (
          <button type="button" className="kd-primary" onClick={onStartWriting}>
            {hasDraft ? "继续作答" : "开始作答"}
          </button>
        )}
        {(activity === "dirty" || activity === "checking") && (
          <button
            type="button"
            className="kd-primary"
            disabled={activity === "checking"}
            onClick={onCheck}
          >
            {activity === "checking" ? "正在检查…" : "检查这一步"}
          </button>
        )}
        {activity === "needs_revision" && (
          <button type="button" className="kd-primary" onClick={onSaveAnswer}>保存答案</button>
        )}
        {activity === "completed" && (
          <button type="button" className="kd-primary" onClick={onNextStep}>
            {hasNextStep ? "继续下一步" : "返回练习总览"}
          </button>
        )}
        {onBackToLearn ? <button type="button" onClick={onBackToLearn}>回学习</button> : null}
      </div>
      {hasPreviousStep || hasNextStep ? (
        <nav className="kd-question-navigation" aria-label="当前知识核题目导航">
          <span>本知识核的题目</span>
          <div>
            <button type="button" disabled={!hasPreviousStep || activity === "checking"} onClick={onPreviousStep}>上一题</button>
            <button type="button" disabled={!hasNextStep || activity === "checking"} onClick={onNextStep}>下一题</button>
          </div>
        </nav>
      ) : null}
      {knowledgeCoreTitle ? (
        <nav className="kd-core-navigation" aria-label="知识核导航">
          <button type="button" disabled={knowledgeCoreIndex === 0} onClick={onPreviousKnowledgeCore}>
            上一个知识核
          </button>
          <button type="button" disabled={knowledgeCoreIndex + 1 >= knowledgeCoreTotal} onClick={onNextKnowledgeCore}>
            下一个知识核
          </button>
        </nav>
      ) : null}
    </section>
  );

  const leftContent = flyleafOpen
    ? pageBody
    : pageBody ?? practiceContent;

  const rightContent = flyleafOpen ? (
    <div className="kd-page-note">
      <p className="kd-page-kicker">扉页背面</p>
      <p>翻到扉页时右页空着——这一刻不是在做题，没有"纸上来的"要对照。</p>
      <p>改完点右下「保存」，或点页眉「回到这一页」翻回去。</p>
    </div>
  ) : rightPage;

  return (
    <article className="kd-notebook" data-surface={surface} data-mode={mode} data-flyleaf={flyleafOpen || undefined}>
      <header className="kd-notebook-head">
        <button
          type="button"
          className="kd-notebook-title"
          onClick={onToggleFlyleaf ?? onFutureFeature}
          aria-expanded={flyleafOpen}
        >
          <span className="kd-notebook-label">自习主题</span>
          <strong>{spaceTitle}</strong>
          <span className="kd-notebook-flip">{flyleafOpen ? "◂ 回到这一页" : "翻到扉页 ▸"}</span>
        </button>
        {continueTitle ? (
          <button
            type="button"
            className="kd-bookmark-button"
            aria-label={`${continueLabel}：${continueTitle}${continueMeta ? `，${continueMeta}` : ""}`}
            onClick={onResume}
          >
            <Bookmark aria-hidden />
            <span>{continueLabel === "从这里开始" ? "开始" : "继续"}</span>
          </button>
        ) : <span className="kd-bookmark-button is-empty" aria-hidden="true" />}
      </header>

      <div className="kd-notebook-body">
        {pageNotice ? <p className="kd-recovery-notice" role="status">{pageNotice}</p> : null}
        <div className="kd-spread">
          <div className="kd-page kd-page-l">
            {!flyleafOpen && <ModeSwitch mode={mode} onModeChange={onModeChange} />}
            {leftContent}
          </div>
          <div className="kd-page kd-page-r">
            {rightContent}
          </div>
        </div>

        {/* 提示只是当前题的一条线索；不用摘要复述题目，也不能泄露答案。 */}
        {flyleafOpen || pageBody || !step ? null : (
          <details className="kd-reference-fold">
            <summary>提示</summary>
            <div>
              <p>{step.referenceHint}</p>
            </div>
          </details>
        )}
      </div>
    </article>
  );
}
