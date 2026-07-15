// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { I18nProvider } from "../lib/i18n";
import { ArtifactAdvancedPanel } from "./ArtifactAdvancedPanel";
import type { StudyArtifactDetail, StudyRepository } from "./repository";
import { StudyRepositoryProvider } from "./repositoryContext";

function detail(artifactId: string, marker: string): StudyArtifactDetail {
  return { artifactId, kind: "knowledge_base", title: marker, version: 1, status: "active", review: {}, envelope: { payload: { marker } } };
}

describe("ArtifactAdvancedPanel", () => {
  it("resets immediately on artifact change and ignores a stale audit response", async () => {
    const user = userEvent.setup();
    let resolveA!: (value: Array<{ origin: string }>) => void;
    const loadSourceAudit = vi.fn().mockImplementation((_spaceId: string, artifactId: string) => (
      artifactId === "artifact-a"
        ? new Promise((resolve) => { resolveA = resolve; })
        : Promise.resolve(["manual source", { trusted: true, rank: 2, optional: null }])
    ));
    const repository = { loadSourceAudit } as unknown as StudyRepository;
    const tree = (value: StudyArtifactDetail) => <I18nProvider><StudyRepositoryProvider repository={repository}><ArtifactAdvancedPanel spaceId="space-1" detail={value} /></StudyRepositoryProvider></I18nProvider>;
    const view = render(tree(detail("artifact-a", "A RAW")));

    await user.click(screen.getByRole("button", { name: "高级" }));
    await user.click(screen.getByRole("button", { name: "查看原始 JSON" }));
    expect(screen.getByText(/A RAW/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "查看来源审计" }));

    view.rerender(tree(detail("artifact-b", "B RAW")));
    expect(screen.queryByText(/A RAW/)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "查看来源审计" })).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "高级" }));
    await user.click(screen.getByRole("button", { name: "查看来源审计" }));
    expect(await screen.findByText("manual source")).toBeInTheDocument();
    expect(screen.getByText("true")).toBeInTheDocument();
    expect(screen.getByText("null")).toBeInTheDocument();

    await act(async () => resolveA([{ origin: "STALE A" }]));
    expect(screen.queryByText("STALE A")).not.toBeInTheDocument();
    expect(screen.getByText("manual source")).toBeInTheDocument();
  });
});
