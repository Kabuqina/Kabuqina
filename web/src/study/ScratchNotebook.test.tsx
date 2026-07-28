// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { I18nProvider } from "../lib/i18n";
import type { StudyRepository, StudySpaceSummary } from "./repository";
import { StudyRepositoryProvider } from "./repositoryContext";
import { ScratchNotebook } from "./ScratchNotebook";

const courses: StudySpaceSummary[] = [
  { id: "space-a", title: "高等数学", status: "active", isCurrent: false, kind: "course" },
  { id: "space-b", title: "大学物理", status: "active", isCurrent: false, kind: "course" },
];

function makeRepository(): StudyRepository {
  return {
    loadScratch: vi.fn().mockResolvedValue({
      pad: "",
      notes: [
        { id: "n1", text: "数学里的等号，是在说两个写法指的是同一个东西。", origin: "来自对话 · 昨天" },
      ],
    }),
    saveScratchPad: vi.fn().mockResolvedValue(undefined),
    fileScratchNote: vi.fn().mockResolvedValue(undefined),
  } as unknown as StudyRepository;
}

function renderScratch(overrides: Partial<StudyRepository> = {}) {
  const repository = { ...makeRepository(), ...overrides } as StudyRepository;
  render(
    <I18nProvider>
      <StudyRepositoryProvider repository={repository}>
        <ScratchNotebook spaceId="scratch-1" courses={courses} />
      </StudyRepositoryProvider>
    </I18nProvider>,
  );
  return repository;
}

// 假计时器一旦泄漏，后面每个用例都会挂在 5s 超时上——失败的用例反而更需要这条兜底。
afterEach(() => vi.useRealTimers());

describe("ScratchNotebook", () => {
  /**
   * 这一条钉住的是产品红线，不是实现：杂记本是**留白**，不是待办箱。
   * 一旦这里冒出数字或「待整理」，它就变成了又一个催你的地方。
   */
  it("counts nothing and labels nothing as pending", async () => {
    renderScratch();
    await screen.findByText(/数学里的等号/);
    const page = screen.getByLabelText("杂记本");
    expect(page.textContent).not.toMatch(/待整理|未整理|\d+\s*条|共\s*\d+/);
    // 没有徽章、没有计数元素。
    expect(page.querySelector("[class*=badge], [class*=count]")).toBeNull();
  });

  it("saves the pad as one whole page once typing settles", async () => {
    const user = userEvent.setup();
    const repository = renderScratch();
    const pad = await screen.findByLabelText("随手写");

    await user.type(pad, "想到一句");
    await waitFor(
      () => expect(repository.saveScratchPad).toHaveBeenCalled(),
      { timeout: 2000 },
    );
    const calls = (repository.saveScratchPad as ReturnType<typeof vi.fn>).mock.calls;
    // 随手写就一页纸：全文覆盖，不做增量 diff。
    expect(calls[calls.length - 1][1]).toBe("想到一句");
    expect(calls[calls.length - 1][0]).toBe("scratch-1");
  });

  it("files a note into a chosen course book and takes it off the page", async () => {
    const user = userEvent.setup();
    const repository = renderScratch();
    await screen.findByText(/数学里的等号/);

    await user.click(screen.getByRole("button", { name: "归到某一本" }));
    // 归本只列课程本；杂记本不能归到自己身上。
    expect(screen.getByRole("button", { name: "高等数学" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "大学物理" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "高等数学" }));

    expect(repository.fileScratchNote).toHaveBeenCalledWith(
      "scratch-1", "n1", "space-a", expect.any(AbortSignal),
    );
    await waitFor(() => expect(screen.queryByText(/数学里的等号/)).not.toBeInTheDocument());
  });

  it("puts a failed filing back on the page instead of swallowing it", async () => {
    const user = userEvent.setup();
    renderScratch({ fileScratchNote: vi.fn().mockRejectedValue(new Error("boom")) });
    await screen.findByText(/数学里的等号/);

    await user.click(screen.getByRole("button", { name: "归到某一本" }));
    await user.click(screen.getByRole("button", { name: "高等数学" }));
    // 归本失败＝这条还在杂记本里，不能凭空消失。
    await waitFor(() => expect(screen.getByText(/数学里的等号/)).toBeInTheDocument());
  });

  it("says so honestly when the scrap book is not wired up", async () => {
    renderScratch({ loadScratch: vi.fn().mockRejectedValue(new Error("unavailable")) });
    expect(await screen.findByRole("alert")).toHaveTextContent("杂记本还没接好");
  });
});
