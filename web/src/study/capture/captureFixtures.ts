// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import type {
  CaptureSessionV1,
  StudyAssistanceV1,
  StudyCaptureError,
  StudyReviewDraftV1,
  StudyTranscriptionV1,
} from "../../chat/study/study-capture-api";

export function makeCaptureSession(overrides: Partial<CaptureSessionV1> = {}): CaptureSessionV1 {
  return {
    schema_version: 1,
    capture_id: "capture-1",
    space_id: "space-a",
    purpose: "stuck",
    source_kind: "upload",
    status: "temporary",
    revision: 1,
    preview: { width: 1280, height: 960 },
    ...overrides,
  };
}

export function makeTranscription(overrides: Partial<StudyTranscriptionV1> = {}): StudyTranscriptionV1 {
  return {
    schema_version: 1,
    capture_id: "capture-1",
    purpose: "stuck",
    question_text: "求 ∫ 3x² · sin(x³) dx",
    student_work: "令 u = x³，du = 3x² dx\n= ∫ sin(u) du",
    lines: [
      { index: 1, text: "∫ 3x² · sin(x³) dx" },
      { index: 2, text: "令 u = x³，du = 3x² dx" },
      { index: 3, text: "= ∫ sin(u) du" },
      { index: 4, text: "这一行右半看不清（有划改）", unreadable: true },
    ],
    unreadable_regions: [{ index: 4, reason: "scribble" }],
    confidence_band: "medium",
    question_match: "same",
    provider: "internal-only",
    model: "internal-only",
    ...overrides,
  };
}

export function makeAssistance(overrides: Partial<StudyAssistanceV1> = {}): StudyAssistanceV1 {
  return {
    mode: "next_step",
    hint: "第 3 行你已经把式子化成 ∫sin(u)du 了。现在问自己一句：什么函数求导之后是 sin(u)？",
    ...overrides,
  };
}

export function makeFullAnswerAssistance(): StudyAssistanceV1 {
  return {
    mode: "full_answer",
    answer: "∫3x²·sin(x³)dx = −cos(x³) + C",
    knowledge_points: ["换元的微分对应", "sin 的原函数与负号", "换回原变量"],
    skipped_items: ["换元的微分对应"],
  };
}

export function makeReviewDraft(overrides: Partial<StudyReviewDraftV1> = {}): StudyReviewDraftV1 {
  return {
    deviation_start: "第 4 行之后",
    basis: "没有换回原变量 x，而且 sin 的原函数漏了负号。",
    uncertain_items: ["第 4 行右半有划改，无法完全确认"],
    ...overrides,
  };
}

export function makeCaptureError(code: StudyCaptureError["code"], message: string): StudyCaptureError {
  const retryable = code !== "capture_invalid_image" && code !== "capture_too_large";
  return {
    code,
    retryable,
    keep_temp: retryable,
    ui_state: code === "capture_camera_unavailable" || code === "capture_permission_denied"
      ? "choosing"
      : code === "capture_invalid_image" || code === "capture_too_large"
        ? "cropping"
        : code === "vision_unreadable" || code === "capture_question_mismatch"
          ? "confirming"
          : "idle",
    message,
  };
}
