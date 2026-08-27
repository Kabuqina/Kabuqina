// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import type {
  CapturePurpose,
  CaptureSessionV1,
  CaptureSourceKind,
  StudyAssistanceV1,
  StudyCaptureErrorCode,
  StudyReviewDraftV1,
  StudyTranscriptionV1,
} from "../../chat/study/study-capture-api";

export type CaptureStatus =
  | "idle"
  | "choosing"
  | "cropping"
  | "submitting"
  | "transcribing"
  | "confirming"
  | "assisting"
  | "reviewing"
  | "failed";

export interface CaptureState {
  status: CaptureStatus;
  capture_id: string | null;
  source: CaptureSourceKind | null;
  purpose: CapturePurpose | null;
  session: CaptureSessionV1 | null;
  transcription: StudyTranscriptionV1 | null;
  assistance: StudyAssistanceV1 | null;
  review: StudyReviewDraftV1 | null;
  error_code: StudyCaptureErrorCode | null;
  error_message: string | null;
}

export const initialCaptureState: CaptureState = {
  status: "idle",
  capture_id: null,
  source: null,
  purpose: null,
  session: null,
  transcription: null,
  assistance: null,
  review: null,
  error_code: null,
  error_message: null,
};

export type CaptureAction =
  | { type: "start_choosing"; purpose: CapturePurpose }
  | { type: "source_selected"; source: CaptureSourceKind }
  | { type: "capture_submitted"; session: CaptureSessionV1 }
  | { type: "transcription_received"; transcription: StudyTranscriptionV1 }
  | { type: "transcription_confirmed" }
  | { type: "request_assistance"; assistance: StudyAssistanceV1 }
  | { type: "request_review"; review: StudyReviewDraftV1 }
  | { type: "wrongbook_confirmed" }
  | { type: "capture_failed"; code: StudyCaptureErrorCode; message: string }
  | { type: "abandon" }
  | { type: "retry" }
  | { type: "reset" };

export function captureReducer(state: CaptureState, action: CaptureAction): CaptureState {
  switch (action.type) {
    case "start_choosing":
      return {
        ...initialCaptureState,
        status: "choosing",
        purpose: action.purpose,
      };
    case "source_selected":
      if (state.status !== "choosing") return state;
      return {
        ...state,
        status: "cropping",
        source: action.source,
      };
    case "capture_submitted":
      if (state.status !== "cropping" && state.status !== "choosing") return state;
      return {
        ...state,
        status: "submitting",
        session: action.session,
        capture_id: action.session.capture_id,
      };
    case "transcription_received":
      if (state.status !== "submitting" && state.status !== "transcribing") return state;
      return {
        ...state,
        status: "confirming",
        transcription: action.transcription,
        error_code: null,
        error_message: null,
      };
    case "transcription_confirmed":
      if (state.status !== "confirming") return state;
      // After confirmation, the next state depends on purpose: stuck → assisting, review → reviewing.
      return {
        ...state,
        status: state.purpose === "review" ? "reviewing" : "assisting",
      };
    case "request_assistance":
      if (state.status !== "assisting" && state.status !== "confirming") return state;
      return {
        ...state,
        status: "assisting",
        assistance: action.assistance,
      };
    case "request_review":
      if (state.status !== "reviewing" && state.status !== "confirming" && state.status !== "assisting") return state;
      return {
        ...state,
        status: "reviewing",
        review: action.review,
      };
    case "wrongbook_confirmed":
      if (state.status !== "reviewing" && state.status !== "assisting") return state;
      return {
        ...state,
        status: "idle",
        session: state.session ? { ...state.session, status: "confirmed" } : null,
      };
    case "capture_failed":
      return {
        ...state,
        status: "failed",
        error_code: action.code,
        error_message: action.message,
      };
    case "abandon":
      return {
        ...initialCaptureState,
        session: state.session ? { ...state.session, status: "abandoned" } : null,
      };
    case "retry":
      // Retry from the last stable state before the failure.
      if (state.status !== "failed") return state;
      return {
        ...state,
        status: state.session ? "cropping" : "choosing",
        error_code: null,
        error_message: null,
      };
    case "reset":
      return initialCaptureState;
    default:
      return state;
  }
}

/** Map a capture status to a stable UI state key for error recovery. */
export function captureUiStateForError(code: StudyCaptureErrorCode): CaptureStatus {
  switch (code) {
    case "capture_camera_unavailable":
    case "capture_permission_denied":
      return "choosing";
    case "capture_invalid_image":
    case "capture_too_large":
      return "cropping";
    case "vision_unreadable":
    case "capture_question_mismatch":
      return "confirming";
    case "capture_revision_conflict":
    case "wrongbook_idempotency_conflict":
      return "reviewing";
    default:
      return "idle";
  }
}
