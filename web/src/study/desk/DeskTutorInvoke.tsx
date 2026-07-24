// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useEffect, useRef } from "react";
import type { CheckResult, StudyActivity, StudyStep } from "./types";

export type DeskCourseChatRequest = {
  focusId: string;
  focusLabel: string;
  prompt: string;
  answer: string;
  feedback: string;
  question: string;
  activity: Exclude<StudyActivity, "checking">;
  checkResult: CheckResult | null;
};

export function DeskTutorInvoke({
  courseName,
  step,
  answer,
  activity,
  checkResult,
  question,
  onQuestionChange,
  onSubmit,
  onCancel,
}: {
  courseName: string;
  step: StudyStep;
  answer: string;
  activity: Exclude<StudyActivity, "checking">;
  checkResult: CheckResult | null;
  question: string;
  onQuestionChange: (value: string) => void;
  onSubmit: (request: DeskCourseChatRequest) => void;
  onCancel: () => void;
}) {
  const questionRef = useRef<HTMLTextAreaElement>(null);
  useEffect(() => {
    const frame = window.requestAnimationFrame(() => questionRef.current?.focus());
    return () => window.cancelAnimationFrame(frame);
  }, []);

  const feedback = checkResult
    ? [checkResult.good, checkResult.gap, checkResult.next].filter(Boolean).join(" ")
    : "";

  return (
    <main className="kd-invoke-layout">
      <section className="kd-invoke-card" aria-labelledby="kd-invoke-title">
        <p className="kd-page-kicker">课程对话</p>
        <h1 id="kd-invoke-title">结合当前这一步问小娜</h1>
        <p>她会带上你正在看的题、当前答案和检查反馈，但不会替你改写答案。</p>
        <div className="kd-context-preview">
          <strong>{courseName} · {step.kicker}</strong>
          <span>返回位置：我的答案与页边批注</span>
        </div>
        <dl className="kd-context-detail">
          <div>
            <dt>当前题目</dt>
            <dd>{step.prompt}</dd>
          </div>
          <div>
            <dt>当前答案</dt>
            <dd>{answer.trim() || "尚未作答"}</dd>
          </div>
          {feedback ? (
            <div>
              <dt>检查反馈</dt>
              <dd>{feedback}</dd>
            </div>
          ) : null}
        </dl>
        <label htmlFor="kd-invoke-question"><strong>我卡在哪里？</strong></label>
        <textarea
          ref={questionRef}
          id="kd-invoke-question"
          value={question}
          onChange={(event) => onQuestionChange(event.currentTarget.value)}
        />
        <div className="kd-inline-actions">
          <button
            type="button"
            className="kd-primary"
            disabled={!question.trim()}
            onClick={() => onSubmit({
              focusId: step.id,
              focusLabel: step.kicker,
              prompt: step.prompt,
              answer,
              feedback,
              question: question.trim(),
              activity,
              checkResult,
            })}
          >
            开始提问
          </button>
          <button type="button" onClick={onCancel}>先不问</button>
        </div>
      </section>
    </main>
  );
}
