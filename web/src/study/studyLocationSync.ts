// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useEffect, useRef } from "react";
import type { StudyLearningMap, StudySharedLocation } from "../chat/study/study-api";
import type { StudyRepository } from "./repository";
import {
  readStudyLocation,
  STUDY_LOCATION_EVENT,
  writeStudyLocation,
  type StudyLocation,
} from "./studyLocation";

function localProjection(
  courseId: string,
  server: StudySharedLocation,
  map: StudyLearningMap,
): StudyLocation {
  const previous = readStudyLocation(courseId);
  const core = server.knowledgeCoreId
    ? map.knowledgeCores.find((item) => item.id === server.knowledgeCoreId)
    : undefined;
  const page = server.stale || (server.page !== "plan" && !core) ? "plan" : server.page;
  const sameExercise = Boolean(
    core
    && previous?.knowledgeCoreId === core.id
    && previous.exerciseId === (server.exerciseId ?? undefined),
  );
  return {
    version: 1,
    courseId,
    page,
    ...(page !== "plan" && core ? {
      knowledgeCoreId: core.id,
      knowledgeCoreTitle: core.front,
    } : {}),
    ...(previous?.outlineLabel ? { outlineLabel: previous.outlineLabel } : {}),
    ...(server.outlineNodeId ? { outlineNodeId: server.outlineNodeId } : {}),
    ...(previous?.planItemId ? { planItemId: previous.planItemId } : {}),
    ...(page !== "plan" && server.exerciseId ? { exerciseId: server.exerciseId } : {}),
    exerciseByCore: server.exerciseByCore ?? {},
    ...(page === "practice"
      ? { activity: sameExercise ? previous?.activity ?? "ready" : "ready" as const }
      : {}),
    updatedAt: server.updatedAt,
  };
}

function wireLocation(location: StudyLocation) {
  return {
    page: location.page,
    ...(location.page !== "plan" && location.knowledgeCoreId
      ? { knowledgeCoreId: location.knowledgeCoreId }
      : {}),
    ...(location.page !== "plan" && location.exerciseId
      ? { exerciseId: location.exerciseId }
      : {}),
  };
}

/**
 * B-13: the server owns the cross-device cursor. localStorage remains a
 * best-effort recovery projection so the desk can still open while offline.
 */
export function useStudyLocationSync(
  repository: StudyRepository,
  courseId: string,
): void {
  const mapRef = useRef<StudyLearningMap | null>(null);
  const serverRef = useRef<StudySharedLocation | null>(null);
  const hydratedRef = useRef(false);
  const applyingServerRef = useRef(false);
  const queueRef = useRef(Promise.resolve());

  useEffect(() => {
    if (!repository.loadLearningMap || !repository.loadSharedLocation || !repository.saveSharedLocation) {
      return;
    }
    const controller = new AbortController();
    hydratedRef.current = false;
    mapRef.current = null;
    serverRef.current = null;

    const applyServer = (location: StudySharedLocation, map: StudyLearningMap) => {
      applyingServerRef.current = true;
      writeStudyLocation(localProjection(courseId, location, map));
      applyingServerRef.current = false;
    };

    const refreshCanonical = async () => {
      const [map, location] = await Promise.all([
        repository.loadLearningMap!(courseId, controller.signal),
        repository.loadSharedLocation!(courseId, controller.signal),
      ]);
      if (controller.signal.aborted) return;
      mapRef.current = map;
      serverRef.current = location;
      hydratedRef.current = true;
      if (location) {
        applyServer(location, map);
      } else {
        const fallback = readStudyLocation(courseId);
        if (fallback) queueSync(fallback);
      }
    };

    const queueSync = (location: StudyLocation) => {
      queueRef.current = queueRef.current.then(async () => {
        if (controller.signal.aborted || !hydratedRef.current || !mapRef.current) return;
        try {
          const saved = await repository.saveSharedLocation!({
            spaceId: courseId,
            expectedRevision: serverRef.current?.revision ?? 0,
            expectedMapRevision: mapRef.current.revision,
            ...wireLocation(location),
          }, controller.signal);
          if (controller.signal.aborted) return;
          serverRef.current = saved;
          applyServer(saved, mapRef.current);
        } catch {
          if (controller.signal.aborted) return;
          // A stale CAS or changed learning map is resolved by re-reading the
          // canonical pair. Transport failures deliberately leave the local
          // projection intact for offline recovery.
          try {
            const [map, canonical] = await Promise.all([
              repository.loadLearningMap!(courseId, controller.signal),
              repository.loadSharedLocation!(courseId, controller.signal),
            ]);
            if (controller.signal.aborted) return;
            mapRef.current = map;
            serverRef.current = canonical;
            if (canonical) applyServer(canonical, map);
          } catch {
            // Offline: local recovery remains available and will be retried by
            // the next explicit Study location change.
          }
        }
      });
    };

    const onLocationChange = (event: Event) => {
      if (applyingServerRef.current || !hydratedRef.current) return;
      const location = (event as CustomEvent<StudyLocation>).detail;
      if (!location || location.courseId !== courseId) return;
      queueSync(location);
    };

    window.addEventListener(STUDY_LOCATION_EVENT, onLocationChange);
    void refreshCanonical().catch(() => {
      hydratedRef.current = true;
      // No destructive fallback: the existing local cursor stays visible.
    });
    return () => {
      controller.abort();
      window.removeEventListener(STUDY_LOCATION_EVENT, onLocationChange);
    };
  }, [courseId, repository]);
}
