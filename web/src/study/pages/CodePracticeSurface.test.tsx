// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { render, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { CodePracticeSurface, transcriptionDiffRange } from "./CodePracticeSurface";

if (typeof Range.prototype.getClientRects !== "function") {
  Object.defineProperty(Range.prototype, "getClientRects", { value: () => [] });
}
if (typeof Range.prototype.getBoundingClientRect !== "function") {
  Object.defineProperty(Range.prototype, "getBoundingClientRect", { value: () => new DOMRect() });
}

describe("transcriptionDiffRange", () => {
  it("marks only the changed learner span and has a 20k bounded linear scan", () => {
    expect(transcriptionDiffRange("print('ok')", "print('no')")).toEqual({ from: 7, to: 9 });
    expect(transcriptionDiffRange("same", "same")).toBeNull();
    expect(transcriptionDiffRange("a".repeat(20_010), "a".repeat(20_000))).toBeNull();
  });
});

describe("CodePracticeSurface", () => {
  it("mounts CodeMirror lazily, updates controlled text and destroys its view", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    const { container, rerender, unmount } = render(
      <CodePracticeSurface targetCode="print('ok')" starter="print('no')" value="print('no')" onChange={onChange} />,
    );
    const editor = await waitFor(() => {
      const current = container.querySelector<HTMLElement>(".cm-content");
      expect(current).not.toBeNull();
      return current!;
    });
    expect(container.querySelector(".kq-study-code-mismatch")).not.toBeNull();

    await user.click(editor);
    await user.keyboard("{End}!");
    expect(onChange).toHaveBeenLastCalledWith("print('no')!");

    rerender(<CodePracticeSurface targetCode="print('ok')" starter="" value="print('ok')" onChange={onChange} />);
    await waitFor(() => expect(container.querySelector(".kq-study-code-mismatch")).toBeNull());
    unmount();
    expect(container.querySelector(".cm-editor")).toBeNull();
  });
});
