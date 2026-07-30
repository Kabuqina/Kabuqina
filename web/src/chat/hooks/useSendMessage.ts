// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useCallback, useEffect, useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { listen, type UnlistenFn } from "@tauri-apps/api/event";
import {
  CHAT_STREAM_EVENT,
  cmdChatPreview,
  cmdChatSend,
  cmdChatSendStream,
  cmdDeskStop,
  cmdGetSessionMessages,
  cmdInteractionResponse,
  fileToDeskAttachment,
  isRecord,
  parseChatSend,
  type PendingAgentInteraction,
  type ChatStreamEnvelope,
  type ChatStreamEvent,
  type DeskAttachmentPayload,
  type UiMsg,
} from "../chat-api";
import { STUDY_LEARNING_EVENT } from "../../study/learningEvent";
import {
  applyEvents,
  emptyProgress,
  type AgentProgressState,
} from "./useAgentProgress";
import type { Locale } from "../../lib/i18n-core";
import { friendlyChatError } from "../friendlyError";
import { latestAssistantText } from "../inFlightTurnUtils";
import type { InFlightTurn, InFlightTurnsController } from "../inFlightTurns";
import { persistActiveSessionId } from "./useChatState";

const POLL_INTERVAL_MS = 300;

export function useSendMessage({
  activeSessionId,
  setActiveSessionId,
  threadModel,
  setThreadModel,
  setMessages,
  loadSessions,
  setApiRequiredOpen,
  setSendErr,
  locale,
  inFlightTurns,
  prepareText,
}: {
  activeSessionId: string | null;
  setActiveSessionId: (id: string | null) => void;
  threadModel: string;
  setThreadModel: (model: string) => void;
  setMessages: React.Dispatch<React.SetStateAction<UiMsg[]>>;
  loadSessions: (options?: { silent?: boolean }) => Promise<void>;
  setApiRequiredOpen: (open: boolean) => void;
  setSendErr: (err: string | null) => void;
  locale: Locale;
  inFlightTurns?: InFlightTurnsController;
  /** Hidden page context can be prepended for transport while transcript keeps the learner's own text. */
  prepareText?: (text: string) => string;
}) {
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [progress, setProgress] = useState<AgentProgressState | null>(null);
  const [pendingInteraction, setPendingInteraction] = useState<PendingAgentInteraction | null>(null);
  const [pendingAttachments, setPendingAttachments] = useState<DeskAttachmentPayload[]>([]);
  const stopTurnRef = useRef(false);
  const inFlightSessionIdRef = useRef<string | null>(null);
  const activeSessionIdRef = useRef(activeSessionId);
  const progressTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  /** Latest progress snapshot — read inside poll callback so the next `since` cursor is fresh. */
  const progressRef = useRef<AgentProgressState | null>(null);

  useEffect(() => {
    activeSessionIdRef.current = activeSessionId;
    const inFlight = inFlightSessionIdRef.current;
    if (!inFlight) {
      return;
    }
    setProgress(activeSessionId === inFlight ? progressRef.current : null);
  }, [activeSessionId]);

  const onAddFiles = useCallback(async (list: FileList | null) => {
    if (!list?.length) {
      return;
    }
    const out: DeskAttachmentPayload[] = [];
    for (let i = 0; i < list.length; i++) {
      if (out.length >= 6) {
        break;
      }
      const f = list[i];
      try {
        out.push(await fileToDeskAttachment(f));
      } catch (e) {
        console.error(e);
      }
    }
    setPendingAttachments((prev) => [...prev, ...out]);
  }, []);

  const onRemoveAttachment = useCallback((index: number) => {
    setPendingAttachments((prev) => prev.filter((_, i) => i !== index));
  }, []);

  const onAddCaptureAttachment = useCallback((payload: DeskAttachmentPayload) => {
    setPendingAttachments((prev) => {
      if (prev.length >= 6) return prev;
      return [...prev, payload];
    });
  }, []);

  const stopProgressPoll = useCallback(() => {
    if (progressTimerRef.current) {
      clearInterval(progressTimerRef.current);
      progressTimerRef.current = null;
    }
  }, []);

  const mergeProgress = useCallback((p: unknown, visibleSessionId: string) => {
    if (!isRecord(p)) {
      return;
    }
    const prev = progressRef.current ?? emptyProgress();
    const rawEvents = Array.isArray(p.events) ? p.events : [];
    const steps = applyEvents(prev.steps, rawEvents as Parameters<typeof applyEvents>[1]);
    const merged: AgentProgressState = {
      running: typeof p.running === "boolean" ? p.running : prev.running,
      status: typeof p.status === "string" ? p.status : prev.status,
      iteration: typeof p.iteration === "number" ? p.iteration : prev.iteration,
      max_iterations:
        typeof p.max_iterations === "number" ? p.max_iterations : prev.max_iterations,
      current_tool: typeof p.current_tool === "string" ? p.current_tool : null,
      error: typeof p.error === "string" ? p.error : null,
      steps,
      nextSeq:
        typeof p.next_seq === "number" && p.next_seq > prev.nextSeq
          ? p.next_seq
          : prev.nextSeq,
    };
    progressRef.current = merged;
    inFlightTurns?.upsertTurn(visibleSessionId, (prev) =>
      prev
        ? {
            ...prev,
            progress: merged,
          }
        : null,
    );
    if (activeSessionIdRef.current === visibleSessionId) {
      setProgress(merged);
    }
  }, [inFlightTurns]);

  const onStopAgent = useCallback(async () => {
    const sid = inFlightSessionIdRef.current || activeSessionId;
    if (!sid) {
      return;
    }
    stopTurnRef.current = true;
    stopProgressPoll();
    setProgress(null);
    setPendingInteraction(null);
    progressRef.current = null;
    setSending(false);
    setMessages((m) => m.filter((x) => x.id !== "pending-assistant"));
    inFlightTurns?.clearTurn(sid);
    setSendErr(null);
    try {
      await cmdDeskStop(sid);
    } catch (e) {
      console.error(e);
      const msg =
        typeof e === "string"
          ? e
          : e && isRecord(e) && typeof e.message === "string"
            ? e.message
            : String(e);
      setSendErr(friendlyChatError(msg, locale));
    }
  }, [activeSessionId, inFlightTurns, locale, setMessages, setSendErr, stopProgressPoll]);

  const onSend = useCallback(async () => {
    const text = input.trim();
    const requestText = prepareText?.(text) ?? text;
    const atts = pendingAttachments;
    if (sending || (!text && !atts.length)) {
      return;
    }
    try {
      const hasKey = await invoke<boolean>("cmd_has_secret");
      if (!hasKey) {
        setApiRequiredOpen(true);
        return;
      }
    } catch {
      setApiRequiredOpen(true);
      return;
    }
    setSending(true);
    stopTurnRef.current = false;
    setSendErr(null);
    setInput("");
    setPendingAttachments([]);
    setPendingInteraction(null);

    let sessionForSend = activeSessionId;
    if (!sessionForSend) {
      sessionForSend =
        typeof crypto !== "undefined" && typeof crypto.randomUUID === "function"
          ? crypto.randomUUID()
          : `desk-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
      setActiveSessionId(sessionForSend);
    }
    persistActiveSessionId(sessionForSend);
    activeSessionIdRef.current = sessionForSend;
    inFlightSessionIdRef.current = sessionForSend;

    // Reset progress for this turn.
    const initial = emptyProgress();
    initial.running = true;
    initial.status = "starting";
    progressRef.current = initial;
    setProgress(initial);

    const imageAtts = atts.filter((a) => a.mime.startsWith("image/"));
    const fileAtts = atts.filter((a) => !imageAtts.includes(a));
    const fileAttLabel =
      fileAtts.length > 0
        ? fileAtts.map((a) => `📎 ${a.name}`).join("\n")
        : "";
    const userText = [text, fileAttLabel].filter(Boolean).join("\n");
    const nowSec = Math.floor(Date.now() / 1000);
    const userMsg: UiMsg = {
      id: `u-${Date.now()}`,
      role: "user",
      text: userText,
      attachments: atts,
      timestamp: nowSec,
    };
    const placeholder: UiMsg = {
      id: "pending-assistant",
      role: "assistant",
      text: "…",
      model: threadModel || undefined,
      timestamp: nowSec,
    };
    const requestId =
      typeof crypto !== "undefined" && typeof crypto.randomUUID === "function"
        ? crypto.randomUUID()
        : `stream-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
    setMessages((m) => [...m, userMsg, placeholder]);
    inFlightTurns?.upsertTurn(sessionForSend, {
      sessionId: sessionForSend,
      requestId,
      startedAt: Date.now(),
      userMsg,
      pendingAssistant: placeholder,
      streamedText: "",
      status: "running",
      progress: initial,
    });

    const isVisible = () => activeSessionIdRef.current === sessionForSend;
    let streamedText = "";
    let animationFrame: number | null = null;
    let sawStreamEvent = false;
    /** SSE error events are deferred until the stream command finishes — final may still succeed. */
    let deferredStreamError: string | null = null;
    let unlistenStream: UnlistenFn | null = null;

    const patchInFlightTurn = (patch: Partial<InFlightTurn>) => {
      inFlightTurns?.upsertTurn(sessionForSend, (prev) =>
        prev
          ? {
              ...prev,
              ...patch,
              pendingAssistant: patch.pendingAssistant ?? prev.pendingAssistant,
              progress: "progress" in patch ? patch.progress ?? null : prev.progress,
            }
          : null,
      );
    };

    const upsertPendingAssistant = (nextText: string, finalModel?: string, finalize = false) => {
      const ts = Math.floor(Date.now() / 1000);
      patchInFlightTurn({
        streamedText: nextText,
        pendingAssistant: {
          ...placeholder,
          text: nextText || "…",
          model: finalModel || placeholder.model,
          timestamp: finalize ? ts : placeholder.timestamp,
        },
      });
      if (!isVisible()) {
        return;
      }
      setMessages((m) => {
        let found = false;
        const next = m.map((x) => {
          if (x.id !== "pending-assistant") {
            return x;
          }
          found = true;
          return {
            ...x,
            id: finalize ? `a-${Date.now()}` : x.id,
            text: nextText || "…",
            model: finalModel || x.model,
            timestamp: finalize ? ts : x.timestamp,
          };
        });
        if (found) {
          return next;
        }
        return [
          ...m,
          {
            id: finalize ? `a-${Date.now()}` : "pending-assistant",
            role: "assistant",
            text: nextText || "…",
            model: finalModel || threadModel || undefined,
            timestamp: ts,
          },
        ];
      });
    };

    const flushStreamedText = () => {
      animationFrame = null;
      upsertPendingAssistant(streamedText);
    };

    const queueDelta = (delta: string) => {
      streamedText += delta;
      if (animationFrame == null) {
        animationFrame = window.requestAnimationFrame(flushStreamedText);
      }
    };

    const startFallbackProgressPoll = () => {
      let seenRunning = false;
      let inactivePolls = 0;
      const pollSid = sessionForSend;
      const pollProgress = async () => {
        try {
          const since = progressRef.current?.nextSeq ?? 0;
          const p = await cmdChatPreview(pollSid, since);
          if (p.running) {
            seenRunning = true;
          } else if (p.status === "inactive" && !seenRunning && inactivePolls < 12) {
            inactivePolls += 1;
            return;
          }
          mergeProgress(p, pollSid);
          if (!p.running && p.status !== "inactive") {
            stopProgressPoll();
          }
        } catch {
          // Preserve the last visible progress; send completion/error owns cleanup.
        }
      };
      void pollProgress();
      progressTimerRef.current = setInterval(pollProgress, POLL_INTERVAL_MS);
    };

    const recoverDetachedStreamFinal = async (): Promise<unknown | null> => {
      patchInFlightTurn({ status: "reconnecting" });
      const deadline = Date.now() + 10 * 60 * 1000;
      let inactivePolls = 0;
      while (!stopTurnRef.current && Date.now() < deadline) {
        try {
          const since = progressRef.current?.nextSeq ?? 0;
          const p = await cmdChatPreview(sessionForSend, since);
          mergeProgress(p, sessionForSend);
          if (!p.running) {
            const rows = await cmdGetSessionMessages(sessionForSend);
            const finalText = latestAssistantText(rows.messages ?? []);
            if (finalText) {
              patchInFlightTurn({ status: "finalizing" });
              return {
                ok: true,
                session_id: sessionForSend,
                final_response: finalText,
                model: threadModel,
              };
            }
            if (p.status === "inactive") {
              inactivePolls += 1;
              if (inactivePolls >= 4) {
                return null;
              }
            }
          }
        } catch {
          // The stream already failed; keep polling briefly so a completed DB
          // write can still win over a transient transport error.
        }
        await new Promise((resolve) => window.setTimeout(resolve, 1000));
      }
      return null;
    };

    const handleStreamEvent = (event: ChatStreamEvent) => {
      sawStreamEvent = true;
      if (event.session_id && event.session_id !== sessionForSend) {
        return;
      }
      if (event.progress) {
        mergeProgress(event.progress, sessionForSend);
      }
      if (event.type === "interaction.request" && event.interaction && !stopTurnRef.current) {
        setPendingInteraction({
          ...event.interaction,
          sessionId: event.session_id || sessionForSend,
        });
      }
      if (event.type === "learning.output.created" && typeof window !== "undefined") {
        window.dispatchEvent(new CustomEvent(STUDY_LEARNING_EVENT, { detail: event }));
      }
      if (event.type === "delta" && typeof event.text === "string" && !stopTurnRef.current) {
        queueDelta(event.text);
      }
      if (event.type === "error" && !stopTurnRef.current) {
        console.error("chat stream error (deferred):", event);
        deferredStreamError = event.detail || event.error || "Stream failed";
      }
    };

    try {
      let raw: unknown;
      try {
        unlistenStream = await listen<ChatStreamEnvelope>(CHAT_STREAM_EVENT, ({ payload }) => {
          if (payload?.requestId !== requestId) {
            return;
          }
          handleStreamEvent(payload.event);
        });
        raw = await cmdChatSendStream(requestId, requestText, sessionForSend, atts.length ? atts : null);
      } catch (streamErr) {
        unlistenStream?.();
        unlistenStream = null;
        if (sawStreamEvent) {
          const recovered = await recoverDetachedStreamFinal();
          if (recovered) {
            raw = recovered;
          } else {
            throw streamErr;
          }
        } else {
          startFallbackProgressPoll();
          raw = await cmdChatSend(requestText, sessionForSend, atts.length ? atts : null);
        }
      }
      const parsed = parseChatSend(raw);
      if (stopTurnRef.current) {
        setMessages((m) => m.filter((x) => x.id !== "pending-assistant"));
        inFlightTurns?.clearTurn(sessionForSend);
        return;
      }
      if (!parsed.ok) {
        console.error("chat send failed:", parsed.err);
        patchInFlightTurn({ status: "failed" });
        setMessages((m) => m.filter((x) => x.id !== "pending-assistant"));
        if (isVisible()) {
          setSendErr(friendlyChatError(deferredStreamError || parsed.err, locale));
        }
        return;
      }
      if (isVisible()) {
        setSendErr(null);
      }
      const resolvedModel = (parsed.model || "").trim() || threadModel;
      if (isVisible()) {
        setActiveSessionId(parsed.sessionId);
      }
      if (resolvedModel && isVisible()) {
        setThreadModel(resolvedModel);
      }
      if (stopTurnRef.current) {
        setMessages((m) => m.filter((x) => x.id !== "pending-assistant"));
        inFlightTurns?.clearTurn(sessionForSend);
        return;
      }
      if (animationFrame != null) {
        window.cancelAnimationFrame(animationFrame);
        animationFrame = null;
      }
      streamedText = parsed.text || streamedText;
      upsertPendingAssistant(streamedText, resolvedModel || undefined, true);
      inFlightTurns?.clearTurn(sessionForSend);
      void loadSessions({ silent: true });
    } catch (e) {
      if (!stopTurnRef.current) {
        patchInFlightTurn({ status: "failed" });
        setMessages((m) => m.filter((x) => x.id !== "pending-assistant"));
        const msg =
          typeof e === "string"
            ? e
            : e && isRecord(e) && typeof e.message === "string"
              ? e.message
              : String(e);
        if (isVisible()) {
          setSendErr(friendlyChatError(msg, locale));
        }
      }
    } finally {
      unlistenStream?.();
      if (animationFrame != null) {
        window.cancelAnimationFrame(animationFrame);
      }
      stopProgressPoll();
      setProgress(null);
      setPendingInteraction(null);
      progressRef.current = null;
      setSending(false);
      stopTurnRef.current = false;
      inFlightSessionIdRef.current = null;
    }
  }, [
    input,
    locale,
    pendingAttachments,
    sending,
    activeSessionId,
    threadModel,
    setActiveSessionId,
    setThreadModel,
    setMessages,
    loadSessions,
    setApiRequiredOpen,
    setSendErr,
    inFlightTurns,
    mergeProgress,
    stopProgressPoll,
    prepareText,
  ]);

  const onRespondInteraction = useCallback(async (action: string, text?: string, data?: Record<string, unknown>) => {
    const interaction = pendingInteraction;
    if (!interaction) return;
    await cmdInteractionResponse(interaction.sessionId, interaction.id, action, text ?? "", data ?? {});
    setPendingInteraction(null);
  }, [pendingInteraction]);

  return {
    input,
    setInput,
    sending,
    progress,
    pendingInteraction,
    pendingAttachments,
    onAddFiles,
    onAddCaptureAttachment,
    onRemoveAttachment,
    onSend,
    onStopAgent,
    onRespondInteraction,
  } as const;
}
