// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useCallback, useEffect, useRef, useState } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useI18n } from "../lib/i18n";
import { RequestCoordinator, type Loadable } from "./loadable";
import { useStudyRepository } from "./repositoryContext";
import type { StudyRepository, StudySpaces } from "./repository";
import { parseStudyPath, studyPath } from "./routeModel";
import { StudyShell } from "./StudyShell";
import { StudyRouteStatus } from "./StudyRouteStatus";
import { STUDY_LEARNING_EVENT } from "./learningEvent";
import type { LegacyStudyCollectionMigrationResult } from "./legacyStudyCollectionMigration";

const builtinCourseBootstraps = new WeakMap<StudyRepository, Promise<boolean>>();
const legacyCollectionBootstraps = new WeakMap<StudyRepository, Promise<LegacyStudyCollectionMigrationResult>>();

export function seedBuiltinCourseOnce(repository: StudyRepository): Promise<boolean> {
  const existing = builtinCourseBootstraps.get(repository);
  if (existing) return existing;
  const pending = repository.seedBuiltinCourse(new AbortController().signal).catch((error) => {
    if (builtinCourseBootstraps.get(repository) === pending) builtinCourseBootstraps.delete(repository);
    throw error;
  });
  builtinCourseBootstraps.set(repository, pending);
  return pending;
}

function migrateLegacyCollectionsOnce(repository: StudyRepository): Promise<LegacyStudyCollectionMigrationResult> {
  const existing = legacyCollectionBootstraps.get(repository);
  if (existing) return existing;
  const pending = repository.migrateLegacyCollections(new AbortController().signal).then(
    (result) => {
      if (result.retryNeeded && legacyCollectionBootstraps.get(repository) === pending) {
        legacyCollectionBootstraps.delete(repository);
      }
      return result;
    },
    (error) => {
      if (legacyCollectionBootstraps.get(repository) === pending) legacyCollectionBootstraps.delete(repository);
      throw error;
    },
  );
  legacyCollectionBootstraps.set(repository, pending);
  return pending;
}

export default function StudyRoute() {
  const repository = useStudyRepository();
  const location = useLocation();
  const { t } = useI18n();
  const coordinator = useRef(new RequestCoordinator());
  const bootstrapCoordinator = useRef(new RequestCoordinator());
  const [spaces, setSpaces] = useState<Loadable<StudySpaces>>({ status: "idle" });

  const load = useCallback(() => {
    const request = coordinator.current.begin();
    setSpaces((current) => ({
      status: "loading",
      ...(current.status === "ready" ? { previous: current.data } : {}),
    }));
    void repository.listSpaces(request.signal).then(
      (data) => {
        if (coordinator.current.isCurrent(request.generation)) setSpaces({ status: "ready", data });
      },
      (error) => {
        if (!coordinator.current.isCurrent(request.generation)) return;
        setSpaces((current) => ({
          status: "error",
          error,
          ...(current.status === "loading" && current.previous ? { previous: current.previous } : {}),
        }));
      },
    );
  }, [repository]);

  useEffect(() => {
    const activeCoordinator = coordinator.current;
    const activeBootstrapCoordinator = bootstrapCoordinator.current;
    load();
    window.addEventListener(STUDY_LEARNING_EVENT, load);
    const bootstrap = activeBootstrapCoordinator.begin();
    void (async () => {
      let seeded = false;
      let legacyChanged = false;
      try {
        seeded = await seedBuiltinCourseOnce(repository);
      } catch {
        // Retry on a later mount; legacy migration still gets its own attempt.
      }
      try {
        legacyChanged = (await migrateLegacyCollectionsOnce(repository)).changed;
      } catch {
        // Both bootstraps fail open and retry on a later mount.
      }
      if (activeBootstrapCoordinator.isCurrent(bootstrap.generation) && (seeded || legacyChanged)) {
        window.dispatchEvent(new Event(STUDY_LEARNING_EVENT));
      }
    })();
    return () => {
      window.removeEventListener(STUDY_LEARNING_EVENT, load);
      activeCoordinator.cancel();
      activeBootstrapCoordinator.cancel();
    };
  }, [load, repository]);

  if (spaces.status === "idle") {
    return <div className="kq-study-route-status" role="status">{t("study.loading")}</div>;
  }
  if (spaces.status === "loading" && !spaces.previous) {
    return <div className="kq-study-route-status" role="status">{t("study.loading")}</div>;
  }
  if (spaces.status === "error" && !spaces.previous) {
    return (
      <StudyRouteStatus alert>
        <h1>{t("study.unavailableTitle")}</h1>
        <p>{t("study.unavailableBody")}</p>
        <button type="button" onClick={load}>{t("study.retry")}</button>
        <a href="/chat">{t("study.backToChat")}</a>
      </StudyRouteStatus>
    );
  }

  const retainedSpaces = spaces.status === "ready" ? spaces.data : spaces.previous!;
  const route = parseStudyPath(location.pathname);
  if (route.kind === "not-found") {
    const fallbackId = route.spaceId && retainedSpaces.spaces.some((space) => space.id === route.spaceId)
      ? route.spaceId
      : retainedSpaces.currentSpaceId;
    return (
      <StudyRouteStatus>
        <h1>{t("study.notFoundTitle")}</h1>
        {fallbackId ? <a href={studyPath(fallbackId)}>{t("study.backToFlyleaf")}</a> : null}
        <a href="/chat">{t("study.backToChat")}</a>
      </StudyRouteStatus>
    );
  }
  if (route.kind === "root") {
    return retainedSpaces.currentSpaceId
      ? <Navigate to={studyPath(retainedSpaces.currentSpaceId)} replace />
      : <StudyShell
          spaces={retainedSpaces}
          onRevalidate={load}
          refreshing={spaces.status === "loading"}
          refreshFailed={spaces.status === "error"}
        />;
  }
  if (!retainedSpaces.spaces.some((space) => space.id === route.spaceId)) {
    return (
      <StudyRouteStatus>
        <h1>{t("study.spaceUnavailableTitle")}</h1>
        <p>{t("study.spaceUnavailableBody")}</p>
        <a href="/study">{t("study.openCurrentSpace")}</a>
        <a href="/chat">{t("study.backToChat")}</a>
      </StudyRouteStatus>
    );
  }
  if (route.kind === "space") {
    // 杂记本不是课程，没有五分页：它按 `/study/<id>` 直接摊开，不重定向到扉页。
    const isScratch = retainedSpaces.spaces.some(
      (space) => space.id === route.spaceId && space.kind === "scratch",
    );
    return isScratch
      ? <StudyShell
          spaces={retainedSpaces}
          spaceId={route.spaceId}
          scratch
          onRevalidate={load}
          refreshing={spaces.status === "loading"}
          refreshFailed={spaces.status === "error"}
        />
      : <Navigate to={studyPath(route.spaceId)} replace />;
  }
  // 手敲 /study/<杂记本>/practice 之类的路径：回到那本本子唯一的一页。
  if (retainedSpaces.spaces.some((space) => space.id === route.spaceId && space.kind === "scratch")) {
    return <Navigate to={`/study/${encodeURIComponent(route.spaceId)}`} replace />;
  }
  return <StudyShell
    spaces={retainedSpaces}
    spaceId={route.spaceId}
    page={route.page}
    onRevalidate={load}
    refreshing={spaces.status === "loading"}
    refreshFailed={spaces.status === "error"}
  />;
}
