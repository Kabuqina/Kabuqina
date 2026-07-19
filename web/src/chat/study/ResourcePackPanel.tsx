// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import {
  BookOpen,
  Check,
  Clapperboard,
  ExternalLink,
  ListTree,
  RefreshCw,
  Sparkles,
  X,
} from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { cn } from "../../lib/cn";
import { WorkspaceSection } from "../workspaceSection";
import { STUDY_LEARNING_EVENT } from "./flashcardLearningStore";
import { resourcePackKind } from "./ResourceRenderer";
import {
  cmdStudyArtifactActivate,
  cmdStudyArtifactReject,
  cmdStudyDrafts,
  type StudyArtifact,
} from "./study-api";

const TEAM_RESOURCE_PROMPT = [
  "用你的学习编队，为当前课程生成一组个性化多模态学习资源，包括适合主题的知识讲解、思维导图、拓展阅读或视频脚本。",
  "请在信息足够时使用 STUDY learning 工具创建 kind=resource_pack 草稿；payload.resources 中每项写明 title、purpose、resource_type，并为讲解内容提供 content_markdown。不要把资源 JSON 贴到聊天里。",
  "创建后提醒我在多模态资源产出区审核；资源会保留在侧栏，并可打开独立详情页阅读。",
].join("\n\n");

const TYPE_META: Record<string, { label: string; icon: typeof ListTree }> = {
  mindmap: { label: "思维导图", icon: ListTree },
  reading: { label: "拓展阅读", icon: BookOpen },
  video_script: { label: "视频脚本", icon: Clapperboard },
  doc: { label: "讲解文档", icon: BookOpen },
};

export function ResourcePackPanel({ onStartPrompt }: { onStartPrompt?: (prompt: string) => void }) {
  const nav = useNavigate();
  const [drafts, setDrafts] = useState<StudyArtifact[]>([]);
  const [status, setStatus] = useState("");

  const refresh = useCallback(async () => {
    try {
      const result = await cmdStudyDrafts("resource_pack");
      setDrafts(result.drafts || []);
      setStatus("");
    } catch (error) {
      setStatus("后端暂不可用");
      console.debug("resource_pack drafts refresh failed:", error);
    }
  }, []);

  useEffect(() => {
    void refresh();
    const onLearning = () => void refresh().catch(() => undefined);
    window.addEventListener(STUDY_LEARNING_EVENT, onLearning);
    return () => window.removeEventListener(STUDY_LEARNING_EVENT, onLearning);
  }, [refresh]);

  const act = async (fn: (id: string) => Promise<unknown>, id: string) => {
    try {
      await fn(id);
      await refresh();
    } catch (error) {
      setStatus("操作失败");
      console.debug("resource_pack action failed:", error);
    }
  };

  return (
    <WorkspaceSection sectionId="workspace.resourcePack" title="多模态资源（编队产出）" dotColor="#7c5cff">
      <div className="mt-2 flex items-center gap-2">
        <button
          type="button"
          onClick={() => onStartPrompt?.(TEAM_RESOURCE_PROMPT)}
          className="kq-quick-action inline-flex flex-1 items-center justify-center gap-1.5 rounded-[10px] px-2.5 py-2 text-[12.5px] leading-snug transition"
        >
          <Sparkles className="h-3.5 w-3.5" aria-hidden />
          召集编队生成资源
        </button>
        <button
          type="button"
          onClick={() => void refresh()}
          className="kq-soft-icon-btn inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-md transition"
          aria-label="刷新"
          title="刷新"
        >
          <RefreshCw className="h-3.5 w-3.5" aria-hidden />
        </button>
      </div>

      {drafts.length ? (
        <div className="mt-3 grid grid-cols-1 gap-1.5">
          {drafts.map((draft) => {
            const kind = resourcePackKind(draft);
            const meta = TYPE_META[kind] || TYPE_META.doc;
            const Icon = meta.icon;
            return (
              <div key={draft.artifact_id} className="kq-workspace-card rounded-md px-2 py-2">
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => nav(`/study/resources/${encodeURIComponent(draft.artifact_id)}`)}
                    className="group flex min-w-0 flex-1 items-center gap-1.5 text-left"
                    aria-label={`打开资源：${draft.title}`}
                  >
                    <Icon className="h-3.5 w-3.5 shrink-0 text-[var(--kq-color-muted)]" aria-hidden />
                    <span className="truncate text-[12.5px] font-medium text-[var(--kq-color-ink)] group-hover:underline">
                      {draft.title}
                    </span>
                    <span className="shrink-0 rounded-full bg-[var(--kq-glass-hover,rgba(0,0,0,0.04))] px-1.5 py-px text-[10px] text-[var(--kq-color-muted)]">
                      {meta.label}
                    </span>
                    <span
                      className={cn(
                        "shrink-0 rounded-full px-1.5 py-px text-[10px]",
                        draft.status === "active"
                          ? "bg-emerald-500/15 text-emerald-600"
                          : "bg-[var(--kq-glass-hover,rgba(0,0,0,0.04))] text-[var(--kq-color-muted)]",
                      )}
                    >
                      {draft.status === "active" ? "已激活" : "待审核"}
                    </span>
                    <ExternalLink className="h-3 w-3 shrink-0 text-[var(--kq-color-muted)] opacity-60" aria-hidden />
                  </button>
                  {draft.status === "active" ? (
                    <span className="inline-flex h-8 w-8 shrink-0 items-center justify-center text-emerald-600" title="已激活" aria-hidden>
                      <Check className="h-3.5 w-3.5" />
                    </span>
                  ) : (
                    <>
                      <button
                        type="button"
                        onClick={() => void act(cmdStudyArtifactActivate, draft.artifact_id)}
                        className="kq-soft-icon-btn inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-md transition"
                        aria-label="激活"
                        title="激活"
                      >
                        <Check className="h-3.5 w-3.5" aria-hidden />
                      </button>
                      <button
                        type="button"
                        onClick={() => void act(cmdStudyArtifactReject, draft.artifact_id)}
                        className="kq-soft-icon-btn inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-md transition"
                        aria-label="驳回"
                        title="驳回"
                      >
                        <X className="h-3.5 w-3.5" aria-hidden />
                      </button>
                    </>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <p className="mt-3 text-[12px] leading-relaxed text-[var(--kq-color-muted)]">
          还没有编队产出的资源。点上面「召集编队」，或直接对小娜说“用学习编队做一份思维导图、拓展阅读或讲解视频脚本”。
        </p>
      )}

      {status ? <div className="mt-2 text-[11.5px] text-[var(--kq-color-muted)]">{status}</div> : null}
    </WorkspaceSection>
  );
}
