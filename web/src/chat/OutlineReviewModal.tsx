// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useState } from "react";
import { Check, Pencil, RefreshCw } from "lucide-react";
import { ShellModal } from "../components/ShellModal";
import type { PendingAgentInteraction } from "./chat-api";

type OutlineReviewModalProps = {
  interaction: PendingAgentInteraction;
  onRespond?: (action: string, text?: string, data?: Record<string, unknown>) => Promise<void>;
};

type PanelMode = "none" | "refine" | "edit";

export function OutlineReviewModal({ interaction, onRespond }: OutlineReviewModalProps) {
  const [draft, setDraft] = useState(interaction.artifact?.content || "");
  const [note, setNote] = useState("");
  const [panel, setPanel] = useState<PanelMode>("none");
  const [busy, setBusy] = useState(false);

  const submit = async (action: string, text = draft, data?: Record<string, unknown>) => {
    if (!onRespond || busy) return;
    setBusy(true);
    try {
      await onRespond(action, text, data);
    } finally {
      setBusy(false);
    }
  };

  const isRefining = panel === "refine";
  const isEditing = panel === "edit";

  return (
    <ShellModal
      open
      title={interaction.question || "请确认"}
      onClose={() => {
        /* 大纲审核是阻断式决策，不允许关闭 */
      }}
      size="lg"
      closable={false}
    >
      <div className="flex flex-col gap-4">
        {isEditing ? (
          <div>
            <label className="mb-2 block text-xs font-medium text-[var(--kq-color-strong)]">
              自行编辑
            </label>
            <textarea
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              disabled={busy}
              className="h-80 w-full resize-none rounded-lg border border-zinc-300 bg-white/70 p-3 font-mono text-sm leading-relaxed text-zinc-800 dark:border-[var(--kq-color-border)] dark:bg-[var(--kq-glass-bg)] dark:text-[var(--kq-color-strong)]"
              autoFocus
            />
          </div>
        ) : (
          <pre className="max-h-72 overflow-auto whitespace-pre-wrap rounded-lg border border-[#e8e0ed] bg-white/70 p-3 text-sm leading-relaxed text-zinc-800 dark:border-[var(--kq-color-border)] dark:bg-[var(--kq-glass-bg)] dark:text-[var(--kq-color-strong)]">
            {draft}
          </pre>
        )}

        {isRefining ? (
          <div className="rounded-lg border border-zinc-200 p-3 dark:border-[var(--kq-color-border)]">
            <label className="mb-2 block text-xs font-medium text-[var(--kq-color-strong)]">
              补充要求
            </label>
            <textarea
              value={note}
              onChange={(e) => setNote(e.target.value)}
              disabled={busy}
              placeholder="例如：增加一页市场分析、减少技术细节……"
              className="h-32 w-full resize-none rounded-lg border border-zinc-300 bg-white/70 p-3 text-sm text-zinc-800 dark:border-[var(--kq-color-border)] dark:bg-[var(--kq-glass-bg)] dark:text-[var(--kq-color-strong)]"
              autoFocus
            />
          </div>
        ) : null}

        <div className="flex flex-wrap justify-end gap-2">
          {isRefining ? (
            <>
              <button
                type="button"
                disabled={busy}
                onClick={() => setPanel("none")}
                className="rounded-lg px-3 py-2 text-sm text-[var(--kq-color-ink)]"
              >
                取消
              </button>
              <button
                type="button"
                disabled={busy || !note.trim()}
                onClick={() => submit("refine", note, { outline: draft })}
                className="kq-quick-action inline-flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm"
              >
                <RefreshCw className="h-4 w-4" aria-hidden />
                重新生成
              </button>
            </>
          ) : isEditing ? (
            <>
              <button
                type="button"
                disabled={busy}
                onClick={() => setPanel("none")}
                className="rounded-lg px-3 py-2 text-sm text-[var(--kq-color-ink)]"
              >
                取消
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={() => submit("edit", draft)}
                className="kq-quick-action inline-flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm"
              >
                <Pencil className="h-4 w-4" aria-hidden />
                保存并生成
              </button>
            </>
          ) : (
            <>
              <button
                type="button"
                disabled={busy}
                onClick={() => submit("approve", draft)}
                className="kq-quick-action inline-flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm"
              >
                <Check className="h-4 w-4" aria-hidden />
                通过
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={() => setPanel("refine")}
                className="kq-quick-action inline-flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm"
              >
                <RefreshCw className="h-4 w-4" aria-hidden />
                补充要求
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={() => setPanel("edit")}
                className="kq-quick-action inline-flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm"
              >
                <Pencil className="h-4 w-4" aria-hidden />
                自行编辑
              </button>
            </>
          )}
        </div>
      </div>
    </ShellModal>
  );
}
