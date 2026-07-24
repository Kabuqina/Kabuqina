// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { DeskWorkFolder } from "./DeskWorkFolder";

const materials = {
  title: "本课材料",
  hint: "选择材料",
  items: [
    { id: "source-a", title: "教材第二章", kind: "resource_pack", status: "active" },
    { id: "source-b", title: "错题整理", kind: "tutoring_note", status: "active" },
  ],
};

describe("DeskWorkFolder", () => {
  it("requires explicit sources and sends only the checked materials", () => {
    const onCreate = vi.fn();
    render(
      <DeskWorkFolder
        courseName="高等数学"
        materials={materials}
        onCreate={onCreate}
        onClose={vi.fn()}
      />,
    );

    const submit = screen.getByRole("button", { name: "带着所选材料问小娜" });
    expect(submit).toBeDisabled();
    fireEvent.click(screen.getByLabelText(/教材第二章/));
    expect(screen.getByLabelText(/教材第二章/)).toBeChecked();
    expect(submit).toBeEnabled();
    fireEvent.click(submit);
    expect(onCreate).toHaveBeenCalledWith(expect.objectContaining({
      selectedSources: [{ id: "source-a", title: "教材第二章", kind: "resource_pack" }],
    }));
  });

  it("shows a truthful result empty state instead of inferred chat files", () => {
    render(
      <DeskWorkFolder
        courseName="高等数学"
        materials={materials}
        onCreate={vi.fn()}
        onClose={vi.fn()}
      />,
    );
    fireEvent.click(screen.getByRole("tab", { name: "成果" }));
    expect(screen.getByText(/没有可靠的课程成果索引/)).toBeInTheDocument();
  });
});
