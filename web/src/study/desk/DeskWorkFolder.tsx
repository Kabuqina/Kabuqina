// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useEffect, useMemo, useRef, useState } from "react";
import type { DeskMaterials } from "./types";

export type DeskCreateChatRequest = {
  focusId: string;
  focusLabel: string;
  question: string;
  prompt: string;
  selectedSources: Array<{ id: string; title: string; kind: string }>;
};

export function DeskWorkFolder({
  courseName,
  materials,
  initialSourceId,
  onCreate,
  onOpenMaterials,
  onClose,
}: {
  courseName: string;
  materials: DeskMaterials;
  initialSourceId?: string | null;
  onCreate: (request: DeskCreateChatRequest) => void;
  onOpenMaterials?: () => void;
  onClose: () => void;
}) {
  const heading = useRef<HTMLHeadingElement>(null);
  const [tab, setTab] = useState<"create" | "results">("create");
  const [selected, setSelected] = useState<string[]>(() => (
    initialSourceId && materials.items.some((item) => item.id === initialSourceId)
      ? [initialSourceId]
      : []
  ));
  const [request, setRequest] = useState("请先帮我梳理制作目标和步骤，不要直接替我完成。");
  useEffect(() => {
    const frame = requestAnimationFrame(() => heading.current?.focus());
    return () => cancelAnimationFrame(frame);
  }, []);
  const sources = useMemo(
    () => materials.items
      .filter((item) => selected.includes(item.id))
      .map((item) => ({ id: item.id, title: item.title, kind: item.kind })),
    [materials.items, selected],
  );

  return (
    <main className="kd-panel-layout">
      <section className="kd-panel-card" aria-labelledby="kd-work-folder-title">
        <header className="kd-panel-heading">
          <div>
            <p className="kd-page-kicker">工作夹</p>
            <h1 id="kd-work-folder-title" ref={heading} tabIndex={-1}>制作 / 成果</h1>
            <p>{courseName} · 这里先确认来源和目标，再进入本子对话。</p>
          </div>
          <button type="button" onClick={onClose}>回到书桌</button>
        </header>
        <div className="kd-panel-tabs" role="tablist" aria-label="工作夹分类">
          <button type="button" role="tab" aria-selected={tab === "create"} onClick={() => setTab("create")}>制作</button>
          <button type="button" role="tab" aria-selected={tab === "results"} onClick={() => setTab("results")}>成果</button>
        </div>
        {tab === "create" ? (
          <div className="kd-work-create" role="tabpanel">
            <h2>选择要带入对话的知识源</h2>
            {materials.unavailable ? (
              <div className="kd-honest-state" role="status">
                <p>材料暂时无法读取。书桌没有替你猜选来源。</p>
                {onOpenMaterials ? <button type="button" onClick={onOpenMaterials}>前往学习页</button> : null}
              </div>
            ) : materials.items.length ? (
              <div className="kd-source-list">
                {materials.items.map((item) => (
                  <label key={item.id}>
                    <input
                      type="checkbox"
                      checked={selected.includes(item.id)}
                      onChange={(event) => {
                        const checked = event.currentTarget.checked;
                        setSelected((current) => (
                          checked
                            ? [...current, item.id]
                            : current.filter((id) => id !== item.id)
                        ));
                      }}
                    />
                    <span><strong>{item.title}</strong><small>{item.kind} · {item.status}</small></span>
                  </label>
                ))}
              </div>
            ) : (
              <div className="kd-honest-state">
                <p>这本本子还没有材料。先整理材料，再开始制作。</p>
                {onOpenMaterials ? <button type="button" onClick={onOpenMaterials}>去整理材料</button> : null}
              </div>
            )}
            <label htmlFor="kd-create-request"><strong>这次想制作什么？</strong></label>
            <textarea id="kd-create-request" value={request} onChange={(event) => setRequest(event.currentTarget.value)} />
            <button
              type="button"
              className="kd-primary"
              disabled={!sources.length || !request.trim()}
              onClick={() => onCreate({
                focusId: `course-create:${sources.map((source) => source.id).sort().join(",")}`,
                focusLabel: "工作夹 · 制作",
                question: request.trim(),
                prompt: `基于所选学习材料协助学生制作；本子：${courseName}`,
                selectedSources: sources,
              })}
            >
              带着所选材料问小娜
            </button>
          </div>
        ) : (
          <div className="kd-honest-state" role="tabpanel">
            <h2>成果会在可核验后出现在这里</h2>
            <p>当前版本没有可靠的学习成果索引，因此不会把普通聊天文件猜成成果。已保存的本子产物接入结构化索引后会在这里显示。</p>
          </div>
        )}
      </section>
    </main>
  );
}
