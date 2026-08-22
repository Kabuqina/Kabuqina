// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useEffect, useRef } from "react";
import { Trash2 } from "lucide-react";
import { useI18n } from "../lib/i18n";
import { cn } from "../lib/cn";
import { PixelGlyph } from "../components/voxel/PixelGlyph";
import { VoxelIcon } from "../components/voxel/VoxelIcon";
import type { SessionRow } from "./chat-api";
import { deriveSessionPresentation } from "./sessionPresentation";
import { readSessionStudyHandoff, type StudyChatHandoff } from "../lib/studyChatHandoff";

/**
 * 历史会话抽屉（设计稿第五轮 5a）。
 *
 * Chat 是**刻意极简**的自由对话空间，所以历史不占一条常驻侧栏——它收进桌沿下面，
 * 需要时才拉开。三类会话（自由 / 课程 / 项目）进同一份列表，**没有并列的作用域
 * 标签页**；来源只用一个低强调标签辨认，用户主动选中某条之后才进入那个作用域。
 *
 * 原来侧栏上的常用工具（定时任务、导出）没有别处可去，收进屉里的右格——
 * 换布局不等于砍能力。
 *
 * 这只屉是**真的被拉出来的一只屉**，不是贴在底边的一块深色面板：
 * - 上沿一道桌沿断面、下沿一张抽屉脸，两端都有实体，中间那段才读作「屉里」；
 * - 屉宽而矮，所以中间一道隔板分成左右两格——一条横穿全屏的摘要没法读，
 *   工具再横铺一行就更浪费高度；
 * - **拉手是唯一的开关**。收起态下抽屉脸仍露在桌沿下，拉手就在正中；纸头上原来那颗
 *   历史入口撤掉了——它用的是 `PanelLeftOpen`（侧栏语义），屉搬到下面之后这个图形
 *   本身就在说错话，而且它和拉手是同一个动作的两个入口。
 *
 * 拉手必须是**真按钮**：键盘可达、带 aria-label。一块可点的木头不是控件。
 */
export function ChatHistoryDrawer({
  open,
  sessions,
  activeSessionId,
  loading,
  onOpen,
  onClose,
  onSelectSession,
  onDeleteSession,
  onOpenActivity,
  onOpenScheduledTasks,
  onExport,
}: {
  open: boolean;
  sessions: SessionRow[];
  activeSessionId: string | null;
  loading?: boolean;
  onOpen: () => void;
  onClose: () => void;
  onSelectSession: (id: string) => void;
  onDeleteSession: (id: string, e: React.MouseEvent) => void;
  onOpenActivity: () => void;
  onOpenScheduledTasks: () => void;
  onExport: () => void;
}) {
  const { t, locale } = useI18n();
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    closeRef.current?.focus();
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose, open]);

  return (
    <>
      {open ? <div className="kq-chat-drawer-scrim" role="presentation" onMouseDown={onClose} /> : null}
      <aside
        className={cn("kq-chat-drawer", open && "is-open")}
        aria-label={t("chat.historyTitle")}
        aria-hidden={!open}
        inert={!open}
      >
        {/* 桌沿的断面：屉拉开后露出来的那 9px 木头厚度。 */}
        <div className="kq-chat-drawer-lip" aria-hidden />

        <div className="kq-chat-drawer-body">
          <section className="kq-chat-drawer-stack">
            <header>
              <strong>{t("chat.historyTitle")}</strong>
              <span className="kq-chat-drawer-count">
                {t("chat.historyCount", { count: String(sessions.length) })}
              </span>
            </header>

            <div className="kq-chat-drawer-list">
              <div className="kq-chat-drawer-scroll">
                {loading && !sessions.length ? (
                  <p className="kq-chat-drawer-empty" role="status">{t("chat.historyLoading")}</p>
                ) : null}
                {!loading && !sessions.length ? (
                  <p className="kq-chat-drawer-empty">{t("chat.historyEmpty")}</p>
                ) : null}
                {sessions.map((session) => {
                  const presentation = deriveSessionPresentation(session, locale);
                  const origin = sessionOrigin(session.id, t);
                  return (
                    <button
                      type="button"
                      key={session.id}
                      className={cn("kq-chat-drawer-row", session.id === activeSessionId && "is-active")}
                      aria-current={session.id === activeSessionId ? "true" : undefined}
                      onClick={() => onSelectSession(session.id)}
                    >
                      <strong>{presentation.label}</strong>
                      <span>
                        {presentation.group}
                        {/* 来源只是一个低强调标签，不是一个并列的作用域入口。 */}
                        {origin ? <small className="kq-chat-drawer-origin">{origin}</small> : null}
                      </span>
                      <span
                        className="kq-chat-drawer-delete"
                        role="button"
                        tabIndex={0}
                        aria-label={t("chat.deleteSession")}
                        onClick={(event) => {
                          event.stopPropagation();
                          onDeleteSession(session.id, event);
                        }}
                        onKeyDown={(event) => {
                          if (event.key !== "Enter" && event.key !== " ") return;
                          event.preventDefault();
                          event.stopPropagation();
                          onDeleteSession(session.id, event as unknown as React.MouseEvent);
                        }}
                      >
                        <Trash2 aria-hidden size={14} />
                      </span>
                    </button>
                  );
                })}
              </div>
            </div>
          </section>

          {/* 隔板不是装饰：真实抽屉里就是靠隔板分区的。上下两端渐隐，读作嵌在屉里的一片木板。 */}
          <div className="kq-chat-drawer-split" aria-hidden />

          <section className="kq-chat-drawer-tools">
            <header>
              <strong>{t("chat.drawerTools")}</strong>
              <button ref={closeRef} type="button" aria-label={t("chat.historyClose")} onClick={onClose}>
                <PixelGlyph name="close" size={14} />
              </button>
            </header>
            <div className="kq-chat-drawer-toollist">
              {/* 进行中搬到这里：横条上不该有第二处会跳数字的东西（设计稿 5）。 */}
              <button type="button" onClick={onOpenActivity}>
                <PixelGlyph name="listTodo" size={15} />{t("appShell.activity")}
              </button>
              <button type="button" onClick={onOpenScheduledTasks}>
                <PixelGlyph name="alarm" size={15} />{t("chat.scheduledTasks")}
              </button>
              <button type="button" onClick={onExport}>
                <PixelGlyph name="download" size={15} />{t("chat.exportChat")}
              </button>
            </div>
          </section>
        </div>

      </aside>

      {/* 抽屉脸站在 aside **外面**：屉体是从它背后滑出来的那部分，脸本身不动——
          脸跟着屉体一起平移的话，收起态它会一路掉到桌沿以下，拉手就没了。
          它也不能跟着 aside 一起 inert：那样收起后就再也拉不开。 */}
      <button
        type="button"
        className="kq-chat-drawer-pull"
        aria-label={open ? t("chat.historyClose") : t("chat.historyOpen")}
        aria-expanded={open}
        onClick={open ? onClose : onOpen}
      >
        <VoxelIcon art="drawerPull" size={52} />
      </button>
    </>
  );
}

/** 会话的来源短语。绑定是会话自己的真值，绝不猜（架构 §8.3）。 */
function sessionOrigin(sessionId: string, t: (key: string) => string): string | null {
  const study: StudyChatHandoff | null = readSessionStudyHandoff(sessionId);
  if (study) return study.spaceTitle || t("appShell.study");
  return null;
}
