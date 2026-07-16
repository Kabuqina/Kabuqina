// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { STUDY_LEARNING_EVENT } from "./learningEvent";
import { RequestCoordinator, type Loadable } from "./loadable";
import { normalizeRepositoryError, StudyRepositoryError, type StudyArtifactDetail, type StudyDraftPage } from "./repository";
import { useStudyRepository } from "./repositoryContext";

type DraftAction = "activate" | "reject" | "archive" | "review";

export type StudyDraftController = {
  spaceId: string;
  snapshot: Loadable<StudyDraftPage>;
  details: Readonly<Record<string, Loadable<StudyArtifactDetail>>>;
  actions: Readonly<Record<string, DraftAction | undefined>>;
  actionErrors: Readonly<Record<string, unknown>>;
  refresh: () => void;
  loadMore: () => void;
  openDetail: (artifactId: string, options?: { force?: boolean }) => void;
  invalidateArtifact: (artifactId: string) => void;
  activate: (artifactId: string) => Promise<boolean>;
  reject: (artifactId: string) => Promise<boolean>;
  archive: (artifactId: string) => Promise<boolean>;
  review: (artifactId: string) => Promise<boolean>;
};

const StudyDraftContext = createContext<StudyDraftController | null>(null);
const PAGE_SIZE = 50;

function snapshotData(snapshot: Loadable<StudyDraftPage>): StudyDraftPage | undefined {
  if (snapshot.status === "ready") return snapshot.data;
  if (snapshot.status === "loading" || snapshot.status === "error") return snapshot.previous;
  return undefined;
}

function detailLoading(current: Loadable<StudyArtifactDetail> | undefined): Loadable<StudyArtifactDetail> {
  if (current?.status === "ready") return { status: "loading", previous: current.data };
  if (current?.status === "error" && current.previous) return { status: "loading", previous: current.previous };
  return { status: "loading" };
}

