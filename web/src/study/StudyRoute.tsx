// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useCallback, useEffect, useRef, useState } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useI18n } from "../lib/i18n";
import { RequestCoordinator, type Loadable } from "./loadable";
import { useStudyRepository } from "./repositoryContext";
import type { StudySpaces } from "./repository";
import { parseStudyPath, studyPath } from "./routeModel";
import { StudyShell } from "./StudyShell";
import { StudyRouteStatus } from "./StudyRouteStatus";

export default function StudyRoute() {
  const repository = useStudyRepository();
  const location = useLocation();
  const { t } = useI18n();
  const coordinator = useRef(new RequestCoordinator());
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
    load();
    return () => activeCoordinator.cancel();
  }, [load]);

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
  if (route.kind === "space") return <Navigate to={studyPath(route.spaceId)} replace />;
  return <StudyShell
    spaces={retainedSpaces}
    spaceId={route.spaceId}
    page={route.page}
    onRevalidate={load}
    refreshing={spaces.status === "loading"}
    refreshFailed={spaces.status === "error"}
  />;
}
