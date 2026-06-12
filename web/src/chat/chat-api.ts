// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { invoke } from "@tauri-apps/api/core";

export type SessionRow = {
  id: string;
  preview?: string;
  title?: string;
  model?: string;
  platform?: string;
  source?: string;
  last_active?: number;
  started_at?: number;
  message_count?: number;
};

export type SessionsResponse = {
  sessions: SessionRow[];
  total: number;
};

export type MessageRow = {
  role: string;
  content: unknown;
  timestamp?: number;
};

export type SessionMessagesResponse = {
  session_id: string;
  messages: MessageRow[];
};

export type UiMsg = {
  id: string;
  role: "user" | "assistant";
  text: string;
  attachments?: DeskAttachmentPayload[];
  /** Unix seconds (Hermes `messages.timestamp`), or ms if > 1e12 */
  timestamp?: number;
  model?: string;
};

export async function cmdGetHermesPort(): Promise<number | null> {
  const p = await invoke<number | null>("cmd_get_hermes_port");
  return p ?? null;
}

export type HermesDeskBootState = {
  port: number | null;
  warming: boolean;
};

export async function cmdGetHermesDeskBootState(): Promise<HermesDeskBootState> {
  return invoke<HermesDeskBootState>("cmd_get_hermes_desk_boot_state");
}

export async function cmdGetHermesBootstrapError(): Promise<string | null> {
  const err = await invoke<string | null>("cmd_get_hermes_bootstrap_error");
  return err?.trim() ? err : null;
}

export async function cmdGetSessions(limit = 50, offset = 0, source?: string): Promise<SessionsResponse> {
  return invoke<SessionsResponse>("cmd_get_sessions", { limit, offset, source: source ?? null });
}

export async function cmdGetSessionMessages(id: string): Promise<SessionMessagesResponse> {
  return invoke<SessionMessagesResponse>("cmd_get_session_messages", { id });
}

export async function cmdDeleteSession(id: string): Promise<void> {
  await invoke("cmd_delete_session", { id });
}

/** Base64 file payload for Hermes ``/api/desk/chat-proto`` (no data: URL prefix). */
export type { DeskAttachmentPayload, ParsedDeskUserContent } from "./deskUserContent";
export { DESK_UI_PERSIST_PREFIX, parseDeskUserContent } from "./deskUserContent";

import type { DeskAttachmentPayload } from "./deskUserContent";

export function fileToDeskAttachment(file: File): Promise<DeskAttachmentPayload> {
  return new Promise((resolve, reject) => {
    const r = new FileReader();
    r.onload = () => {
      const s = r.result as string;
      const i = s.indexOf(";base64,");
      if (i < 0) {
        reject(new Error("Failed to read file as data URL"));
        return;
      }
      const mime = (s.slice(5, i) || file.type || "application/octet-stream").trim() || "application/octet-stream";
      const data = s.slice(i + 8).replace(/\s/g, "");
      resolve({ name: file.name, mime, data });
    };
    r.onerror = () => reject(r.error ?? new Error("read error"));
    r.readAsDataURL(file);
  });
}

export async function cmdChatSend(
  message: string,
  sessionId: string | null,
  attachments?: DeskAttachmentPayload[] | null
): Promise<unknown> {
  // Tauri maps Rust `session_id` → JS `sessionId` (snake_case args use camelCase keys).
  return invoke("cmd_chat_send", {
    message,
    sessionId,
    attachments: attachments?.length ? attachments : null,
  });
}

export const CHAT_STREAM_EVENT = "chat-stream-event";

export type ChatStreamEvent = {
  type: "start" | "delta" | "boundary" | "progress" | "final" | "error" | "done" | string;
  session_id?: string;
  text?: string;
  progress?: ChatPreviewResponse;
  interaction?: AgentInteractionRequest;
  ok?: boolean;
  error?: string;
  detail?: string;
  final_response?: string;
  model?: string;
};

export type ChatStreamEnvelope = {
  requestId: string;
  event: ChatStreamEvent;
};

export async function cmdChatSendStream(
  requestId: string,
  message: string,
  sessionId: string | null,
  attachments?: DeskAttachmentPayload[] | null
): Promise<unknown> {
  return invoke("cmd_chat_send_stream", {
    requestId,
    message,
    sessionId,
    attachments: attachments?.length ? attachments : null,
  });
}

export function cmdDeskStop(sessionId: string): Promise<unknown> {
  return invoke("cmd_desk_stop", { sessionId });
}

export type AgentInteractionRequest = {
  id: string;
  kind: "choice" | "text" | "outline_review" | "pptx_render" | string;
  question: string;
  choices: string[];
  artifact?: {
    type?: string;
    content?: string;
    /** For kind="pptx_render": the structured deck spec built by pptx_write. */
    deck?: unknown;
    filename?: string;
    [key: string]: unknown;
  } | null;
  created_at?: number;
};

export type PendingAgentInteraction = AgentInteractionRequest & {
  sessionId: string;
};

export async function cmdInteractionResponse(
  sessionId: string,
  interactionId: string,
  action: string,
  text?: string,
  data?: Record<string, unknown>,
): Promise<unknown> {
  return invoke("cmd_interaction_response", {
    sessionId,
    interactionId,
    action,
    text: text ?? "",
    data: data ?? {},
  });
}

