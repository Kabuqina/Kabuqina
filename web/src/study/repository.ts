// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import {
  cmdStudyArtifactSummaries,
  cmdStudySpaces,
  cmdStudySpaceSelect,
  type StudyDraftsResponse,
  type StudySpacesResponse,
} from "../chat/study/study-api";

export type StudySpaceSummary = {
  id: string;
  title: string;
  status: string;
  isCurrent: boolean;
};

export type StudySpaces = {
  currentSpaceId: string | null;
  spaces: StudySpaceSummary[];
};

export type StudyDraftInbox = {
  total: number;
  kindCounts: Readonly<Record<string, number>>;
};

export type StudyRepositoryErrorCode =
  | "unavailable"
  | "not-found"
  | "conflict"
  | "invalid"
  | "unknown";

export class StudyRepositoryError extends Error {
  constructor(
    public readonly code: StudyRepositoryErrorCode,
    options?: { cause?: unknown },
  ) {
    super(`study repository: ${code}`, options);
    this.name = "StudyRepositoryError";
  }
}

export interface StudyRepository {
  listSpaces(signal: AbortSignal): Promise<StudySpaces>;
  selectSpace(spaceId: string, signal: AbortSignal): Promise<StudySpaces>;
  listDrafts(spaceId: string, signal: AbortSignal): Promise<StudyDraftInbox>;
}

type DeskBridgeErrorPayload = {
  status: number | null;
  code: string;
  detail: string;
};

function isDeskBridgeErrorPayload(error: unknown): error is DeskBridgeErrorPayload {
  if (!error || typeof error !== "object") return false;
  const candidate = error as Record<string, unknown>;
  return (
    (candidate.status === null || typeof candidate.status === "number") &&
    typeof candidate.code === "string" &&
    typeof candidate.detail === "string"
  );
}

type StudyCommands = {
  spaces: () => Promise<StudySpacesResponse>;
  selectSpace: (spaceId: string) => Promise<StudySpacesResponse>;
  draftSummary: (spaceId: string) => Promise<StudyDraftsResponse>;
};

const defaultCommands: StudyCommands = {
  spaces: cmdStudySpaces,
  selectSpace: cmdStudySpaceSelect,
  draftSummary: (spaceId) => cmdStudyArtifactSummaries({
    spaceId,
    status: "draft",
    limit: 1,
  }),
};

function abortError(): DOMException {
  return new DOMException("The operation was aborted", "AbortError");
}

async function invokeWithSignal<T>(signal: AbortSignal, invoke: () => Promise<T>): Promise<T> {
  if (signal.aborted) throw abortError();
  try {
    const value = await invoke();
    if (signal.aborted) throw abortError();
    return value;
  } catch (error) {
    if (signal.aborted) throw abortError();
    throw normalizeRepositoryError(error);
  }
}

function mapSpaces(response: StudySpacesResponse): StudySpaces {
  const spaces = response.spaces.map((space) => ({
    id: space.space_id,
    title: space.title,
    status: space.status,
    isCurrent: space.is_current,
  }));
  return {
    currentSpaceId:
      response.currentSpaceId ?? spaces.find((space) => space.isCurrent)?.id ?? null,
    spaces,
  };
}

export function normalizeRepositoryError(error: unknown): StudyRepositoryError {
  if (error instanceof StudyRepositoryError) return error;
  if (isDeskBridgeErrorPayload(error)) {
    if (["desk_not_ready", "desk_auth_not_ready", "desk_transport_error"].includes(error.code)) {
      return new StudyRepositoryError("unavailable", { cause: error });
    }
    if (error.code === "study_not_found" || error.status === 404) {
      return new StudyRepositoryError("not-found", { cause: error });
    }
    if (error.code === "study_conflict" || error.status === 409) {
      return new StudyRepositoryError("conflict", { cause: error });
    }
    if (["study_invalid_request", "invalid_study_id"].includes(error.code) || error.status === 400) {
      return new StudyRepositoryError("invalid", { cause: error });
    }
    return new StudyRepositoryError("unknown", { cause: error });
  }
  const message = error instanceof Error ? error.message : String(error);
  const stablePrefix = message.split(":", 1)[0].trim().toLowerCase();

  if (
    stablePrefix === "desk_not_ready" ||
    message.startsWith("Kabuqina is not ready yet") ||
    message.startsWith("Hermes is not ready yet")
  ) {
    return new StudyRepositoryError("unavailable", { cause: error });
  }
  if (stablePrefix === "invalid study id" || stablePrefix === "invalid_study_id") {
    return new StudyRepositoryError("invalid", { cause: error });
  }
  if (stablePrefix === "study_not_found" || stablePrefix === "space_not_found") {
    return new StudyRepositoryError("not-found", { cause: error });
  }
  if (stablePrefix === "study_conflict") {
    return new StudyRepositoryError("conflict", { cause: error });
  }
  return new StudyRepositoryError("unknown", { cause: error });
}

export function createStudyRepository(commands: StudyCommands = defaultCommands): StudyRepository {
  return {
    async listSpaces(signal) {
      return mapSpaces(await invokeWithSignal(signal, commands.spaces));
    },
    async selectSpace(spaceId, signal) {
      return mapSpaces(await invokeWithSignal(signal, () => commands.selectSpace(spaceId)));
    },
    async listDrafts(spaceId, signal) {
      const response = await invokeWithSignal(signal, () => commands.draftSummary(spaceId));
      return { total: response.count, kindCounts: response.kind_counts };
    },
  };
}

export const studyRepository = createStudyRepository();
