// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

export const STUDY_MATERIAL_REQUEST_EVENT = "kabuqina:study-material-request";

export type StudyMaterialRequest = {
  spaceId: string;
  artifactId: string;
  page?: number;
};

export function requestStudyMaterial(request: StudyMaterialRequest): void {
  window.dispatchEvent(new CustomEvent<StudyMaterialRequest>(
    STUDY_MATERIAL_REQUEST_EVENT,
    { detail: request },
  ));
}

export function onStudyMaterialRequest(listener: (request: StudyMaterialRequest) => void): () => void {
  const handler = (event: Event) => {
    const request = (event as CustomEvent<StudyMaterialRequest>).detail;
    if (request?.spaceId && request.artifactId) listener(request);
  };
  window.addEventListener(STUDY_MATERIAL_REQUEST_EVENT, handler);
  return () => window.removeEventListener(STUDY_MATERIAL_REQUEST_EVENT, handler);
}
