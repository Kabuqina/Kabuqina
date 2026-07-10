import { useState } from "react";
import { Link, Route, Routes } from "react-router-dom";
import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { renderWithRouter } from "./renderWithRouter";

function KeyboardProbe() {
  const [count, setCount] = useState(0);
  return (
    <main>
      <h1>Study test harness</h1>
      <button type="button" onClick={() => setCount((value) => value + 1)}>
        Reviewed {count}
      </button>
      <Link to="/study/space-1/flyleaf">Open study</Link>
    </main>
  );
}

function RouteProbe() {
  return (
    <Routes>
      <Route path="/" element={<KeyboardProbe />} />
      <Route path="/study/:spaceId/:page" element={<h1>Flyleaf route</h1>} />
    </Routes>
  );
}

describe("component test foundation", () => {
  it("drives controls through keyboard-visible user interactions", async () => {
    const { user } = renderWithRouter(<RouteProbe />);

    await user.tab();
    await user.keyboard("{Enter}");

    expect(screen.getByRole("button", { name: "Reviewed 1" })).toHaveFocus();
  });

  it("tests route navigation without a browser process", async () => {
    const { user } = renderWithRouter(<RouteProbe />);

    await user.click(screen.getByRole("link", { name: "Open study" }));

    expect(screen.getByRole("heading", { name: "Flyleaf route" })).toBeVisible();
  });
});
