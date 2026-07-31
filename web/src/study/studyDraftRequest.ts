// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

export const STUDY_DRAFT_REQUEST_EVENT = "kabuqina:study-draft-request";

export type StudyDraftRequest = {
  spaceId: string;
  artifactId: string;
};

export function requestStudyDraft(request: StudyDraftRequest): void {
  window.dispatchEvent(new CustomEvent<StudyDraftRequest>(
    STUDY_DRAFT_REQUEST_EVENT,
    { detail: request },
  ));
}

export function onStudyDraftRequest(listener: (request: StudyDraftRequest) => void): () => void {
  const handler = (event: Event) => {
    const request = (event as CustomEvent<StudyDraftRequest>).detail;
    if (request?.spaceId && request.artifactId) listener(request);
  };
  window.addEventListener(STUDY_DRAFT_REQUEST_EVENT, handler);
  return () => window.removeEventListener(STUDY_DRAFT_REQUEST_EVENT, handler);
}
