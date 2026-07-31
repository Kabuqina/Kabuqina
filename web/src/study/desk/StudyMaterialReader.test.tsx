// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { I18nProvider } from "../../lib/i18n";
import { parseReaderPages, StudyMaterialReader } from "./StudyMaterialReader";

describe("StudyMaterialReader", () => {
  beforeEach(() => {
    window.localStorage.clear();
    vi.restoreAllMocks();
  });

  it("splits extracted PDF text into separately remembered pages", () => {
    expect(parseReaderPages("<!-- page:7 -->\n甲\n\n<!-- page:8 -->\n乙", 1)).toEqual([
      { page: 7, text: "甲" },
      { page: 8, text: "乙" },
    ]);
  });

  it("opens the real file outline and jumps without leaving the Study surface", async () => {
    const user = userEvent.setup();
    const readMaterial = vi.fn().mockImplementation(async (_space, artifact, start, end) => ({
      artifactId: artifact,
      title: "Python程序设计",
      filename: "Python程序设计.pdf",
      suffix: ".pdf",
      totalPages: 342,
      pageStart: start,
      pageEnd: end,
      content: `<!-- page:${start} -->\n第 ${start} 页正文`,
      outline: [
        { id: "chapter-1", title: "第1章 计算机和程序", level: 1, page: 7 },
        { id: "chapter-2", title: "第2章 编写简单程序", level: 1, page: 31 },
      ],
      textQuality: "sufficient",
      warning: "",
    }));
    const onClose = vi.fn();

    render(
      <I18nProvider>
        <StudyMaterialReader
          spaceId="python-course"
          artifactId="material-1"
          initialPage={7}
          readMaterial={readMaterial}
          onClose={onClose}
        />
      </I18nProvider>,
    );

    expect(await screen.findByRole("heading", { name: "Python程序设计" })).toBeInTheDocument();
    expect(screen.getByText("第 7 页正文")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /第2章 编写简单程序/ }));
    await waitFor(() => expect(readMaterial).toHaveBeenLastCalledWith("python-course", "material-1", 31, 36));
    expect(await screen.findByText("第 31 页正文")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "放回去" }));
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("soft-deletes from the reader while promising to retain generated learning data", async () => {
    const user = userEvent.setup();
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(true);
    const deleteMaterial = vi.fn().mockResolvedValue({
      artifact_id: "material-1",
      status: "deleted" as const,
    });
    const onDeleted = vi.fn();
    const onClose = vi.fn();
    window.localStorage.setItem(
      "kabuqina.study.material-reader.v1:python-course:material-1",
      "7",
    );

    render(
      <I18nProvider>
        <StudyMaterialReader
          spaceId="python-course"
          artifactId="material-1"
          readMaterial={vi.fn().mockResolvedValue({
            artifactId: "material-1",
            title: "Python程序设计",
            filename: "Python程序设计.pdf",
            suffix: ".pdf",
            totalPages: 42,
            pageStart: 1,
            pageEnd: 6,
            content: "正文",
            outline: [],
            textQuality: "sufficient",
            warning: "",
          })}
          deleteMaterial={deleteMaterial}
          onDeleted={onDeleted}
          onClose={onClose}
        />
      </I18nProvider>,
    );

    await screen.findByRole("heading", { name: "Python程序设计" });
    await user.click(screen.getByRole("button", { name: "删除这份知识源" }));

    expect(confirm).toHaveBeenCalledWith(expect.stringContaining("已经生成的计划、学习内容和练习记录会保留"));
    await waitFor(() => expect(deleteMaterial).toHaveBeenCalledWith("python-course", "material-1"));
    expect(onDeleted).toHaveBeenCalledOnce();
    expect(onClose).toHaveBeenCalledOnce();
    expect(window.localStorage.getItem(
      "kabuqina.study.material-reader.v1:python-course:material-1",
    )).toBeNull();
  });
});
