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
        if (coordinator.current.isCurrent(request.generation)) setSpaces({ status: "error", error });
      },
    );
  }, [repository]);

  useEffect(() => {
    load();
    return () => coordinator.current.cancel();
  }, [load]);

  if (spaces.status === "idle" || spaces.status === "loading") {
    return <div className="kq-study-route-status" role="status">{t("study.loading")}</div>;
  }
  if (spaces.status === "error") {
    return (
      <main className="kq-study-route-status" role="alert">
        <h1>{t("study.unavailableTitle")}</h1>
        <p>{t("study.unavailableBody")}</p>
        <button type="button" onClick={load}>{t("study.retry")}</button>
        <a href="/chat">{t("study.backToChat")}</a>
      </main>
    );
  }

  const route = parseStudyPath(location.pathname);
  if (route.kind === "not-found") {
    const fallbackId = route.spaceId && spaces.data.spaces.some((space) => space.id === route.spaceId)
      ? route.spaceId
      : spaces.data.currentSpaceId;
    return (
      <main className="kq-study-route-status">
        <h1>{t("study.notFoundTitle")}</h1>
        {fallbackId ? <a href={studyPath(fallbackId)}>{t("study.backToFlyleaf")}</a> : null}
        <a href="/chat">{t("study.backToChat")}</a>
      </main>
    );
  }
  if (route.kind === "root") {
    return spaces.data.currentSpaceId
      ? <Navigate to={studyPath(spaces.data.currentSpaceId)} replace />
      : <StudyShell spaces={spaces.data} />;
  }
  if (!spaces.data.spaces.some((space) => space.id === route.spaceId)) {
    return (
      <main className="kq-study-route-status">
        <h1>{t("study.spaceUnavailableTitle")}</h1>
        <p>{t("study.spaceUnavailableBody")}</p>
        <a href="/study">{t("study.openCurrentSpace")}</a>
        <a href="/chat">{t("study.backToChat")}</a>
      </main>
    );
  }
  if (route.kind === "space") return <Navigate to={studyPath(route.spaceId)} replace />;
  return <StudyShell spaces={spaces.data} spaceId={route.spaceId} page={route.page} />;
}
