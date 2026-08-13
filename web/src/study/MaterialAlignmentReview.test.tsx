// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { I18nProvider } from "../lib/i18n";
import { MaterialAlignmentReview } from "./MaterialAlignmentReview";

/** 形状严格照 hermes_core/learning/material_alignment_contract.py。 */
const PAYLOAD = {
  schema_version: 1,
  batch_id: "batch-1",
  materials: [
    {
      material_id: "m-textbook",
      title: "高等数学教材.pdf",
      source_ref: "import:1",
      structure: [
        { section_id: "s-2-3", title: "2.3 极限的运算法则", locator: "p.23" },
        { section_id: "s-2-4", title: "2.4 无穷小与无穷大", locator: "p.27" },
      ],
    },
    { material_id: "m-workbook", title: "习题集.pdf", source_ref: "import:2", structure: [] },
    { material_id: "m-stray", title: "线性代数笔记.pdf", source_ref: "import:3", structure: [] },
  ],
  course_groups: [
    {
      group_id: "g1",
      proposed_title: "高等数学",
      rationale: "两份材料都在讲极限与连续性。",
      material_ids: ["m-textbook", "m-workbook"],
      skeleton: {
        material_id: "m-textbook",
        reason: "它有 12 章目录，另一份都能挂上去。",
        role: "explanation",
        role_reason: "以讲解为主。",
      },
      attachments: [
        {
          material_id: "m-workbook",
          role: "practice",
          role_reason: "整本都是题。",
          mappings: [
            { source_locator: "p.41", target_section_id: "s-2-3", reason: "都在练未定式。" },
            { source_locator: "p.45", target_section_id: "s-2-4", reason: "无穷小比较。" },
            { source_locator: "p.47", target_section_id: "s-2-4", reason: "同上。" },
            { source_locator: "p.49", target_section_id: "s-2-3", reason: "约去公因子。" },
          ],
          unaligned: [{ source_locator: "p.60-p.72", reason: "这部分讲导数，教材这一章没有。" }],
        },
      ],
    },
  ],
  ungrouped: [{ material_id: "m-stray", reason: "看起来是另一门课的笔记。" }],
};

function renderReview(envelope: unknown = { payload: PAYLOAD }) {
  const onConfirm = vi.fn();
  const onReject = vi.fn();
  render(
    <I18nProvider>
      <MaterialAlignmentReview
        envelope={envelope}
        onConfirm={onConfirm}
        onReject={onReject}
        busy={false}
      />
    </I18nProvider>,
  );
  return { onConfirm, onReject };
}

describe("MaterialAlignmentReview", () => {
  it("names the skeleton and gives Nana's reason for nominating it", () => {
    renderReview();
    expect(screen.getByText("高等数学")).toBeInTheDocument();
    expect(screen.getByText("高等数学教材.pdf")).toBeInTheDocument();
    expect(screen.getByText(/它有 12 章目录/)).toBeInTheDocument();
  });

  it("renders each correspondence as a checkable claim, not a bare id", () => {
    renderReview();
    // 「来源 → 骨架某节」必须还原成学生看得懂的节标题。
    expect(screen.getByText(/p\.41 → 2\.3 极限的运算法则/)).toBeInTheDocument();
    expect(screen.getByText("都在练未定式。")).toBeInTheDocument();
    expect(screen.queryByText(/s-2-3/)).not.toBeInTheDocument();
  });

  it("shows what could not be matched instead of hiding it", () => {
    renderReview();
    expect(screen.getByText("p.60-p.72")).toBeInTheDocument();
    expect(screen.getByText(/这部分讲导数/)).toBeInTheDocument();
  });

  it("shows materials that could not be placed in any course", () => {
    renderReview();
    expect(screen.getByText("线性代数笔记.pdf")).toBeInTheDocument();
    expect(screen.getByText(/另一门课的笔记/)).toBeInTheDocument();
  });

  it("never shows a coverage number (§2.1.2 红线 4)", () => {
    renderReview();
    expect(screen.queryByText(/%|覆盖|已对齐/)).not.toBeInTheDocument();
  });

  it("keeps long mapping lists collapsed but reachable", async () => {
    const user = userEvent.setup();
    renderReview();
    expect(screen.queryByText(/p\.49 →/)).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /还有 1 条对应/ }));
    expect(screen.getByText(/p\.49 →/)).toBeInTheDocument();
  });

  it("does nothing until the student confirms", async () => {
    const user = userEvent.setup();
    const { onConfirm, onReject } = renderReview();
    expect(onConfirm).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "就按这个来" }));
    expect(onConfirm).toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "不对，重来" }));
    expect(onReject).toHaveBeenCalled();
  });

  it("hides its own action row when the host supplies the buttons", () => {
    // 草稿箱已有确认/拒绝按钮；这里再渲染一套会出现两组同义按钮。
    render(
      <I18nProvider>
        <MaterialAlignmentReview envelope={{ payload: PAYLOAD }} />
      </I18nProvider>,
    );
    expect(screen.queryByRole("button", { name: "就按这个来" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "不对，重来" })).not.toBeInTheDocument();
    // 但"确认的是什么"这句话仍然要在。
    expect(screen.getByText(/确认的是这批分本与对应关系本身/)).toBeInTheDocument();
  });

  it("says so rather than rendering half a proposal", () => {
    renderReview({ payload: { schema_version: 1, materials: [], course_groups: [] } });
    expect(screen.getByRole("alert")).toHaveTextContent("读不出这份对齐提案");
  });
});