export function StudyDraftProvider({ spaceId, children }: { spaceId: string; children: ReactNode }) {
  const repository = useStudyRepository();
  const listRequests = useRef(new RequestCoordinator());
  const loadMoreRequests = useRef(new RequestCoordinator());
  const detailRequests = useRef(new Map<string, RequestCoordinator>());
  const actionRequests = useRef(new Map<string, RequestCoordinator>());
  const currentSpaceId = useRef(spaceId);
  const [snapshot, setSnapshot] = useState<Loadable<StudyDraftPage>>({ status: "idle" });
  const [details, setDetails] = useState<Record<string, Loadable<StudyArtifactDetail>>>({});
  const [actions, setActions] = useState<Record<string, DraftAction | undefined>>({});
  const [actionErrors, setActionErrors] = useState<Record<string, unknown>>({});

  const refresh = useCallback(() => {
    // A refreshed first page invalidates every pagination cursor derived from
    // the previous snapshot. Abort those requests before replacing page one.
    loadMoreRequests.current.cancel();
    const request = listRequests.current.begin();
    setSnapshot((current) => ({
      status: "loading",
      ...(current.status === "ready" ? { previous: current.data } : {}),
      ...(current.status === "error" && current.previous ? { previous: current.previous } : {}),
    }));
    void repository.listDraftPage(spaceId, PAGE_SIZE, 0, request.signal).then(
      (next) => {
        if (!listRequests.current.isCurrent(request.generation) || currentSpaceId.current !== spaceId) return;
        setSnapshot({ status: "ready", data: next });
      },
      (error) => {
        if (!listRequests.current.isCurrent(request.generation) || currentSpaceId.current !== spaceId) return;
        setSnapshot((current) => ({
          status: "error",
          error,
          ...(current.status === "loading" && current.previous ? { previous: current.previous } : {}),
        }));
      },
    );
  }, [repository, spaceId]);

  const loadMore = useCallback(() => {
    // Never derive an offset from `previous` while a first-page refresh is in
    // flight: that cursor belongs to the snapshot being replaced.
    if (snapshot.status !== "ready") return;
    const current = snapshot.data;
    if (!current || !current.truncated) return;
    const request = loadMoreRequests.current.begin();
    void repository.listDraftPage(spaceId, PAGE_SIZE, current.items.length, request.signal).then(
      (next) => {
        if (!loadMoreRequests.current.isCurrent(request.generation) || currentSpaceId.current !== spaceId) return;
        setSnapshot((existing) => {
          const prior = snapshotData(existing);
          if (!prior) return existing;
          const items = [...prior.items, ...next.items.filter((item) => !prior.items.some((old) => old.artifact_id === item.artifact_id))];
          return {
            status: "ready",
            data: {
              ...next,
              items,
              returned: items.length,
              offset: 0,
              truncated: items.length < next.total,
            },
          };
        });
      },
      () => undefined,
    );
  }, [repository, snapshot, spaceId]);

  const invalidateArtifact = useCallback((artifactId: string) => {
    if (!artifactId) return;
    detailRequests.current.get(artifactId)?.cancel();
    detailRequests.current.delete(artifactId);
    actionRequests.current.get(artifactId)?.cancel();
    actionRequests.current.delete(artifactId);
    // Keep a body-free tombstone until the stale summary disappears. Automatic
    // detail effects will not retry an error entry, while explicit retries can
    // still pass force: true.
    setDetails((previous) => ({
      ...previous,
      [artifactId]: { status: "error", error: new StudyRepositoryError("not-found") },
    }));
    setActions((previous) => {
      const next = { ...previous };
      delete next[artifactId];
      return next;
    });
    setActionErrors((previous) => {
      const next = { ...previous };
      delete next[artifactId];
      return next;
    });
    window.dispatchEvent(new Event(STUDY_LEARNING_EVENT));
  }, []);

  const openDetail = useCallback((artifactId: string, options?: { force?: boolean }) => {
    if (!artifactId) return;
    const current = details[artifactId];
    if (!options?.force && (current?.status === "ready" || current?.status === "loading" || current?.status === "error")) return;
    const requests = detailRequests.current.get(artifactId) ?? new RequestCoordinator();
    detailRequests.current.set(artifactId, requests);
    const request = requests.begin();
    setDetails((previous) => ({ ...previous, [artifactId]: detailLoading(previous[artifactId]) }));
    void repository.loadArtifactDetail(spaceId, artifactId, request.signal).then(
      (detail) => {
        if (!requests.isCurrent(request.generation) || currentSpaceId.current !== spaceId) return;
        setDetails((previous) => ({ ...previous, [artifactId]: { status: "ready", data: detail } }));
      },
      (error) => {
        if (!requests.isCurrent(request.generation) || currentSpaceId.current !== spaceId) return;
        if (normalizeRepositoryError(error).code === "not-found") {
          invalidateArtifact(artifactId);
          return;
        }
        setDetails((previous) => {
          const prior = previous[artifactId];
          return {
            ...previous,
            [artifactId]: {
              status: "error",
              error,
              ...(prior?.status === "loading" && prior.previous ? { previous: prior.previous } : {}),
            },
          };
        });
      },
    );
  }, [details, invalidateArtifact, repository, spaceId]);

  const mutate = useCallback((artifactId: string, action: DraftAction): Promise<boolean> => {
    if (!artifactId || actions[artifactId]) return Promise.resolve(false);
    const requests = actionRequests.current.get(artifactId) ?? new RequestCoordinator();
    actionRequests.current.set(artifactId, requests);
    const request = requests.begin();
    setActions((previous) => ({ ...previous, [artifactId]: action }));
    setActionErrors((previous) => {
      const next = { ...previous };
      delete next[artifactId];
      return next;
    });
    const operation = action === "review"
      ? repository.runSemanticReview(spaceId, artifactId, request.signal)
      : repository.setArtifactStatus(
        spaceId,
        artifactId,
        action === "activate" ? "active" : action === "reject" ? "rejected" : "archived",
        request.signal,
      );
    return operation.then(
      () => {
        if (!requests.isCurrent(request.generation) || currentSpaceId.current !== spaceId) return false;
        setActions((previous) => ({ ...previous, [artifactId]: undefined }));
        setDetails((previous) => {
          const next = { ...previous };
          delete next[artifactId];
          return next;
        });
        window.dispatchEvent(new Event(STUDY_LEARNING_EVENT));
        return true;
      },
      (error) => {
        if (!requests.isCurrent(request.generation) || currentSpaceId.current !== spaceId) return false;
        setActions((previous) => ({ ...previous, [artifactId]: undefined }));
        setActionErrors((previous) => ({ ...previous, [artifactId]: error }));
        return false;
      },
    );
  }, [actions, repository, spaceId]);

  useEffect(() => {
    const activeListRequests = listRequests.current;
    const activeLoadMoreRequests = loadMoreRequests.current;
    const activeDetailRequests = detailRequests.current;
    const activeActionRequests = actionRequests.current;
    currentSpaceId.current = spaceId;
    activeListRequests.cancel();
    activeLoadMoreRequests.cancel();
    activeDetailRequests.forEach((requests) => requests.cancel());
    activeActionRequests.forEach((requests) => requests.cancel());
    activeDetailRequests.clear();
    activeActionRequests.clear();
    setDetails({});
    setActions({});
    setActionErrors({});
    setSnapshot({ status: "idle" });
    refresh();
    const onLearningEvent = () => refresh();
    window.addEventListener(STUDY_LEARNING_EVENT, onLearningEvent);
    return () => {
      window.removeEventListener(STUDY_LEARNING_EVENT, onLearningEvent);
      activeListRequests.cancel();
      activeLoadMoreRequests.cancel();
      activeDetailRequests.forEach((requests) => requests.cancel());
      activeActionRequests.forEach((requests) => requests.cancel());
    };
  }, [refresh, spaceId]);

  const value = useMemo<StudyDraftController>(() => ({
    spaceId,
    snapshot,
    details,
    actions,
    actionErrors,
    refresh,
    loadMore,
    openDetail,
    invalidateArtifact,
    activate: (artifactId) => mutate(artifactId, "activate"),
    reject: (artifactId) => mutate(artifactId, "reject"),
    archive: (artifactId) => mutate(artifactId, "archive"),
    review: (artifactId) => mutate(artifactId, "review"),
  }), [actionErrors, actions, details, invalidateArtifact, loadMore, mutate, openDetail, refresh, snapshot, spaceId]);

  return <StudyDraftContext.Provider value={value}>{children}</StudyDraftContext.Provider>;
}

export function useStudyDrafts(): StudyDraftController {
  const value = useContext(StudyDraftContext);
  if (!value) throw new Error("StudyDraftProvider is required");
  return value;
}
