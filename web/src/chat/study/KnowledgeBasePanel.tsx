// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { Check, Network, RefreshCw, Sparkles, X } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useI18n } from "../../lib/i18n";
import { WorkspaceSection } from "../workspaceSection";
import { STUDY_LEARNING_EVENT } from "./flashcardLearningStore";
import { COURSE_KNOWLEDGE_BASE_PROMPT } from "./studyPrompts";
import {
  cmdStudyArtifactActivate,
  cmdStudyArtifactReject,
  cmdStudyDrafts,
  type StudyArtifact,
} from "./study-api";

export function KnowledgeBasePanel({ onStartPrompt }: { onStartPrompt?: (prompt: string) => void }) {
  const { locale } = useI18n();
  const nav = useNavigate();
  const [artifacts, setArtifacts] = useState<StudyArtifact[]>([]);
  const [status, setStatus] = useState("");

  const refresh = useCallback(async () => {
    try {
      const result = await cmdStudyDrafts("knowledge_base");
      setArtifacts(result.drafts || []);
      setStatus("");
    } catch (error) {
      setStatus(locale === "en" ? "Knowledge bases are unavailable." : "知识库暂时无法加载");
      console.debug("knowledge base refresh failed:", error);
    }
  }, [locale]);

  useEffect(() => {
    void refresh();
    const onLearning = () => void refresh().catch(() => undefined);
    window.addEventListener(STUDY_LEARNING_EVENT, onLearning);
    return () => window.removeEventListener(STUDY_LEARNING_EVENT, onLearning);
  }, [refresh]);

  const transition = async (operation: (id: string) => Promise<unknown>, artifactId: string) => {
    try {
      await operation(artifactId);
      await refresh();
    } catch (error) {
      setStatus(locale === "en" ? "Operation failed. Try again." : "操作失败，请重试");
      console.debug("knowledge base transition failed:", error);
    }
  };

  return (
    <WorkspaceSection sectionId="workspace.knowledgeBase" title={locale === "en" ? "Course knowledge base" : "课程知识库"} dotColor="#3b82f6">
      <div className="mt-2 grid grid-cols-2 gap-2">
        <button
          type="button"
          onClick={() => onStartPrompt?.(COURSE_KNOWLEDGE_BASE_PROMPT)}
          className="kq-quick-action inline-flex min-w-0 items-center justify-center gap-1.5 rounded-[10px] px-2 py-2 text-[12px] leading-snug transition"
        >
          <Sparkles className="h-3.5 w-3.5 shrink-0" />
          <span className="truncate">{locale === "en" ? "Build knowledge base" : "构建课程知识库"}</span>
        </button>
        <button
          type="button"
          onClick={() => nav("/study/knowledge-graph")}
          className="kq-quick-action inline-flex min-w-0 items-center justify-center gap-1.5 rounded-[10px] px-2 py-2 text-[12px] leading-snug transition"
        >
          <Network className="h-3.5 w-3.5 shrink-0" />
          <span className="truncate">{locale === "en" ? "Open graph" : "查看知识图谱"}</span>
        </button>
      </div>
      <div className="mt-2 flex justify-end">
        <button type="button" onClick={() => void refresh()} className="kq-soft-icon-btn rounded-md p-2" aria-label={locale === "en" ? "Refresh knowledge bases" : "刷新知识库"}>
          <RefreshCw className="h-3.5 w-3.5" />
        </button>
      </div>

      {artifacts.length ? (
        <div className="mt-1 space-y-2">
          {artifacts.map((artifact) => {
            const conceptCount = artifact.payload?.concepts?.length || 0;
            return (
              <div key={artifact.artifact_id} className="kq-workspace-card rounded-lg px-2.5 py-2">
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => artifact.status === "active" && nav("/study/knowledge-graph")}
                    className="min-w-0 flex-1 text-left"
                    title={artifact.title}
                  >
                    <div className="truncate text-[12.5px] font-medium text-[var(--kq-color-ink)]">{artifact.title}</div>
                    <div className="mt-0.5 text-[10.5px] text-[var(--kq-color-muted)]">
                      {locale === "en" ? `${conceptCount} concepts` : `${conceptCount} 个知识点`} · {artifact.status === "active" ? (locale === "en" ? "Active" : "已激活") : (locale === "en" ? "Pending review" : "待审核")}
                    </div>
                  </button>
                  {artifact.status === "active" ? (
                    <Check className="h-4 w-4 shrink-0 text-emerald-600" aria-label="已激活" />
                  ) : (
                    <>
                      <button
                        type="button"
                        onClick={() => void transition(cmdStudyArtifactActivate, artifact.artifact_id)}
                        className="kq-soft-icon-btn rounded-md p-2"
                        aria-label={locale === "en" ? "Activate knowledge base" : "激活知识库"}
                        title={locale === "en" ? "Activate knowledge base" : "激活知识库"}
                      >
                        <Check className="h-3.5 w-3.5" />
                      </button>
                      <button
                        type="button"
                        onClick={() => void transition(cmdStudyArtifactReject, artifact.artifact_id)}
                        className="kq-soft-icon-btn rounded-md p-2"
                        aria-label={locale === "en" ? "Reject knowledge base" : "驳回知识库"}
                        title={locale === "en" ? "Reject knowledge base" : "驳回知识库"}
                      >
                        <X className="h-3.5 w-3.5" />
                      </button>
                    </>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <p className="mt-2 text-[12px] leading-relaxed text-[var(--kq-color-muted)]">
          {locale === "en"
            ? "No knowledge base yet. Generate and activate one here; the graph only shows reviewed concepts."
            : "还没有知识库。生成后先在这里审核激活，图谱只展示已确认的知识点关系。"}
        </p>
      )}
      {status ? <p className="mt-2 text-[11px] text-amber-700 dark:text-amber-300">{status}</p> : null}
    </WorkspaceSection>
  );
}
