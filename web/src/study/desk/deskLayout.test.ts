// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import fs from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

const deskCss = fs.readFileSync(
  path.join(process.cwd(), "src", "study", "desk", "desk.css"),
  "utf8",
);

describe("Study desk layout contract", () => {
  it("gives the canvas the full surface after the desk header moved into AppShell", () => {
    const rootRules = Array.from(
      deskCss.matchAll(/(?:^|\n)\s*\.kq-desk\s*\{([\s\S]*?)\}/g),
      (match) => match[1],
    );

    expect(rootRules).toHaveLength(2);
    for (const rule of rootRules) {
      expect(rule).toMatch(/grid-template-rows:\s*minmax\(0,\s*1fr\)/);
    }
    expect(deskCss).not.toContain("grid-template-rows: 50px minmax(0, 1fr)");
  });

  it("presents the five page tabs as the visible page titles", () => {
    const tabRule = deskCss.match(/\.kd-page-tabs button\s*\{([\s\S]*?)\}/)?.[1] ?? "";

    expect(tabRule).toMatch(/font-size:\s*clamp\(17px,/);
    expect(tabRule).toMatch(/font-weight:\s*700/);
  });

  it("scrolls overflowing notebook content while keeping the page tabs fixed", () => {
    const pageBodyRule = deskCss.match(/\.kd-page-body\s*\{([\s\S]*?)\}/)?.[1] ?? "";

    expect(pageBodyRule).toMatch(/min-height:\s*0/);
    expect(pageBodyRule).toMatch(/overflow-x:\s*hidden/);
    expect(pageBodyRule).toMatch(/overflow-y:\s*auto/);
    expect(pageBodyRule).toMatch(/overscroll-behavior:\s*contain/);
  });

  it("lets the notebook use the row formerly reserved for the redundant work-folder entry", () => {
    const centerStageRules = Array.from(
      deskCss.matchAll(/(?:^|\n)\s*\.kd-center-stage\s*\{([\s\S]*?)\}/g),
      (match) => match[1],
    );
    const layoutRule = centerStageRules.find((rule) => /display:\s*grid/.test(rule)) ?? "";

    expect(layoutRule).toMatch(/grid-template-rows:\s*minmax\(0,\s*1fr\)/);
    expect(layoutRule).not.toMatch(/38px/);
    expect(deskCss).not.toContain(".kd-work-folder");
  });
});
