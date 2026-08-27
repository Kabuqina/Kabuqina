// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useCallback, useEffect, useReducer, useRef } from "react";
import type { CapturePurpose, StudyCaptureErrorCode } from "../../chat/study/study-capture-api";
import { captureReducer, initialCaptureState, type CaptureState } from "./captureState";
import { mockCaptureRepository, type MockCaptureRepository } from "./mockCaptureRepository";

/**
 * 「纸上来的」右页：拍照/上传 → 裁剪 → 转写确认 → 下一步提示/完整答案 → 错题三态。
 * 原型右页的 0/6/1/2/3/4/5 步在这里是正交的 capture 状态机（`captureState.ts`），
 * 数据全部来自 MockStudyCaptureRepository——真管线接进来时只换 repository。
 */
export function StudyCaptureFlow({
  purpose,
  repository = mockCaptureRepository,
}: {
  purpose: CapturePurpose;
  repository?: MockCaptureRepository;
}) {
  const [state, dispatch] = useReducer(captureReducer, initialCaptureState);
  // 防止慢请求把旧状态盖到新流程上（重拍/放弃后又来了上一个响应）。
  const generationRef = useRef(0);
  const beginGeneration = useCallback(() => ++generationRef.current, []);
  const isCurrent = useCallback((generation: number) => generation === generationRef.current, []);

  // 转写确认之后拉下一步提示或讲评草稿——取决于这次拍的目的。
  useEffect(() => {
    const captureId = state.capture_id;
    if (!captureId) return;
    if (state.status === "assisting" && !state.assistance) {
      const generation = beginGeneration();
      void repository.requestAssistance(captureId, "next_step").then(
        (assistance) => { if (isCurrent(generation)) dispatch({ type: "request_assistance", assistance }); },
        (error) => {
          if (isCurrent(generation)) dispatch({
            type: "capture_failed",
            code: error?.code ?? "vision_unreadable",
            message: error?.message ?? "提示暂时没有生成，请重试。",
          });
        },
      );
    }
    if (state.status === "reviewing" && !state.review) {
      const generation = beginGeneration();
      void repository.requestReview(captureId).then(
        (review) => { if (isCurrent(generation)) dispatch({ type: "request_review", review }); },
        (error) => {
          if (isCurrent(generation)) dispatch({
            type: "capture_failed",
            code: error?.code ?? "vision_unreadable",
            message: error?.message ?? "讲评暂时没有生成，请重试。",
          });
        },
      );
    }
  }, [beginGeneration, isCurrent, repository, state.assistance, state.capture_id, state.review, state.status]);

  const startChoosing = useCallback(() => {
    beginGeneration();
    dispatch({ type: "start_choosing", purpose });
  }, [beginGeneration, purpose]);

  const selectSource = useCallback((source: "camera" | "upload") => {
    beginGeneration();
    dispatch({ type: "source_selected", source });
  }, [beginGeneration]);

  // 裁剪页「就这样，看一下」：mock 在此刻才真正 stage + transcribe。
  const submitCrop = useCallback(() => {
    if (state.status !== "cropping" || !state.source || !state.purpose) return;
    const generation = beginGeneration();
    const stage = state.source === "camera"
      ? repository.stageCamera(new Blob(["mock-camera-frame"], { type: "image/png" }), state.purpose)
      : repository.stageUpload(new File(["mock-upload"], "paper.png", { type: "image/png" }), state.purpose);
    void stage.then(
      async (session) => {
        if (!isCurrent(generation)) return;
        dispatch({ type: "capture_submitted", session });
        try {
          const transcription = await repository.transcribe(session);
          if (isCurrent(generation)) dispatch({ type: "transcription_received", transcription });
        } catch (error: unknown) {
          const captureError = error as { code?: StudyCaptureErrorCode; message?: string };
          if (isCurrent(generation)) dispatch({
            type: "capture_failed",
            code: captureError?.code ?? "vision_unreadable",
            message: captureError?.message ?? "这张照片暂时读不出来，可以重拍一张。",
          });
        }
      },
      (error) => {
        if (isCurrent(generation)) dispatch({
          type: "capture_failed",
          code: error?.code ?? "capture_invalid_image",
          message: error?.message ?? "这张图片没有传上去，请重试。",
        });
      },
    );
  }, [beginGeneration, isCurrent, repository, state.purpose, state.source, state.status]);

  const confirmTranscription = useCallback(() => {
    beginGeneration();
    dispatch({ type: "transcription_confirmed" });
  }, [beginGeneration]);

  const requestFullAnswer = useCallback(() => {
    const captureId = state.capture_id;
    if (!captureId) return;
    const generation = beginGeneration();
    void repository.requestAssistance(captureId, "full_answer").then(
      (assistance) => { if (isCurrent(generation)) dispatch({ type: "request_assistance", assistance }); },
      (error) => {
        if (isCurrent(generation)) dispatch({
          type: "capture_failed",
          code: error?.code ?? "vision_unreadable",
          message: error?.message ?? "答案暂时没有生成，请重试。",
        });
      },
    );
  }, [beginGeneration, isCurrent, repository, state.capture_id]);

  const queueForReview = useCallback(() => {
    const captureId = state.capture_id;
    if (!captureId) return;
    const generation = beginGeneration();
    void repository.requestReview(captureId).then(
      (review) => { if (isCurrent(generation)) dispatch({ type: "request_review", review }); },
      (error) => {
        if (isCurrent(generation)) dispatch({
          type: "capture_failed",
          code: error?.code ?? "vision_unreadable",
          message: error?.message ?? "讲评暂时没有生成，请重试。",
        });
      },
    );
  }, [beginGeneration, isCurrent, repository, state.capture_id]);

  const decideWrongbook = useCallback((decision: "wrong" | "correct" | "unreadable") => {
    const captureId = state.capture_id;
    if (!captureId) return;
    const generation = beginGeneration();
    void repository.confirmWrongbook(captureId, decision).then(
      () => { if (isCurrent(generation)) dispatch({ type: "wrongbook_confirmed" }); },
      (error) => {
        if (isCurrent(generation)) dispatch({
          type: "capture_failed",
          code: error?.code ?? "wrongbook_idempotency_conflict",
          message: error?.message ?? "错题本暂时没有保存，请重试。",
        });
      },
    );
  }, [beginGeneration, isCurrent, repository, state.capture_id]);

  const abandon = useCallback(() => {
    const captureId = state.capture_id;
    beginGeneration();
    if (captureId) void repository.abandon(captureId);
    dispatch({ type: "abandon" });
  }, [beginGeneration, repository, state.capture_id]);

  // 「重拍」= 放弃这张，回到选来源。
  const retake = useCallback(() => {
    const captureId = state.capture_id;
    beginGeneration();
    if (captureId) void repository.abandon(captureId);
    dispatch({ type: "abandon" });
    dispatch({ type: "start_choosing", purpose });
  }, [beginGeneration, purpose, repository, state.capture_id]);

  return (
    <section className="kd-capture" aria-label="纸上来的" data-status={state.status}>
      <CaptureBody
        state={state}
        purpose={purpose}
        onStart={startChoosing}
        onSelectSource={selectSource}
        onSubmitCrop={submitCrop}
        onConfirmTranscription={confirmTranscription}
        onRetake={retake}
        onRequestFullAnswer={requestFullAnswer}
        onQueueForReview={queueForReview}
        onDecideWrongbook={decideWrongbook}
        onAbandon={abandon}
        onRetry={() => dispatch({ type: "retry" })}
      />
    </section>
  );
}

