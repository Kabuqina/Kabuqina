// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { lazy, Suspense, type ReactNode, type RefObject } from "react";
import type { StudyPageSlug } from "../routeModel";
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

export interface DeskNotebookProps {
  art: DeskArtAssets;
  /** 练习专用；没有可用测验时缺席，本子仍然照常打开。 */
  overview?: DeskOverview;
  step?: StudyStep;
  density: DeskDensity;
  activity: StudyActivity;
  answer: string;
  answerStateText: string;
  saveStatusText: string;
  operationError: string | null;
  checkResult: CheckResult | null;
  currentPage?: StudyPageSlug;
  /**
   * 非练习分页的正文。笔记本的五个分页共用同一本本子（原型 `StudyNotebook`）——
   * 扉页 / 计划 / 学习 / 评估 由 `StudyPageOutlet` 铺在这里，练习仍由本组件自己画，
   * 因为只有它带着作答面、检查反馈和页边批注。
   */
  pageBody?: ReactNode;
  hasNextStep: boolean;
  taskSurfaceRef: RefObject<HTMLElement | null>;
  answerRef: RefObject<HTMLDivElement | null>;
  feedbackRef: RefObject<HTMLDivElement | null>;
  onResume: () => void;
  onStartWriting: () => void;
  onAnswerChange: (value: string) => void;
  onCheck: () => void;
  onModify: () => void;
  onAskTutor: () => void;
  onNextStep: () => void;
  onNavigatePage?: (page: StudyPageSlug) => void;
  onFutureFeature: () => void;
}

const PAGE_TABS: ReadonlyArray<{ label: string; page: StudyPageSlug }> = [
  { label: "扉页", page: "flyleaf" },
  { label: "计划", page: "plan" },
  { label: "学习", page: "learn" },
  { label: "练习", page: "practice" },
  { label: "评估", page: "evaluate" },
];

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

export function DeskNotebook({
  art,
  overview,
  step,
  density,
  activity,
  answer,
  answerStateText,
  saveStatusText,
  operationError,
  checkResult,
  currentPage = "practice",
  pageBody,
  hasNextStep,
  taskSurfaceRef,
  answerRef,
  feedbackRef,
  onResume,
  onStartWriting,
  onAnswerChange,
  onCheck,
  onModify,
  onAskTutor,
  onNextStep,
  onNavigatePage,
  onFutureFeature,
}: DeskNotebookProps) {
  const Bookmark = art.bookmark;
  const ArrowRight = art.arrowRight;
  const Check = art.check;
  const Circle = art.circle;
  const Coffee = art.coffee;
  const CircleCheck = art.circleCheck;
  const CircleDot = art.circleDot;

  const isOverview = density === "overview";
  const hasDraft = answer.trim() !== "";
  const readOnly = activity !== "dirty";
  const showFeedback =
    (activity === "needs_revision" || activity === "completed") && checkResult !== null;

  return (
    <article className="kd-notebook">
      <header className="kd-notebook-head">
        <nav className="kd-page-tabs" aria-label="笔记本分页">
          {PAGE_TABS.map(({ label, page }) => (
            <button
              key={page}
              type="button"
              aria-current={page === currentPage ? "page" : undefined}
              onClick={
                page === currentPage
                  ? undefined
                  : onNavigatePage
                    ? () => onNavigatePage(page)
                    : onFutureFeature
              }
            >
              {label}
            </button>
          ))}
        </nav>
        {step ? (
          <button type="button" className="kd-bookmark-button" onClick={onResume}>
            <strong><Bookmark /> <span>继续：{step.kicker}</span></strong>
            <span>{step.title}</span>
          </button>
        ) : null}
      </header>

      <div className="kd-page-body">
        {pageBody ?? (!(step && overview) ? (
          <section className="kd-overview-copy">
            <p className="kd-page-kicker">练习</p>
            <h2>这本课程本还没有可练的题</h2>
            <p>先在学习页读材料，或让小娜按材料出一组练习。其余分页照常可用。</p>
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
              <p className="kd-page-kicker">{step.kicker}</p>
              <h2 className="kd-task-title">{step.title}</h2>
              <p className="kd-standard"><strong>完成标准：</strong>{step.standard}</p>
              <p className="kd-prompt">{step.prompt}</p>

              <div className="kd-answer-label">
                <strong id="kd-answer-heading">我的答案</strong>
                <span>{answerStateText}</span>
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

              {showFeedback && (
                <div className="kd-feedback" tabIndex={-1} ref={feedbackRef}>
                  <h3>{activity === "completed" ? "页边批注 · 本步完成" : "页边批注 · 需要修改"}</h3>
                  <div className="kd-feedback-row">
                    <Check />
                    <p><strong>{checkResult.goodLabel}</strong>{checkResult.good}</p>
                  </div>
                  {activity === "needs_revision" && (
                    <>
                      <div className="kd-feedback-row">
                        <Circle />
                        <p><strong>还差一步</strong>{checkResult.gap}</p>
                      </div>
                      <div className="kd-feedback-row">
                        <ArrowRight />
                        <p><strong>接下来试试</strong>{checkResult.next}</p>
                      </div>
                    </>
                  )}
                </div>
              )}
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
                <>
                  <button type="button" className="kd-primary" onClick={onModify}>修改答案</button>
                  <button id="kd-inline-chat" type="button" onClick={onAskTutor}>
                    <Coffee /> 让小娜陪我补这一步
                  </button>
                </>
              )}
              {activity === "completed" && (
                <button type="button" className="kd-primary" onClick={onNextStep}>
                  {hasNextStep ? "继续下一步" : "返回练习总览"}
                </button>
              )}
            </div>
          </section>
        ))}

        {/* 「本题参考」是练习那一页的东西；扉页/计划/学习/评估上不该出现。 */}
        {pageBody || !step ? null : (
          <details className="kd-reference-fold">
            <summary>本题参考</summary>
            <div>
              <p>{step.referenceSummary}</p>
              <p><strong>提示：</strong>{step.referenceHint}</p>
            </div>
          </details>
        )}
      </div>
    </article>
  );
}
