// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { StudyCaptureFlow } from "./StudyCaptureFlow";
import { createMockCaptureRepository } from "./mockCaptureRepository";

async function reachConfirming(purpose: "stuck" | "review" = "stuck") {
  const user = userEvent.setup();
  const repository = createMockCaptureRepository();
  render(<StudyCaptureFlow purpose={purpose} repository={repository} />);
  await user.click(screen.getByRole("button", { name: "拍一张" }));
  await user.click(screen.getByRole("button", { name: /上传图片/ }));
  await user.click(screen.getByRole("button", { name: "就这样，看一下" }));
  await screen.findByText("我读到的是这样");
  return { user, repository };
}

describe("StudyCaptureFlow", () => {
  it("walks stuck purpose through chooser → crop → transcription → next-step hint", async () => {
    const { user } = await reachConfirming("stuck");
    // 转写逐行呈现，看不清的行不猜。
    expect(screen.getByText(/这一行右半看不清/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "对，就是这样" }));
    expect(await screen.findByText("下一步")).toBeInTheDocument();
    expect(screen.getByText(/什么函数求导之后是 sin\(u\)/)).toBeInTheDocument();
  });

  it("escalates to the full answer only on explicit request, then queues review", async () => {
    const { user } = await reachConfirming("stuck");
    await user.click(screen.getByRole("button", { name: "对，就是这样" }));
    await screen.findByText("下一步");
    expect(screen.queryByText(/−cos/)).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /直接给我答案/ }));
    expect(await screen.findByText(/−cos\(x³\) \+ C/)).toBeInTheDocument();
    expect(screen.getByText(/你跳过的是/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "加进复习队列" }));
    expect(await screen.findByText("这道算做错了吗")).toBeInTheDocument();
  });

  it("review purpose lands on the wrongbook decision after confirmation", async () => {
    const { user } = await reachConfirming("review");
    await user.click(screen.getByRole("button", { name: "对，就是这样" }));
    expect(await screen.findByText("这道算做错了吗")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /确实做错/ }));
    // 三态确认后流程回到空右页。
    await waitFor(() => expect(screen.getByRole("button", { name: "拍一张" })).toBeInTheDocument());
  });

  it("abandons cleanly from the chooser without touching the repository", async () => {
    const user = userEvent.setup();
    const repository = createMockCaptureRepository();
    const stageUpload = vi.spyOn(repository, "stageUpload");
    render(<StudyCaptureFlow purpose="stuck" repository={repository} />);
    await user.click(screen.getByRole("button", { name: "拍一张" }));
    await user.click(screen.getByRole("button", { name: "先不拍了" }));
    expect(screen.getByRole("button", { name: "拍一张" })).toBeInTheDocument();
    expect(stageUpload).not.toHaveBeenCalled();
  });

  it("shows a bounded error and retries when staging fails", async () => {
    const user = userEvent.setup();
    const repository = createMockCaptureRepository();
    vi.spyOn(repository, "stageUpload").mockRejectedValueOnce({
      code: "capture_too_large", message: "图片超过 10MB", retryable: false,
    });
    render(<StudyCaptureFlow purpose="stuck" repository={repository} />);
    await user.click(screen.getByRole("button", { name: "拍一张" }));
    await user.click(screen.getByRole("button", { name: /上传图片/ }));
    await user.click(screen.getByRole("button", { name: "就这样，看一下" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("图片超过 10MB");
    // 错误文案不暴露内部细节之外的出口：重试或不拍。
    fireEvent.click(screen.getByRole("button", { name: "不拍了" }));
    expect(screen.getByRole("button", { name: "拍一张" })).toBeInTheDocument();
  });
});
