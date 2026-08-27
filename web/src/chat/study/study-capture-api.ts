// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

/** Stable wire contracts shared by renderer, Tauri, and Python. */

export const CAPTURE_SCHEMA_VERSION = 1 as const;

export type CapturePurpose = "stuck" | "review" | "printed_source";
export type CaptureSourceKind = "camera" | "upload";
export type CaptureSessionStatus =
  | "temporary"
  | "normalized"
  | "transcribed"
  | "drafted"
  | "confirmed"
  | "abandoned";

export interface CaptureSessionV1 {
  schema_version: typeof CAPTURE_SCHEMA_VERSION;
  capture_id: string;
  space_id: string;
  purpose: CapturePurpose;
  source_kind: CaptureSourceKind;
  status: CaptureSessionStatus;
  revision: number;
  preview: {
    width: number;
    height: number;
  };
}

export interface CaptureTransformV1 {
  schema_version: typeof CAPTURE_SCHEMA_VERSION;
  capture_id: string;
  expected_revision: number;
  crop: {
    x: number;
    y: number;
    width: number;
    height: number;
  };
  rotation: 0 | 90 | 180 | 270;
  grayscale: boolean;
  max_edge: number;
}

export type ConfidenceBand = "high" | "medium" | "low";
export type QuestionMatch = "same" | "different" | "unknown";

export interface TranscriptionLine {
  index: number;
  text: string;
  unreadable?: boolean;
}

export interface StudyTranscriptionV1 {
  schema_version: typeof CAPTURE_SCHEMA_VERSION;
  capture_id: string;
  purpose: CapturePurpose;
  question_text: string;
  student_work: string;
  lines: TranscriptionLine[];
  unreadable_regions: Array<{
    index: number;
    reason: string;
  }>;
  confidence_band: ConfidenceBand;
  question_match: QuestionMatch;
  provider: string;
  model: string;
}

export type AssistanceMode = "next_step" | "full_answer";

export interface StudyAssistanceV1 {
  mode: AssistanceMode;
  /** Present only when mode is next_step. A single directional hint. */
  hint?: string;
  /** Present only when mode is full_answer. */
  answer?: string;
  knowledge_points?: string[];
  skipped_items?: string[];
}

export interface StudyReviewDraftV1 {
  deviation_start: string;
  basis: string;
  uncertain_items: string[];
}

export type WrongbookDecision = "wrong" | "correct" | "unreadable";
export type WrongbookEntryStatus = "draft" | "confirmed" | "active";

export interface ExternalWrongbookEntryV1 {
  capture_id: string;
  media_id: string | null;
  question_text: string;
  student_work: string;
  correct_work: string;
  knowledge_points: string[];
  review: StudyReviewDraftV1 | null;
  status: WrongbookEntryStatus;
  created_at: string;
  updated_at: string;
}

export type StudyCaptureErrorCode =
  | "capture_camera_unavailable"
  | "capture_permission_denied"
  | "capture_invalid_image"
  | "capture_too_large"
  | "capture_revision_conflict"
  | "vision_not_configured"
  | "vision_unavailable"
  | "vision_contract_invalid"
  | "vision_unreadable"
  | "capture_question_mismatch"
  | "wrongbook_idempotency_conflict";

export interface StudyCaptureError {
  code: StudyCaptureErrorCode;
  retryable: boolean;
  /** Whether the temporary image should be kept for retry. */
  keep_temp: boolean;
  /** Which UI state to return to after this error. */
  ui_state: "idle" | "choosing" | "cropping" | "confirming";
  message: string;
}
