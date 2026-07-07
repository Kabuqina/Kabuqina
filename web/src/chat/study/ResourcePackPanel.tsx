// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

// STUDY M3: renders 备课组 (导图师/影像师/阅读官) resource_pack drafts —
// mindmaps, reading lists, and video-script storyboards — as reviewable,
// cardified content, with activate/reject through the desktop learning API.

import {
  BookOpen,
  Check,
  Clapperboard,
  ListTree,
  RefreshCw,
  Sparkles,
  X,
} from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { cn } from "../../lib/cn";
import { WorkspaceSection } from "../workspaceSection";
import { STUDY_LEARNING_EVENT } from "./flashcardLearningStore";
import {
  cmdStudyArtifactActivate,
  cmdStudyArtifactReject,
  cmdStudyDrafts,
  type ResourceMindmapNode,
  type ResourcePackResource,
  type StudyArtifact,
} from "./study-api";

const TEAM_RESOURCE_PROMPT =
  "用你的学习编队，为当前课程生成一份知识点思维导图、一份拓展阅读清单，以及一段讲解动画/短视频脚本分镜。";

const TYPE_META: Record<string, { label: string; icon: typeof ListTree }> = {
  mindmap: { label: "思维导图", icon: ListTree },
  reading: { label: "拓展阅读", icon: BookOpen },
  video_script: { label: "视频脚本", icon: Clapperboard },
  doc: { label: "讲解文档", icon: BookOpen },
};

function resourceType(draft: StudyArtifact): string {
  const t = draft.payload?.resource_type;
  if (t && TYPE_META[t]) return t;
  const first = draft.payload?.resources?.[0]?.resource_type;
  return first && TYPE_META[first] ? first : "doc";
}

function MindmapNodes({ nodes, depth = 0 }: { nodes: ResourceMindmapNode[]; depth?: number }) {
  return (
    <ul className={cn("space-y-0.5", depth > 0 && "ml-3 border-l border-[var(--kq-glass-border)] pl-2")}>
      {nodes.map((n, i) => {
        const label = n.label || n.title || "";
        const children = Array.isArray(n.children) ? n.children : [];
        return (
          <li key={`${depth}-${i}-${label}`}>
            <span className="break-words text-[12px] text-[var(--kq-color-ink)]">
              {depth === 0 ? "● " : "– "}
              {label}
            </span>
            {children.length ? <MindmapNodes nodes={children} depth={depth + 1} /> : null}
          </li>
        );
      })}
    </ul>
  );
}

function toNodeArray(outline: ResourcePackResource["outline"]): ResourceMindmapNode[] {
  if (!outline) return [];
  return Array.isArray(outline) ? outline : [outline];
}

function ResourceBody({ type, resource }: { type: string; resource: ResourcePackResource }) {
  if (type === "mindmap") {
    const nodes = toNodeArray(resource.outline);
    return (
      <div className="mt-1 min-w-0">
        {nodes.length ? (
          <MindmapNodes nodes={nodes} />
        ) : resource.mermaid ? (
          <pre className="overflow-x-auto whitespace-pre-wrap break-words rounded bg-[var(--kq-glass-hover,rgba(0,0,0,0.04))] p-2 text-[11px] leading-snug">
            {resource.mermaid}
          </pre>
        ) : (
          <p className="text-[11.5px] text-[var(--kq-color-muted)]">{resource.purpose}</p>
        )}
      </div>
    );
  }
  if (type === "video_script") {
    const scenes = Array.isArray(resource.scenes) ? resource.scenes : [];
    return (
      <ol className="mt-1 space-y-1">
        {scenes.map((s, i) => (
          <li key={i} className="rounded border border-[var(--kq-glass-border)] px-2 py-1 text-[11.5px]">
            <span className="font-medium text-[var(--kq-color-ink)]">场景 {i + 1}</span>
            {s.narration ? <div className="text-[var(--kq-color-ink)]">🗣 {s.narration}</div> : null}
            {s.visual ? <div className="text-[var(--kq-color-muted)]">🎬 {s.visual}</div> : null}
          </li>
        ))}
        {!scenes.length ? (
          <li className="text-[11.5px] text-[var(--kq-color-muted)]">{resource.purpose}</li>
        ) : null}
      </ol>
    );
  }
  // reading / doc
  return (
    <div className="mt-0.5 text-[11.5px] leading-snug text-[var(--kq-color-muted)]">
      {resource.purpose ? <p className="break-words">{resource.purpose}</p> : null}
      <div className="mt-0.5 flex flex-wrap gap-x-2 gap-y-0.5">
        {resource.difficulty ? <span>难度：{resource.difficulty}</span> : null}
        {resource.reason ? <span className="break-words">理由：{resource.reason}</span> : null}
      </div>
      {resource.url ? (
        <span className="break-all text-[var(--kq-color-accent,#4466cc)]">{resource.url}</span>
      ) : null}
    </div>
  );
}

export function ResourcePackPanel({ onStartPrompt }: { onStartPrompt?: (prompt: string) => void }) {
  const [drafts, setDrafts] = useState<StudyArtifact[]>([]);
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [status, setStatus] = useState("");

  const refresh = useCallback(async () => {
    try {
      const res = await cmdStudyDrafts("resource_pack");
      setDrafts(res.drafts || []);
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
        <div className="mt-3 grid gap-1.5">
          {drafts.map((draft) => {
            const type = resourceType(draft);
            const meta = TYPE_META[type];
            const Icon = meta.icon;
            const open = expanded[draft.artifact_id];
            const resources = draft.payload?.resources || [];
            return (
              <div key={draft.artifact_id} className="kq-workspace-card overflow-hidden rounded-md px-2 py-2">
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => setExpanded((p) => ({ ...p, [draft.artifact_id]: !p[draft.artifact_id] }))}
                    className="flex min-w-0 flex-1 items-center gap-1.5 text-left"
                  >
                    <Icon className="h-3.5 w-3.5 shrink-0 text-[var(--kq-color-muted)]" aria-hidden />
                    <span className="truncate text-[12.5px] font-medium text-[var(--kq-color-ink)]">
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
                  </button>
                  {draft.status === "active" ? (
                    <span
                      className="inline-flex h-8 w-8 shrink-0 items-center justify-center text-emerald-600"
                      title="已激活"
                      aria-hidden
                    >
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
                {open ? (
                  <div className="mt-2 space-y-2 border-t border-[var(--kq-glass-border)] pt-2">
                    {resources.map((resource, i) => (
                      <div key={i} className="min-w-0">
                        <div className="break-words text-[12px] font-medium text-[var(--kq-color-ink)]">
                          {resource.title || `资源 ${i + 1}`}
                        </div>
                        <ResourceBody type={type} resource={resource} />
                      </div>
                    ))}
                    {!resources.length ? (
                      <p className="text-[11.5px] text-[var(--kq-color-muted)]">（暂无可渲染的内容字段）</p>
                    ) : null}
                  </div>
                ) : null}
              </div>
            );
          })}
        </div>
      ) : (
        <p className="mt-3 text-[12px] leading-relaxed text-[var(--kq-color-muted)]">
          还没有编队产出的资源。点上面「召集编队」，或直接对小娜说“用学习编队做一份思维导图/拓展阅读/讲解视频脚本”。
        </p>
      )}

      {status ? <div className="mt-2 text-[11.5px] text-[var(--kq-color-muted)]">{status}</div> : null}
    </WorkspaceSection>
  );
}
