// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useCallback, useEffect, useRef, useState } from "react";
import { useI18n } from "../lib/i18n";
import { RequestCoordinator, type Loadable } from "../study/loadable";
import {
  cmdStudioCreateProject,
  cmdStudioProjects,
  cmdStudioSaveBrief,
  StudioNotImplementedError,
  type StudioProject,
} from "./studio-api";
import { StudioShell } from "./StudioShell";

export default function StudioRoute() {
  const { t } = useI18n();
  const coordinator = useRef(new RequestCoordinator());
  const [state, setState] = useState<Loadable<StudioProject[]>>({ status: "idle" });
  const [currentProjectId, setCurrentProjectId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    const request = coordinator.current.begin();
    setState((current) => ({
      status: "loading",
      previous: current.status === "ready" ? current.data : undefined,
    }));
    cmdStudioProjects()
      .then((result) => {
        if (!coordinator.current.isCurrent(request.generation)) return;
        setState({ status: "ready", data: result.projects });
        setCurrentProjectId((id) => id ?? result.projects[0]?.id ?? null);
      })
      .catch((error) => {
        if (!coordinator.current.isCurrent(request.generation)) return;
        setState({ status: "error", error });
      });
  }, []);

  useEffect(() => {
    load();
    return () => coordinator.current.cancel();
  }, [load]);

  const run = (task: () => Promise<unknown>) => {
    setBusy(true);
    void task().finally(() => {
      setBusy(false);
      load();
    });
  };

  if (state.status === "idle" || state.status === "loading") {
    return <p className="kq-studio-status" role="status">{t("studio.loading")}</p>;
  }

  if (state.status === "error") {
    // 后端还没实现时说实话，不造假数据（架构 §0.3：可以降为连接验证，不可伪装成完整中心）。
    const pending = state.error instanceof StudioNotImplementedError;
    return (
      <div className="kq-studio-status" role={pending ? "status" : "alert"}>
        <h2>{t(pending ? "studio.pendingTitle" : "studio.errorTitle")}</h2>
        <p>{t(pending ? "studio.pendingLead" : "studio.errorLead")}</p>
        {pending ? null : (
          <button type="button" className="kq-studio-secondary" onClick={load}>
            {t("studio.retry")}
          </button>
        )}
      </div>
    );
  }

  return (
    <StudioShell
      projects={state.data}
      currentProjectId={currentProjectId}
      onSelectProject={setCurrentProjectId}
      onCreateProject={() =>
        run(async () => {
          const created = await cmdStudioCreateProject(t("studio.newProjectTitle"));
          setCurrentProjectId(created.id);
        })
      }
      onSaveBrief={(projectId, brief) => run(() => cmdStudioSaveBrief(projectId, brief))}
      busy={busy}
    />
  );
}
