// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useCallback, useEffect, useRef, useState } from "react";
import { cmdGetKabuqinaSessions, type SessionRow } from "../../chat/chat-api";
import { readSessionStudyHandoff } from "../../lib/studyChatHandoff";
import type { DeskActivityRecord } from "./types";

const LABELS: Record<string, string> = {
  "quiz.attempt": "完成了一次练习检查",
  "flashcard.review": "复习了一张卡片",
  "plan.item.completed": "完成了一项学习计划",
  "plan.item.skipped": "调整了一项学习计划",
};

function displayTime(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.valueOf())) return value;
  return new Intl.DateTimeFormat("zh-CN", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

export function DeskActivityPanel({
  activities,
  unavailable,
  loading,
  error,
  spaceId,
  onOpenFull,
  onOpenChatSession,
  onRetryStudy,
  onClose,
}: {
  activities: DeskActivityRecord[];
  unavailable?: boolean;
  loading?: boolean;
  error?: boolean;
  spaceId: string;
  onOpenFull?: () => void;
  onOpenChatSession?: (sessionId: string) => void;
  onRetryStudy?: () => void;
  onClose: () => void;
}) {
  const heading = useRef<HTMLHeadingElement>(null);
  const [chatState, setChatState] = useState<
    | { status: "loading"; items: SessionRow[] }
    | { status: "ready"; items: SessionRow[] }
    | { status: "error"; items: SessionRow[] }
  >({ status: "loading", items: [] });
  const loadChats = useCallback(() => {
    setChatState((current) => ({ status: "loading", items: current.items }));
    void cmdGetKabuqinaSessions(50, 0).then(
      (response) => {
        const items = response.sessions.filter((session) => (
          readSessionStudyHandoff(session.id)?.spaceId === spaceId
        ));
        setChatState({ status: "ready", items });
      },
      () => setChatState((current) => ({ status: "error", items: current.items })),
    );
  }, [spaceId]);
  useEffect(() => {
    const frame = requestAnimationFrame(() => heading.current?.focus());
    return () => cancelAnimationFrame(frame);
  }, []);
  useEffect(loadChats, [loadChats]);
  return (
    <main className="kd-panel-layout">
      <section className="kd-panel-card" aria-labelledby="kd-activity-title">
        <header className="kd-panel-heading">
          <div>
            <p className="kd-page-kicker">学习动态</p>
            <h1 id="kd-activity-title" ref={heading} tabIndex={-1}>这本课程最近发生了什么</h1>
            <p>这里只显示 Study 仓库已经记录的学习证据。</p>
          </div>
          <button type="button" onClick={onClose}>回到书桌</button>
        </header>
        {loading && !activities.length ? <p role="status">正在读取学习动态…</p> : null}
        {error || unavailable ? (
          <div className="kd-honest-state" role="alert">
            <p>学习动态暂时无法读取，已有记录没有被改动。</p>
            {onRetryStudy ? <button type="button" onClick={onRetryStudy}>重新读取学习动态</button> : null}
          </div>
        ) : null}
        {activities.length ? (
          <ol className="kd-activity-list">
            {activities.map((item) => (
              <li key={item.id}>
                <span aria-hidden="true" />
                <div>
                  <strong>{LABELS[item.type] ?? item.type}</strong>
                  <time dateTime={item.createdAt}>{displayTime(item.createdAt)}</time>
                </div>
              </li>
            ))}
          </ol>
        ) : !loading && !error && !unavailable ? (
          <div className="kd-honest-state"><p>这本课程还没有学习动态。完成一道题或复习一张卡片后，记录会出现在这里。</p></div>
        ) : null}
        {loading && activities.length ? <p role="status">正在刷新学习动态…</p> : null}
        <section className="kd-recent-chats" aria-labelledby="kd-recent-chat-title">
          <h2 id="kd-recent-chat-title">本课对话</h2>
          {chatState.status === "loading" && !chatState.items.length ? <p role="status">正在读取课程对话…</p> : null}
          {chatState.status === "error" && !chatState.items.length ? (
            <div className="kd-honest-state" role="alert">
              <p>课程对话暂时无法读取。Study 学习记录仍可正常使用。</p>
              <button type="button" onClick={loadChats}>重试</button>
            </div>
          ) : null}
          {chatState.items.length ? (
            <ul>
              {chatState.items.map((session) => (
                <li key={session.id}>
                  <button type="button" onClick={() => onOpenChatSession?.(session.id)}>
                    <strong>{session.title || session.preview || "课程对话"}</strong>
                    <span>{session.message_count ?? 0} 条消息</span>
                  </button>
                </li>
              ))}
            </ul>
          ) : chatState.status === "ready" ? (
            <p>还没有与这本课程绑定的对话。普通聊天不会被自动归入本课。</p>
          ) : null}
          {chatState.status === "error" && chatState.items.length ? <button type="button" onClick={loadChats}>刷新失败，再试一次</button> : null}
        </section>
        {onOpenFull ? <button type="button" onClick={onOpenFull}>查看错题与完整评估</button> : null}
      </section>
    </main>
  );
}
