// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { I18nProvider } from "../lib/i18n";
import { GatherFromStudy } from "./GatherFromStudy";

const mocks = vi.hoisted(() => ({
  spaces: vi.fn(),
  summaries: vi.fn(),
  gather: vi.fn(),
}));

vi.mock("../chat/study/study-api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../chat/study/study-api")>()),
  cmdStudySpaces: mocks.spaces,
  cmdStudyArtifactSummaries: mocks.summaries,
}));

vi.mock("./studio-api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("./studio-api")>()),
  cmdStudioGatherSources: mocks.gather,
}));

afterEach(() => vi.clearAllMocks());

function seed() {
  mocks.spaces.mockResolvedValue({
    spaces: [{ space_id: "math", title: "高等数学" }],
  });
  mocks.summaries.mockResolvedValue({
    items: [
      { artifact_id: "a1", kind: "knowledge", title: "极限的运算法则", status: "active" },
      { artifact_id: "a2", kind: "quiz", title: "未定式自测", status: "active" },
    ],
    count: 2,
  });
}

function renderGather() {
  const onClose = vi.fn();
  const onGathered = vi.fn();
  render(
    <I18nProvider>
      <GatherFromStudy projectId="p1" onClose={onClose} onGathered={onGathered} />
    </I18nProvider>,
  );
  return { onClose, onGathered };
}

describe("GatherFromStudy", () => {
  it("reads real course content to pick from", async () => {
    seed();
    renderGather();
    expect(await screen.findByText("极限的运算法则")).toBeInTheDocument();
    expect(screen.getByText("未定式自测")).toBeInTheDocument();
    expect(mocks.summaries).toHaveBeenCalledWith({ spaceId: "math", status: "active" });
  });

  it("will not advance until something is chosen", async () => {
    seed();
    renderGather();
    await screen.findByText("极限的运算法则");
    expect(screen.getByRole("button", { name: /看看会取走什么/ })).toBeDisabled();
  });

  it("previews exactly what will be taken before creating any snapshot", async () => {
    const user = userEvent.setup();
    seed();
    renderGather();
    await screen.findByText("极限的运算法则");

    await user.click(screen.getByRole("checkbox", { name: /极限的运算法则/ }));
    await user.click(screen.getByRole("button", { name: /看看会取走什么/ }));

    // 预览列出被选中的那一项，并说明取走的是快照、原件不动。
    expect(screen.getByText(/确认后会生成下面这些只读快照/)).toBeInTheDocument();
    expect(screen.getByText(/课程本原件不动/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /取这 1 项/ })).toBeInTheDocument();
    // 未选的那一项不该混进来。
    expect(screen.queryByText("未定式自测")).not.toBeInTheDocument();
    // 关键：预览阶段还没有写任何快照。
    expect(mocks.gather).not.toHaveBeenCalled();
  });

  it("sends references rather than copied content", async () => {
    const user = userEvent.setup();
    seed();
    mocks.gather.mockResolvedValue({ id: "p1" });
    const { onGathered, onClose } = renderGather();
    await screen.findByText("极限的运算法则");

    await user.click(screen.getByRole("checkbox", { name: /极限的运算法则/ }));
    await user.click(screen.getByRole("button", { name: /看看会取走什么/ }));
    await user.click(screen.getByRole("button", { name: /取这 1 项/ }));

    // 架构 §4.2：前端交引用，由后端读原对象生成快照，正文不经前端搬运。
    await waitFor(() =>
      expect(mocks.gather).toHaveBeenCalledWith("p1", [
        { kind: "study_artifact", spaceId: "math", artifactId: "a1" },
      ]),
    );
    await waitFor(() => expect(onGathered).toHaveBeenCalled());
    expect(onClose).toHaveBeenCalled();
  });

  it("says nothing was taken when the write fails", async () => {
    const user = userEvent.setup();
    seed();
    mocks.gather.mockRejectedValue(new Error("boom"));
    const { onGathered } = renderGather();
    await screen.findByText("极限的运算法则");

    await user.click(screen.getByRole("checkbox", { name: /极限的运算法则/ }));
    await user.click(screen.getByRole("button", { name: /看看会取走什么/ }));
    await user.click(screen.getByRole("button", { name: /取这 1 项/ }));

    expect(await screen.findByRole("alert")).toHaveTextContent("什么都没有带走");
    expect(onGathered).not.toHaveBeenCalled();
  });
});