export type ProgressEvent = {
  seq: number;
  kind: "tool.started" | "tool.completed";
  tool: string;
  preview: string | null;
  duration: number | null;
  is_error: boolean;
  ts: number;
};

export type ChatPreviewResponse = {
  running: boolean;
  status: string;
  iteration?: number;
  max_iterations?: number;
  current_tool?: string | null;
  error?: string | null;
  events?: ProgressEvent[];
  next_seq?: number;
};

/**
 * Transcribe a base64-encoded audio blob via the Rust → Python STT proxy.
 * Returns the recognised text on success; throws with a human-readable message
 * on failure (STT not configured, network error, etc.).
 */
/** Generate TTS audio for the given text, returns base64-encoded MP3 data */
export async function cmdTtsSpeak(text: string): Promise<string> {
  return invoke<string>("cmd_tts_speak", { text });
}

export async function cmdTranscribe(audioB64: string, mime: string): Promise<string> {
  return invoke<string>("cmd_transcribe", { audioB64, mime });
}

/**
 * Local-STT model presence on disk.
 *
 * Returned by the Python ``GET /api/desk/stt-model/status`` endpoint; used
 * by the mic UI to decide whether to show the first-time download prompt.
 */
export type SttModelStatus = {
  downloaded: boolean;
  size: number;
  path: string;
};

export async function cmdSttModelStatus(): Promise<SttModelStatus> {
  return invoke<SttModelStatus>("cmd_stt_model_status");
}

export type SttModelDownloadResult = {
  ok: boolean;
  size: number;
  path: string;
  source?: string;
  already?: boolean;
};

/**
 * Download the bundled local STT GGML model (~57 MB) on demand.
 *
 * Resolves on success with the size + final path; rejects with a string
 * error if the download fails (timeout, both mirrors blocked, hash
 * mismatch, …). The Python side renames atomically so a partial file
 * never masquerades as a complete one.
 */
export async function cmdSttModelDownload(): Promise<SttModelDownloadResult> {
  return invoke<SttModelDownloadResult>("cmd_stt_model_download");
}

export type LoadPackageStatus = {
  id: string;
  title: string;
  description: string;
  feature: string;
  modelId: string;
  sizeMb: number;
  downloaded: boolean;
  size: number;
  path: string;
  realPath?: string;
  agentPath?: string;
  workspaceIndexPath?: string;
  source?: string;
  sources?: LoadPackageSource[];
  usedByCapabilities?: Array<{ id: string; title: string }>;
  job?: LoadPackageJob | null;
};

export type LoadPackageSource = {
  id: string;
  label: string;
  url: string;
};

export type LoadPackageJob = {
  packageId: string;
  status: "running" | "done" | "error" | string;
  phase: "queued" | "downloading" | "checking" | "installing" | "done" | "error" | string;
  downloadedBytes: number;
  totalBytes: number;
  percent: number | null;
  source?: string;
  error?: string;
  startedAt?: number;
  updatedAt?: number;
};

export type LoadPackagesResponse = {
  packages: LoadPackageStatus[];
};

export type LoadPackageDownloadResult = {
  ok: boolean;
  size?: number;
  path?: string;
  source?: string;
  already?: boolean;
};

function hasTauriInvoke(): boolean {
  const internals = typeof window === "undefined"
    ? undefined
    : (window as unknown as { __TAURI_INTERNALS__?: { invoke?: unknown } }).__TAURI_INTERNALS__;
  return typeof internals?.invoke === "function";
}

function ensureLoadPackageBridge(): void {
  if (!hasTauriInvoke()) {
    throw new Error("desktop_bridge_unavailable");
  }
}

export async function cmdLoadPackages(): Promise<LoadPackagesResponse> {
  ensureLoadPackageBridge();
  return invoke<LoadPackagesResponse>("cmd_load_packages");
}

export async function cmdLoadPackageDownload(packageId: string): Promise<LoadPackageStatus> {
  ensureLoadPackageBridge();
  return invoke<LoadPackageStatus>("cmd_load_package_download", { packageId });
}

export async function cmdLoadPackageDelete(packageId: string): Promise<{ ok: boolean; removed?: boolean; path?: string }> {
  ensureLoadPackageBridge();
  return invoke("cmd_load_package_delete", { packageId });
}

export function cmdChatPreview(
  sessionId: string,
  since?: number
): Promise<ChatPreviewResponse> {
  return invoke("cmd_chat_preview", { sessionId, since: since ?? 0 });
}

export function isRecord(x: unknown): x is Record<string, unknown> {
  return x !== null && typeof x === "object" && !Array.isArray(x);
}

export function parseChatSend(
  r: unknown
):
  | { ok: true; sessionId: string; text: string; model: string }
  | { ok: false; err: string } {
  if (!isRecord(r)) {
    return { ok: false, err: "Invalid response" };
  }
  if (r.ok === true) {
    return {
      ok: true,
      sessionId: String(r.session_id ?? ""),
      text: String(r.final_response ?? ""),
      model: String((r as { model?: unknown }).model ?? ""),
    };
  }
  const detail = typeof r.detail === "string" ? r.detail : "";
  const err = String((r as { error?: unknown }).error ?? "error");
  return { ok: false, err: detail || err };
}