function CaptureBody({
  state,
  purpose,
  onStart,
  onSelectSource,
  onSubmitCrop,
  onConfirmTranscription,
  onRetake,
  onRequestFullAnswer,
  onQueueForReview,
  onDecideWrongbook,
  onAbandon,
  onRetry,
}: {
  state: CaptureState;
  purpose: CapturePurpose;
  onStart: () => void;
  onSelectSource: (source: "camera" | "upload") => void;
  onSubmitCrop: () => void;
  onConfirmTranscription: () => void;
  onRetake: () => void;
  onRequestFullAnswer: () => void;
  onQueueForReview: () => void;
  onDecideWrongbook: (decision: "wrong" | "correct" | "unreadable") => void;
  onAbandon: () => void;
  onRetry: () => void;
}) {
  if (state.status === "idle") {
    return (
      <div className="kd-capture-empty">
        <p className="kd-page-kicker">纸上来的</p>
        <p>{purpose === "review"
          ? "现在轮到纸了。写完拍给我看，我对着你的步骤讲。"
          : "现在轮到纸了。写到哪一步卡住，就拍那一步。"}</p>
        <button type="button" className="kd-primary" onClick={onStart}>拍一张</button>
      </div>
    );
  }

  if (state.status === "choosing") {
    return (
      <div>
        <p className="kd-page-kicker">照片从哪里来</p>
        <p>拍一张新的，或者从电脑里选一张。两种方式都会先进入同一个裁剪步骤。</p>
        <div className="kd-capture-sources">
          <button type="button" onClick={() => onSelectSource("camera")}>
            <strong>拍照</strong>
            <span>使用电脑上可用的摄像头</span>
          </button>
          <button type="button" onClick={() => onSelectSource("upload")}>
            <strong>上传图片</strong>
            <span>从电脑选择 JPG、PNG 或 WebP</span>
          </button>
        </div>
        <p className="kd-capture-note">没有可用摄像头时仍可上传图片，不会挡住后面的识别与讲评。</p>
        <button type="button" onClick={onAbandon}>先不拍了</button>
      </div>
    );
  }

  if (state.status === "cropping") {
    return (
      <div>
        <p className="kd-page-kicker">裁到答题区</p>
        <p className="kd-capture-note">来自：{state.source === "camera" ? "拍照" : "上传图片"}</p>
        <div className="kd-capture-preview" aria-label="你的草稿纸">你的草稿纸</div>
        <div className="kd-inline-actions">
          <button type="button">旋转</button>
          <button type="button">重裁</button>
          <button type="button">转灰度（可撤销）</button>
        </div>
        <p className="kd-capture-note">3024×4032 → 1280×960 ／ 约 1.1k image tokens</p>
        <button type="button" className="kd-primary" onClick={onSubmitCrop}>就这样，看一下</button>
      </div>
    );
  }

  if (state.status === "submitting" || state.status === "transcribing") {
    return <p role="status">正在读这张照片…</p>;
  }

  if (state.status === "confirming" && state.transcription) {
    return (
      <div>
        <p className="kd-page-kicker">我读到的是这样</p>
        <p className="kd-capture-note">置信度：{state.transcription.confidence_band}</p>
        <ol className="kd-capture-lines">
          {state.transcription.lines.map((line) => (
            <li key={line.index} data-unreadable={line.unreadable || undefined}>
              {line.text}
            </li>
          ))}
        </ol>
        <div className="kd-inline-actions">
          <button type="button" className="kd-primary" onClick={onConfirmTranscription}>对，就是这样</button>
          <button type="button" onClick={onRetake}>重拍这张</button>
        </div>
      </div>
    );
  }

  if (state.status === "assisting") {
    if (!state.assistance) return <p role="status">小娜正在看这一步…</p>;
    if (state.assistance.mode === "full_answer") {
      return (
        <div>
          <p className="kd-page-kicker">完整答案</p>
          <p>{state.assistance.answer}</p>
          {state.assistance.knowledge_points?.length ? (
            <p className="kd-capture-note">
              这题建立在 {state.assistance.knowledge_points.length} 个知识点上：
              {state.assistance.knowledge_points.join("、")}。
              {state.assistance.skipped_items?.length ? `你跳过的是：${state.assistance.skipped_items.join("、")}。` : null}
            </p>
          ) : null}
          <button type="button" className="kd-primary" onClick={onQueueForReview}>加进复习队列</button>
        </div>
      );
    }
    return (
      <div>
        <p className="kd-page-kicker">下一步</p>
        <p>{state.assistance.hint}</p>
        <div className="kd-inline-actions">
          <button type="button" onClick={onAbandon}>回纸上继续</button>
        </div>
        <button type="button" className="kd-capture-escape" onClick={onRequestFullAnswer}>
          我不想推了，直接给我答案
        </button>
      </div>
    );
  }

  if (state.status === "reviewing") {
    if (!state.review) return <p role="status">小娜正在对照你的步骤…</p>;
    return (
      <div>
        <p className="kd-page-kicker">这道算做错了吗</p>
        <p><strong>{state.review.deviation_start}</strong>{state.review.basis}</p>
        {state.review.uncertain_items.length ? (
          <p className="kd-capture-note">不确定的地方：{state.review.uncertain_items.join("；")}</p>
        ) : null}
        <div className="kd-inline-actions">
          <button type="button" className="kd-primary" onClick={() => onDecideWrongbook("wrong")}>
            确实做错 → 进错题本
          </button>
          <button type="button" onClick={() => onDecideWrongbook("correct")}>其实做对了</button>
          <button type="button" onClick={onRetake}>看不清，重拍</button>
        </div>
      </div>
    );
  }

  // failed：保留学生能懂的下一步，不暴露 provider / 路径 / token。
  return (
    <div role="alert">
      <p className="kd-page-kicker">这张照片没走通</p>
      <p>{state.error_message ?? "出了点问题，请重试。"}</p>
      <div className="kd-inline-actions">
        <button type="button" className="kd-primary" onClick={onRetry}>重试</button>
        <button type="button" onClick={onAbandon}>不拍了</button>
      </div>
    </div>
  );
}
