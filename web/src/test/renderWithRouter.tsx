import type { ReactElement } from "react";
import { MemoryRouter } from "react-router-dom";
import { render, type RenderResult } from "@testing-library/react";
import userEvent, { type UserEvent } from "@testing-library/user-event";

type RenderWithRouterOptions = {
  initialEntries?: string[];
};

type RenderWithRouterResult = RenderResult & {
  user: UserEvent;
};

export function renderWithRouter(
  ui: ReactElement,
  { initialEntries = ["/"] }: RenderWithRouterOptions = {},
): RenderWithRouterResult {
  const user = userEvent.setup();
  return {
    user,
    ...render(<MemoryRouter initialEntries={initialEntries}>{ui}</MemoryRouter>),
  };
}
