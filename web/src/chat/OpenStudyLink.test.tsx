// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, useLocation } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { I18nProvider } from "../lib/i18n";
import { OpenStudyLink } from "./OpenStudyLink";

function Location() { return <output data-testid="location">{useLocation().pathname}</output>; }

describe("OpenStudyLink", () => {
  it("is an accessible keyboard link to the first-class study route", async () => {
    const user = userEvent.setup();
    render(
      <I18nProvider>
        <MemoryRouter initialEntries={["/chat"]}>
          <OpenStudyLink />
          <Location />
        </MemoryRouter>
      </I18nProvider>,
    );
    const link = screen.getByRole("link", { name: "打开当前学习空间" });
    expect(link).toHaveAttribute("href", "/study");
    link.focus();
    await user.keyboard("{Enter}");
    expect(screen.getByTestId("location")).toHaveTextContent("/study");
  });
});
