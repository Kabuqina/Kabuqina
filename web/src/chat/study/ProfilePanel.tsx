// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

// STUDY M1: 6-dimension learning profile (学习画像). Renders the active/latest
// student_state artifact as a dependency-free SVG radar + per-dimension detail,
// with activate/reject. Levels are a dynamic, editable snapshot (not a fixed
// ability label — see learning_contract._v_student_state).

import { Check, RefreshCw, UserRoundCog, X } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { WorkspaceSection } from "../workspaceSection";
import { STUDY_LEARNING_EVENT } from "./flashcardLearningStore";
import { LEARNING_PROFILE_PROMPT } from "./studyPrompts";
import {
  cmdStudyArtifactActivate,
  cmdStudyArtifactReject,
  cmdStudyDrafts,
  type ProfileDimension,
  type StudyArtifact,
} from "./study-api";

// Fixed axis order + short radar labels; payload dims are matched by key.
const AXES: { key: string; label: string }[] = [
  { key: "foundation", label: "知识基础" },
  { key: "cognitive_style", label: "认知风格" },
  { key: "weak_points", label: "易错点" },
  { key: "goal", label: "学习目标" },
  { key: "pace", label: "节奏进度" },
  { key: "interest", label: "兴趣方向" },
];

const CX = 100;
const CY = 96;
const R = 58;
const MAX = 5;

function point(axisIndex: number, ratio: number): [number, number] {
  const angle = ((-90 + axisIndex * (360 / AXES.length)) * Math.PI) / 180;
  return [CX + R * ratio * Math.cos(angle), CY + R * ratio * Math.sin(angle)];
}

function polygon(ratios: number[]): string {
  return ratios.map((r, i) => point(i, r).join(",")).join(" ");
}

function pickCurrent(items: StudyArtifact[]): StudyArtifact | null {
  if (!items.length) return null;
  const byRecent = [...items].sort((a, b) =>
    String(b.updated_at || "").localeCompare(String(a.updated_at || "")),
  );
  return byRecent.find((a) => a.status === "active") || byRecent[0];
}

function ProfileRadar({ dims }: { dims: Record<string, ProfileDimension> }) {
  const ratios = AXES.map((ax) => {
    const lvl = Number(dims[ax.key]?.level ?? 0);
    return Math.max(0, Math.min(MAX, lvl)) / MAX;
  });
  const rings = [0.34, 0.67, 1];
  return (
    <svg viewBox="0 0 200 200" className="w-full max-w-[220px]" role="img" aria-label="学习画像雷达图">
      {rings.map((f) => (
        <polygon
          key={f}
          points={polygon(AXES.map(() => f))}
          fill="none"
          stroke="var(--kq-glass-border,#e5e7eb)"
          strokeWidth="1"
        />
      ))}
      {AXES.map((ax, i) => {
        const [x, y] = point(i, 1);
        const [lx, ly] = point(i, 1.22);
        return (
          <g key={ax.key}>
            <line x1={CX} y1={CY} x2={x} y2={y} stroke="var(--kq-glass-border,#e5e7eb)" strokeWidth="1" />
            <text
              x={lx}
              y={ly}
              fontSize="9"
              fill="var(--kq-color-muted,#98a2b3)"
              textAnchor={lx > CX + 2 ? "start" : lx < CX - 2 ? "end" : "middle"}
              dominantBaseline="middle"
            >
              {ax.label}
            </text>
          </g>
        );
      })}
      <polygon
        points={polygon(ratios)}
        fill="rgba(124,92,255,0.18)"
        stroke="#7c5cff"
        strokeWidth="1.5"
      />
      {ratios.map((r, i) => {
        const [x, y] = point(i, r);
        return <circle key={i} cx={x} cy={y} r="2" fill="#7c5cff" />;
      })}
    </svg>
  );
}

