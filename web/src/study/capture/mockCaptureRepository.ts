// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import type {
  CaptureSessionV1,
  CaptureTransformV1,
  ExternalWrongbookEntryV1,
  StudyAssistanceV1,
  StudyReviewDraftV1,
  StudyTranscriptionV1,
  WrongbookDecision,
} from "../../chat/study/study-capture-api";
import {
  makeAssistance,
  makeCaptureError,
  makeCaptureSession,
  makeFullAnswerAssistance,
  makeReviewDraft,
  makeTranscription,
} from "./captureFixtures";

export interface MockCaptureRepository {
  stageUpload(file: File, purpose: CaptureSessionV1["purpose"]): Promise<CaptureSessionV1>;
  stageCamera(blob: Blob, purpose: CaptureSessionV1["purpose"]): Promise<CaptureSessionV1>;
  normalize(transform: CaptureTransformV1): Promise<CaptureSessionV1>;
  transcribe(session: CaptureSessionV1): Promise<StudyTranscriptionV1>;
  requestAssistance(
    captureId: string,
    mode: "next_step" | "full_answer",
  ): Promise<StudyAssistanceV1>;
  requestReview(captureId: string): Promise<StudyReviewDraftV1>;
  confirmWrongbook(
    captureId: string,
    decision: WrongbookDecision,
  ): Promise<ExternalWrongbookEntryV1 | null>;
  abandon(captureId: string): Promise<void>;
}

let captureCounter = 0;
const sessions = new Map<string, CaptureSessionV1>();

function nextCaptureId(): string {
  captureCounter += 1;
  return `capture-${captureCounter}`;
}

function delay(ms = 120): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export function createMockCaptureRepository(): MockCaptureRepository {
  return {
    async stageUpload(file, purpose) {
      await delay();
      if (file.size > 10 * 1024 * 1024) {
        throw makeCaptureError("capture_too_large", "图片超过 10MB");
      }
      const session = makeCaptureSession({
        capture_id: nextCaptureId(),
        purpose,
        source_kind: "upload",
      });
      sessions.set(session.capture_id, session);
      return session;
    },

    async stageCamera(blob, purpose) {
      await delay();
      if (!blob.size) {
        throw makeCaptureError("capture_invalid_image", "照片为空");
      }
      const session = makeCaptureSession({
        capture_id: nextCaptureId(),
        purpose,
        source_kind: "camera",
      });
      sessions.set(session.capture_id, session);
      return session;
    },

    async normalize(transform) {
      await delay();
      const session = sessions.get(transform.capture_id);
      if (!session) {
        throw makeCaptureError("capture_invalid_image", "找不到这张 capture");
      }
      if (session.revision !== transform.expected_revision) {
        throw makeCaptureError("capture_revision_conflict", "裁剪版本冲突");
      }
      const normalized: CaptureSessionV1 = {
        ...session,
        status: "normalized",
        revision: session.revision + 1,
        preview: {
          width: Math.round(session.preview.width * transform.crop.width),
          height: Math.round(session.preview.height * transform.crop.height),
        },
      };
      sessions.set(session.capture_id, normalized);
      return normalized;
    },

    async transcribe(session) {
      await delay();
      if (!sessions.has(session.capture_id)) {
        throw makeCaptureError("capture_invalid_image", "找不到这张 capture");
      }
      const transcribed: CaptureSessionV1 = { ...session, status: "transcribed" };
      sessions.set(session.capture_id, transcribed);
      return makeTranscription({ capture_id: session.capture_id, purpose: session.purpose });
    },

    async requestAssistance(captureId, mode) {
      await delay();
      if (!sessions.has(captureId)) {
        throw makeCaptureError("capture_invalid_image", "找不到这张 capture");
      }
      return mode === "full_answer" ? makeFullAnswerAssistance() : makeAssistance();
    },

    async requestReview(captureId) {
      await delay();
      if (!sessions.has(captureId)) {
        throw makeCaptureError("capture_invalid_image", "找不到这张 capture");
      }
      return makeReviewDraft();
    },

    async confirmWrongbook(captureId, decision) {
      await delay();
      const session = sessions.get(captureId);
      if (!session) {
        throw makeCaptureError("capture_invalid_image", "找不到这张 capture");
      }
      if (decision !== "wrong") {
        // correct/unreadable do not create an active entry.
        return null;
      }
      const now = new Date().toISOString();
      return {
        capture_id: captureId,
        media_id: `media-${captureId}`,
        question_text: "求 ∫ 3x² · sin(x³) dx",
        student_work: "令 u = x³，du = 3x² dx\n= ∫ sin(u) du",
        correct_work: "= -cos(u) + C = -cos(x³) + C",
        knowledge_points: ["换元的微分对应", "sin 的原函数与负号"],
        review: makeReviewDraft(),
        status: "active",
        created_at: now,
        updated_at: now,
      };
    },

    async abandon(captureId) {
      await delay();
      const session = sessions.get(captureId);
      if (session) {
        sessions.set(captureId, { ...session, status: "abandoned" });
      }
    },
  };
}

export const mockCaptureRepository = createMockCaptureRepository();
