// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useCallback, useEffect, useRef, useState } from "react";
import { cmdSttModelDownload, cmdSttModelStatus, cmdTranscribe } from "../chat-api";

export type RecorderState =
  | "idle"
  | "recording"
  | "processing"
  | "downloading-model";

const PREFERRED_MIME_TYPES = [
  "audio/webm;codecs=opus",
  "audio/webm",
  "audio/ogg;codecs=opus",
];

export function getSupportedMimeType(): string {
  if (typeof MediaRecorder === "undefined") return "";
  return PREFERRED_MIME_TYPES.find((t) => MediaRecorder.isTypeSupported(t)) ?? "";
}

export interface UseVoiceRecorderReturn {
  recorderState: RecorderState;
  durationMs: number;
  mimeTypeSupported: boolean;
  start: () => Promise<void>;
  stop: () => void;
  /**
   * Probe the bundled local-STT model on disk. Cheap (single Tauri RT call).
   * Returns ``true`` if already present; ``false`` if first-use download
   * needed.
   */
  isLocalModelReady: () => Promise<boolean>;
  /** Trigger the lazy-download. Surfaces ``downloading-model`` state. */
  downloadLocalModel: () => Promise<boolean>;
}

export function useVoiceRecorder(opts: {
  maxDurationMs?: number;
  onTranscript: (text: string) => void;
  onError: (err: string) => void;
}): UseVoiceRecorderReturn {
  const { maxDurationMs = 60_000, onTranscript, onError } = opts;

  const [recorderState, setRecorderState] = useState<RecorderState>("idle");
  const [durationMs, setDurationMs] = useState(0);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const startTimeRef = useRef(0);
  const tickRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const maxTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const streamRef = useRef<MediaStream | null>(null);

  // Store callbacks in refs so start/stop don't re-create on every render.
  const onTranscriptRef = useRef(onTranscript);
  const onErrorRef = useRef(onError);
  onTranscriptRef.current = onTranscript;
  onErrorRef.current = onError;

  const mimeType = getSupportedMimeType();
  const mimeTypeSupported = mimeType !== "";

  const clearTimers = useCallback(() => {
    if (tickRef.current) {
      clearInterval(tickRef.current);
      tickRef.current = null;
    }
    if (maxTimerRef.current) {
      clearTimeout(maxTimerRef.current);
      maxTimerRef.current = null;
    }
  }, []);

  const stopRecording = useCallback(() => {
    clearTimers();
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
      mediaRecorderRef.current.stop();
    }
  }, [clearTimers]);

  const start = useCallback(async () => {
    if (recorderState !== "idle") return;

    if (!mimeTypeSupported) {
      onErrorRef.current("此设备不支持浏览器录音（WebView2 版本过低）。");
      return;
    }

    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (err) {
      const name = (err as Error).name;
      onErrorRef.current(
        name === "NotAllowedError"
          ? "麦克风权限被拒绝，请在系统或浏览器中允许后重试。"
          : "无法打开麦克风，请检查设备连接。"
      );
      return;
    }

    streamRef.current = stream;
    chunksRef.current = [];

    const mr = new MediaRecorder(stream, { mimeType });
    mediaRecorderRef.current = mr;

    mr.ondataavailable = (e) => {
      if (e.data.size > 0) chunksRef.current.push(e.data);
    };

    mr.onstop = () => {
      stream.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
      setRecorderState("processing");
      setDurationMs(0);

      const blob = new Blob(chunksRef.current, { type: mr.mimeType || mimeType });
      chunksRef.current = [];

      const reader = new FileReader();
      reader.onload = async () => {
        try {
          const s = reader.result as string;
          const sep = s.indexOf(";base64,");
          if (sep < 0) throw new Error("bad data url");
          const audioB64 = s.slice(sep + 8);
          const effectiveMime = mr.mimeType || mimeType;
          const transcript = await cmdTranscribe(audioB64, effectiveMime);
          onTranscriptRef.current(transcript);
        } catch (e) {
          const msg = e instanceof Error ? e.message : String(e);
          onErrorRef.current(msg || "语音识别失败，请重试。");
        } finally {
          setRecorderState("idle");
        }
      };
      reader.onerror = () => {
        onErrorRef.current("录音数据读取失败。");
        setRecorderState("idle");
      };
      reader.readAsDataURL(blob);
    };

    mr.start(250);
    startTimeRef.current = Date.now();
    setDurationMs(0);
    setRecorderState("recording");

    tickRef.current = setInterval(
      () => setDurationMs(Date.now() - startTimeRef.current),
      200
    );
    maxTimerRef.current = setTimeout(stopRecording, maxDurationMs);
  }, [recorderState, mimeType, mimeTypeSupported, maxDurationMs, stopRecording]);

  const isLocalModelReady = useCallback(async (): Promise<boolean> => {
    try {
      const s = await cmdSttModelStatus();
      return !!s.downloaded;
    } catch {
      // Backend may not be ready / endpoint missing on older bundles —
      // assume ready so the user still gets the cloud-STT path attempt
      // (transcribe will surface a real error if it actually fails).
      return true;
    }
  }, []);

  const downloadLocalModel = useCallback(async (): Promise<boolean> => {
    if (recorderState !== "idle") return false;
    setRecorderState("downloading-model");
    try {
      await cmdSttModelDownload();
      setRecorderState("idle");
      return true;
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      onErrorRef.current(msg || "stt_model_download_failed");
      setRecorderState("idle");
      return false;
    }
  }, [recorderState]);

  useEffect(() => {
    return () => {
      clearTimers();
      if (mediaRecorderRef.current?.state !== "inactive") {
        mediaRecorderRef.current?.stop();
      }
      streamRef.current?.getTracks().forEach((t) => t.stop());
    };
  }, [clearTimers]);

  return {
    recorderState,
    durationMs,
    mimeTypeSupported,
    start,
    stop: stopRecording,
    isLocalModelReady,
    downloadLocalModel,
  };
}