export function ProfilePanel({ onStartPrompt }: { onStartPrompt?: (prompt: string) => void }) {
  const [profile, setProfile] = useState<StudyArtifact | null>(null);
  const [status, setStatus] = useState("");

  const refresh = useCallback(async () => {
    try {
      const res = await cmdStudyDrafts("student_state");
      setProfile(pickCurrent(res.drafts || []));
    } catch (error) {
      setStatus("后端暂不可用");
      console.debug("profile refresh failed:", error);
    }
  }, []);

  useEffect(() => {
    void refresh();
    const onLearning = () => void refresh().catch(() => undefined);
    window.addEventListener(STUDY_LEARNING_EVENT, onLearning);
    return () => window.removeEventListener(STUDY_LEARNING_EVENT, onLearning);
  }, [refresh]);

  const dimsByKey = useMemo(() => {
    const map: Record<string, ProfileDimension> = {};
    for (const d of profile?.payload?.dimensions || []) {
      if (d?.key) map[d.key] = d;
    }
    return map;
  }, [profile]);

  const act = async (fn: (id: string) => Promise<unknown>) => {
    if (!profile) return;
    try {
      await fn(profile.artifact_id);
      await refresh();
    } catch (error) {
      setStatus("操作失败");
      console.debug("profile action failed:", error);
    }
  };

  const hasDims = (profile?.payload?.dimensions || []).length > 0;

  return (
    <WorkspaceSection sectionId="workspace.profile" title="学习画像（6 维）" dotColor="#7c5cff">
      <div className="mt-2 flex items-center gap-2">
        <button
          type="button"
          onClick={() => onStartPrompt?.(LEARNING_PROFILE_PROMPT)}
          className="kq-quick-action inline-flex flex-1 items-center justify-center gap-1.5 rounded-[10px] px-2.5 py-2 text-[12.5px] leading-snug transition"
        >
          <UserRoundCog className="h-3.5 w-3.5" aria-hidden />
          {profile ? "更新学习画像" : "构建学习画像"}
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

      {profile && hasDims ? (
        <div className="mt-3">
          <div className="flex items-center justify-between">
            <span className="truncate text-[12.5px] font-medium text-[var(--kq-color-ink)]" title={profile.title}>
              {profile.title}
            </span>
            <span
              className={
                profile.status === "active"
                  ? "shrink-0 rounded-full bg-emerald-500/15 px-1.5 py-px text-[10px] text-emerald-600"
                  : "shrink-0 rounded-full bg-[var(--kq-glass-hover,rgba(0,0,0,0.04))] px-1.5 py-px text-[10px] text-[var(--kq-color-muted)]"
              }
            >
              {profile.status === "active" ? "已激活" : "待审核"}
            </span>
          </div>

          <div className="mt-1 flex justify-center">
            <ProfileRadar dims={dimsByKey} />
          </div>

          <ul className="mt-1 grid grid-cols-1 gap-1.5">
            {AXES.map((ax) => {
              const d = dimsByKey[ax.key];
              return (
                <li key={ax.key} className="min-w-0">
                  <div className="flex items-baseline gap-1.5">
                    <span className="text-[12px] font-medium text-[var(--kq-color-ink)]">{ax.label}</span>
                    <span className="text-[11px] text-[#7c5cff]">{Number(d?.level ?? 0)}/5</span>
                  </div>
                  {d?.summary ? (
                    <p className="break-words text-[11.5px] leading-snug text-[var(--kq-color-muted)]">
                      {d.summary}
                    </p>
                  ) : null}
                </li>
              );
            })}
          </ul>

          <p className="mt-2 text-[10.5px] leading-snug text-[var(--kq-color-muted)]">
            分值是随学习动态更新、你可随时修改的当前状态快照，非固定能力评价。
          </p>

          {profile.status !== "active" ? (
            <div className="mt-2 flex items-center gap-2">
              <button
                type="button"
                onClick={() => void act(cmdStudyArtifactActivate)}
                className="kq-quick-action inline-flex flex-1 items-center justify-center gap-1.5 rounded-[10px] px-2.5 py-1.5 text-[12px] leading-snug transition"
              >
                <Check className="h-3.5 w-3.5" aria-hidden />
                激活为当前画像
              </button>
              <button
                type="button"
                onClick={() => void act(cmdStudyArtifactReject)}
                className="kq-soft-icon-btn inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-md transition"
                aria-label="驳回"
                title="驳回"
              >
                <X className="h-3.5 w-3.5" aria-hidden />
              </button>
            </div>
          ) : null}
        </div>
      ) : (
        <p className="mt-3 text-[12px] leading-relaxed text-[var(--kq-color-muted)]">
          还没有学习画像。点上面「构建学习画像」，小娜会用对话帮你梳理知识基础、认知风格、易错点、目标、节奏与兴趣 6 个维度，生成后在这里以雷达图查看并激活。
        </p>
      )}

      {status ? <div className="mt-2 text-[11.5px] text-[var(--kq-color-muted)]">{status}</div> : null}
    </WorkspaceSection>
  );
}
