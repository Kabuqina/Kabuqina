// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { describe, expect, it } from "vitest";
import {
  captureReducer,
  captureUiStateForError,
  initialCaptureState,
} from "./captureState";
import {
  makeAssistance,
  makeCaptureSession,
  makeReviewDraft,
  makeTranscription,
} from "./captureFixtures";

describe("capture state machine", () => {
  it("starts choosing with a purpose", () => {
    const state = captureReducer(initialCaptureState, {
      type: "start_choosing",
      purpose: "stuck",
    });
    expect(state.status).toBe("choosing");
    expect(state.purpose).toBe("stuck");
  });

  it("moves to cropping after a source is selected", () => {
    const choosing = captureReducer(initialCaptureState, {
      type: "start_choosing",
      purpose: "review",
    });
    const cropping = captureReducer(choosing, {
      type: "source_selected",
      source: "upload",
    });
    expect(cropping.status).toBe("cropping");
    expect(cropping.source).toBe("upload");
  });

  it("moves to submitting after capture is submitted", () => {
    const choosing = captureReducer(initialCaptureState, {
      type: "start_choosing",
      purpose: "stuck",
    });
    const cropping = captureReducer(choosing, {
      type: "source_selected",
      source: "camera",
    });
    const session = makeCaptureSession();
    const submitting = captureReducer(cropping, {
      type: "capture_submitted",
      session,
    });
    expect(submitting.status).toBe("submitting");
    expect(submitting.capture_id).toBe(session.capture_id);
  });

  it("moves to confirming after transcription arrives", () => {
    const choosing = captureReducer(initialCaptureState, {
      type: "start_choosing",
      purpose: "stuck",
    });
    const cropping = captureReducer(choosing, {
      type: "source_selected",
      source: "upload",
    });
    const session = makeCaptureSession();
    const submitting = captureReducer(cropping, {
      type: "capture_submitted",
      session,
    });
    const confirming = captureReducer(submitting, {
      type: "transcription_received",
      transcription: makeTranscription({ capture_id: session.capture_id }),
    });
    expect(confirming.status).toBe("confirming");
    expect(confirming.transcription?.capture_id).toBe(session.capture_id);
  });

  it("routes to assisting for stuck purpose after confirmation", () => {
    const confirming = {
      ...initialCaptureState,
      status: "confirming" as const,
      purpose: "stuck" as const,
    };
    const assisting = captureReducer(confirming, { type: "transcription_confirmed" });
    expect(assisting.status).toBe("assisting");
  });

  it("routes to reviewing for review purpose after confirmation", () => {
    const confirming = {
      ...initialCaptureState,
      status: "confirming" as const,
      purpose: "review" as const,
    };
    const reviewing = captureReducer(confirming, { type: "transcription_confirmed" });
    expect(reviewing.status).toBe("reviewing");
  });

  it("accepts assistance and returns to idle on wrongbook confirmation", () => {
    const confirming = {
      ...initialCaptureState,
      status: "confirming" as const,
      purpose: "stuck" as const,
      session: makeCaptureSession(),
    };
    const assisting = captureReducer(confirming, {
      type: "request_assistance",
      assistance: makeAssistance(),
    });
    expect(assisting.status).toBe("assisting");
    expect(assisting.assistance?.mode).toBe("next_step");

    const done = captureReducer(assisting, { type: "wrongbook_confirmed" });
    expect(done.status).toBe("idle");
    expect(done.session?.status).toBe("confirmed");
  });

  it("accepts review and returns to idle on wrongbook confirmation", () => {
    const confirming = {
      ...initialCaptureState,
      status: "confirming" as const,
      purpose: "review" as const,
      session: makeCaptureSession(),
    };
    const reviewing = captureReducer(confirming, {
      type: "request_review",
      review: makeReviewDraft(),
    });
    expect(reviewing.status).toBe("reviewing");
    expect(reviewing.review?.deviation_start).toBeTruthy();

    const done = captureReducer(reviewing, { type: "wrongbook_confirmed" });
    expect(done.status).toBe("idle");
    expect(done.session?.status).toBe("confirmed");
  });

  it("stores the error and allows retry from a stable state", () => {
    const failed = captureReducer(initialCaptureState, {
      type: "capture_failed",
      code: "vision_unreadable",
      message: "无法识别",
    });
    expect(failed.status).toBe("failed");
    expect(failed.error_code).toBe("vision_unreadable");

    const retried = captureReducer(failed, { type: "retry" });
    expect(retried.status).toBe("choosing");
    expect(retried.error_code).toBeNull();
  });

  it("abandons cleanly", () => {
    const choosing = captureReducer(initialCaptureState, {
      type: "start_choosing",
      purpose: "printed_source",
    });
    const abandoned = captureReducer(choosing, { type: "abandon" });
    expect(abandoned.status).toBe("idle");
    expect(abandoned.purpose).toBeNull();
  });

  it("maps error codes to stable UI states", () => {
    expect(captureUiStateForError("capture_camera_unavailable")).toBe("choosing");
    expect(captureUiStateForError("capture_permission_denied")).toBe("choosing");
    expect(captureUiStateForError("capture_invalid_image")).toBe("cropping");
    expect(captureUiStateForError("vision_unreadable")).toBe("confirming");
    expect(captureUiStateForError("capture_question_mismatch")).toBe("confirming");
  });
});
