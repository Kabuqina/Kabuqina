// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it } from "vitest";
import { DerivationPracticeSurface } from "./DerivationPracticeSurface";

function SurfaceHarness() {
  const [value, setValue] = useState({});
  return <DerivationPracticeSurface
    check="numeric-equivalence"
    steps={[{ expr: "x + 1", justification: "given" }, { cloze: true }]}
    targetSteps={[{ expr: "x + 1" }, { expr: "x^2 + 2x + 1", justification: "expand" }]}
    value={value}
    onChange={setValue}
  />;
}

describe("DerivationPracticeSurface", () => {
  it("keeps the derivation in semantic DOM and submits cloze expression, machine expression and reason", async () => {
    const user = userEvent.setup();
    render(<SurfaceHarness />);

    expect(document.querySelectorAll("ol > li")).toHaveLength(2);
    expect(screen.getByText("given")).toBeInTheDocument();
    await user.type(screen.getByLabelText("Derivation step 2"), "(x+1)^2");
    await user.type(screen.getByLabelText("Machine expression 2"), "(x+1)**2");
    await user.type(screen.getByLabelText("Justification 2"), "expand");

    expect(screen.getByLabelText("Derivation step 2")).toHaveValue("(x+1)^2");
    expect(screen.getByLabelText("Machine expression 2")).toHaveValue("(x+1)**2");
    expect(screen.getByLabelText("Justification 2")).toHaveValue("expand");
  });
});
