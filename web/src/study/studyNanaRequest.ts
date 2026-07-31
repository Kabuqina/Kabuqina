// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import type { StudyNanaPage } from "../lib/studyChatHandoff";

const STUDY_NANA_REQUEST_EVENT = "kabuqina:study-nana-request";

export type StudyNanaRequest = {
  spaceId: string;
  page: StudyNanaPage;
  focusId: string;
  focusLabel: string;
  outlineNodeId?: string;
  selectedSource?: { id: string; title: string };
  autoSend?: boolean;
  initialPrompt: string;
};

export function requestStudyNana(request: StudyNanaRequest): void {
  window.dispatchEvent(new CustomEvent<StudyNanaRequest>(STUDY_NANA_REQUEST_EVENT, {
    detail: request,
  }));
}

export function onStudyNanaRequest(listener: (request: StudyNanaRequest) => void): () => void {
  const handle = (event: Event) => {
    const request = (event as CustomEvent<StudyNanaRequest>).detail;
    if (!request || typeof request !== "object") return;
    listener(request);
  };
  window.addEventListener(STUDY_NANA_REQUEST_EVENT, handle);
  return () => window.removeEventListener(STUDY_NANA_REQUEST_EVENT, handle);
}
