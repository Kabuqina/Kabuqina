// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useEffect, useState } from "react";
import { X } from "lucide-react";
import { useI18n } from "../lib/i18n";
import {
  cmdStudyArtifactSummaries,
  cmdStudySpaces,
  type StudyArtifactSummary,
  type StudySpace,
} from "../chat/study/study-api";
import { cmdStudioGatherSources, StudioNotImplementedError, type StudioSourceRef } from "./studio-api";

/**
 * 取材（架构 §4.1）。**方向很重要：Study 不向外推送，Studio 在需要素材时来取**，
 * 所以这个流程只能从 Studio 侧发起，Study 里没有"发送到 Studio"的按钮。
 *
 *   选课程 → 选内容 → **预览将取走什么** → 创建只读快照 → 回到项目
 *
 * 预览那一步不是礼貌性确认，是这条合同的核心：学生必须在快照生成前看清
 * 到底什么会被带走。取走的是**只读快照**，课程本原件不动，也不会因此变成学习证据。
 */
export function GatherFromStudy({
  projectId,
  onClose,
  onGathered,
}: {
  projectId: string;
  onClose: () => void;
  onGathered: () => void;
}) {
  const { t } = useI18n();
  const [spaces, setSpaces] = useState<StudySpace[] | null>(null);
  const [spaceId, setSpaceId] = useState<string | null>(null);
  const [artifacts, setArtifacts] = useState<StudyArtifactSummary[] | null>(null);
  const [picked, setPicked] = useState<Set<string>>(new Set());
  const [step, setStep] = useState<"pick" | "preview">("pick");
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState<"pending" | "generic" | null>(null);

  useEffect(() => {
    cmdStudySpaces()
      .then((result) => {
        setSpaces(result.spaces);
        setSpaceId((current) => current ?? result.spaces[0]?.space_id ?? null);
      })
      .catch(() => setFailure("generic"));
  }, []);

  useEffect(() => {
    if (!spaceId) return;
    setArtifacts(null);
    setPicked(new Set());
    cmdStudyArtifactSummaries({ spaceId, status: "active" })
      .then((result) => setArtifacts(result.items))
      .catch(() => setFailure("generic"));
  }, [spaceId]);

  const space = spaces?.find((s) => s.space_id === spaceId) ?? null;
  const chosen = (artifacts ?? []).filter((a) => picked.has(a.artifact_id));

  const toggle = (id: string) =>
    setPicked((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  const confirm = () => {
    setBusy(true);
    setFailure(null);
    const refs: StudioSourceRef[] = chosen.map((artifact) => ({
      kind: "study_artifact",
      spaceId: spaceId!,
      artifactId: artifact.artifact_id,
    }));
    cmdStudioGatherSources(projectId, refs)
      .then(() => {
        onGathered();
        onClose();
      })
      .catch((error) => {
        setFailure(error instanceof StudioNotImplementedError ? "pending" : "generic");
      })
      .finally(() => setBusy(false));
  };

  return (
    <div className="kq-studio-dialog-backdrop" role="presentation">
      <section
        className="kq-studio-dialog"
        role="dialog"
        aria-modal="true"
        aria-label={t("studio.gatherCta")}
      >
        <header>
          <h2>{t("studio.gatherCta")}</h2>
          <button type="button" onClick={onClose} aria-label={t("studio.gatherCancel")}>
            <X aria-hidden />
          </button>
        </header>

        {failure ? (
          <p className="kq-studio-dialog-error" role={failure === "pending" ? "status" : "alert"}>
            {t(failure === "pending" ? "studio.gatherPendingBackend" : "studio.gatherFailed")}
          </p>
        ) : null}

        {step === "pick" ? (
          <>
            <label className="kq-studio-field">
              <span>{t("studio.gatherCourse")}</span>
              <select
                value={spaceId ?? ""}
                onChange={(event) => setSpaceId(event.currentTarget.value)}
                disabled={!spaces?.length}
              >
                {(spaces ?? []).map((s) => (
                  <option key={s.space_id} value={s.space_id}>
                    {s.title}
                  </option>
                ))}
              </select>
            </label>

            {artifacts === null ? (
              <p className="kq-studio-muted">{t("studio.gatherLoading")}</p>
            ) : artifacts.length ? (
              <ul className="kq-studio-pick-list">
                {artifacts.map((artifact) => (
                  <li key={artifact.artifact_id}>
                    <label>
                      <input
                        type="checkbox"
                        checked={picked.has(artifact.artifact_id)}
                        onChange={() => toggle(artifact.artifact_id)}
                      />
                      <span>
                        <strong>{artifact.title}</strong>
                        <small>{artifact.kind}</small>
                      </span>
                    </label>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="kq-studio-muted">{t("studio.gatherNothing")}</p>
            )}

            <div className="kq-studio-actions">
              <button
                type="button"
                className="kq-studio-primary"
                disabled={!picked.size}
                onClick={() => setStep("preview")}
              >
                {t("studio.gatherNext")}
              </button>
            </div>
          </>
        ) : (
          <>
            {/* 预览：把将要生成的快照逐条摊开，别让学生在不知情下带走东西。 */}
            <p className="kq-studio-muted">{t("studio.gatherPreviewLead")}</p>
            <ul className="kq-studio-preview-list">
              {chosen.map((artifact) => (
                <li key={artifact.artifact_id}>
                  <strong>{artifact.title}</strong>
                  <small>
                    {space?.title ?? ""} · {artifact.kind}
                  </small>
                </li>
              ))}
            </ul>
            <p className="kq-studio-readonly-note">{t("studio.gatherReadOnly")}</p>
            <div className="kq-studio-actions">
              <button type="button" className="kq-studio-secondary" onClick={() => setStep("pick")}>
                {t("studio.gatherBack")}
              </button>
              <button type="button" className="kq-studio-primary" disabled={busy} onClick={confirm}>
                {t("studio.gatherConfirm", { count: chosen.length })}
              </button>
            </div>
          </>
        )}
      </section>
    </div>
  );
}
