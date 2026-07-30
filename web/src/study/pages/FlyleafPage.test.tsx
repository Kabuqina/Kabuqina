// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { StudyStudentState } from "../../chat/study/study-api";
import { I18nProvider } from "../../lib/i18n";
import { StudyDraftProvider } from "../DraftContext";
import { LEGACY_STUDY_CONTEXT_STORAGE_KEY } from "../legacyStudyContextMigration";
import type { StudyRepository } from "../repository";
import { StudyRepositoryProvider } from "../repositoryContext";
import { FlyleafPage } from "./FlyleafPage";

const emptyDrafts = { items: [], total: 0, kindCounts: {}, returned: 0, limit: 50, offset: 0, truncated: false };
const active: StudyStudentState = {
  artifact_id: "state-1",
  status: "active",
  payload: {
    course: "Physics",
    goals: ["Pass the exam"],
    preferences: { style: "code first" },
    constraints: ["30 minutes"],
    progress_notes: [],
    current_stage: "",
    next_adjustment: "",
  },
};

function repository(overrides: Partial<StudyRepository> = {}): StudyRepository {
  return {
    loadFlyleaf: vi.fn().mockResolvedValue({ active: null }),
    saveFlyleaf: vi.fn(),
    migrateLegacyContext: vi.fn().mockResolvedValue(false),
    listDraftPage: vi.fn().mockResolvedValue(emptyDrafts),
    loadArtifactDetail: vi.fn(),
    setArtifactStatus: vi.fn(),
    ...overrides,
  } as unknown as StudyRepository;
}

function renderPage(repo: StudyRepository) {
  render(
    <I18nProvider><StudyRepositoryProvider repository={repo}><MemoryRouter>
      <StudyDraftProvider spaceId="space-b"><FlyleafPage spaceId="space-b" /></StudyDraftProvider>
    </MemoryRouter></StudyRepositoryProvider></I18nProvider>,
  );
}

afterEach(() => localStorage.clear());

describe("FlyleafPage", () => {
  it("lets the learner edit a recovery draft and explicitly confirm it", async () => {
    const user = userEvent.setup();
    const saved = { ...active, artifact_id: "state-2", payload: { ...active.payload, goals: ["Explain vectors"] } };
    const saveFlyleaf = vi.fn().mockResolvedValue(saved);
    renderPage(repository({ loadFlyleaf: vi.fn().mockResolvedValue({ active }), saveFlyleaf }));

    const goals = screen.getByRole("textbox", { name: "我的目标" });
    await waitFor(() => expect(goals).toHaveValue("Pass the exam"));
    await user.clear(goals);
    await user.type(goals, "Explain vectors");
    expect(localStorage.getItem("kabuqina.study.flyleaf-edit.v1:space-b")).toContain("Explain vectors");
    await user.click(screen.getByRole("button", { name: "确认并生效" }));
    expect(saveFlyleaf).toHaveBeenCalledWith(
      "space-b",
      expect.objectContaining({ goals: ["Explain vectors"] }),
      expect.any(AbortSignal),
    );
    await waitFor(() => expect(goals).toHaveValue("Explain vectors"));
    expect(localStorage.getItem("kabuqina.study.flyleaf-edit.v1:space-b")).toBeNull();
  });

  it("opens an empty course as a directly editable contract", async () => {
    renderPage(repository());
    expect(screen.getByRole("textbox", { name: "我的目标" })).toHaveValue("");
    expect(screen.getByRole("textbox", { name: "我的偏好" })).toHaveValue("");
    expect(screen.getByRole("textbox", { name: "时间与约束" })).toBeEnabled();
    expect(screen.getAllByRole("textbox")).toHaveLength(3);
    expect(screen.getByRole("button", { name: "确认并生效" })).toBeEnabled();
    expect(screen.getAllByRole("button")).toHaveLength(3);
    expect(screen.queryByText("我的学习合同")).not.toBeInTheDocument();
    expect(screen.queryByText("当前课程的学习设定")).not.toBeInTheDocument();
    expect(screen.getByRole("region", { name: "扉页" })).toHaveFocus();
  });

  it("keeps every optional field blank when the learner confirms without writing", async () => {
    const user = userEvent.setup();
    const saveFlyleaf = vi.fn().mockResolvedValue({
      ...active,
      payload: {
        ...active.payload,
        goals: [],
        preferences: {},
        constraints: [],
      },
    });
    renderPage(repository({ saveFlyleaf }));

    await user.click(screen.getByRole("button", { name: "确认并生效" }));

    expect(saveFlyleaf).toHaveBeenCalledWith(
      "space-b",
      expect.objectContaining({ goals: [], preferences: {}, constraints: [] }),
      expect.any(AbortSignal),
    );
    await waitFor(() => {
      expect(screen.getByRole("textbox", { name: "我的目标" })).toHaveValue("");
      expect(screen.getByRole("textbox", { name: "我的偏好" })).toHaveValue("");
      expect(screen.getByRole("textbox", { name: "时间与约束" })).toHaveValue("");
    });
  });

  it("keeps Nana suggestions out of the simplified page", async () => {
    renderPage(repository({
      loadFlyleaf: vi.fn().mockResolvedValue({ active }),
      listDraftPage: vi.fn().mockResolvedValue({
        ...emptyDrafts,
        items: [{ artifact_id: "draft-state", kind: "student_state", title: "Suggestion", status: "draft" }],
        total: 1,
        returned: 1,
        kindCounts: { student_state: 1 },
      }),
      loadArtifactDetail: vi.fn().mockResolvedValue({
        artifactId: "draft-state", kind: "student_state", title: "Suggestion", version: 1,
        status: "draft", review: {}, envelope: { payload: { ...active.payload, goals: ["Draft goal"] } },
      }),
    }));

    expect(screen.queryByText("小娜拟的建议")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "采用后继续编辑" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "请小娜帮我拟一版" })).toBeInTheDocument();
  });

  it("brings an explicitly requested Nana draft back into the same three input lines", async () => {
    const user = userEvent.setup();
    const generatedAt = new Date(Date.now() + 1_000).toISOString();
    const listDraftPage = vi.fn()
      .mockResolvedValueOnce(emptyDrafts)
      .mockResolvedValue({
        ...emptyDrafts,
        items: [{
          artifact_id: "draft-state", kind: "student_state", title: "Suggestion", status: "draft", updated_at: generatedAt,
        }],
        total: 1,
        returned: 1,
        kindCounts: { student_state: 1 },
      });
    const loadArtifactDetail = vi.fn().mockResolvedValue({
      artifactId: "draft-state", kind: "student_state", title: "Suggestion", version: 1,
      status: "draft", review: {}, envelope: { payload: {
        ...active.payload,
        goals: ["理解向量"],
        preferences: { style: "先看图" },
        constraints: ["每晚二十分钟"],
      } },
    });
    const adopted = {
      ...active,
      artifact_id: "draft-state",
      payload: {
        ...active.payload,
        goals: ["理解向量"],
        preferences: { style: "先看图" },
        constraints: ["每晚二十分钟"],
      },
    };
    const loadFlyleaf = vi.fn()
      .mockResolvedValueOnce({ active: null })
      .mockResolvedValue({ active: adopted });
    const setArtifactStatus = vi.fn().mockResolvedValue(undefined);
    const saveFlyleaf = vi.fn();
    renderPage(repository({ listDraftPage, loadArtifactDetail, loadFlyleaf, setArtifactStatus, saveFlyleaf }));

    await waitFor(() => expect(listDraftPage).toHaveBeenCalledTimes(1));
    await user.click(screen.getByRole("button", { name: "请小娜帮我拟一版" }));
    window.dispatchEvent(new Event("study-learning-event"));

    await waitFor(() => expect(screen.getByRole("textbox", { name: "我的目标" })).toHaveValue("理解向量"));
    expect(screen.getByRole("textbox", { name: "我的偏好" })).toHaveValue("先看图");
    expect(screen.getByRole("textbox", { name: "时间与约束" })).toHaveValue("每晚二十分钟");
    expect(screen.getAllByRole("textbox")).toHaveLength(3);
    expect(screen.queryByText("小娜拟的建议")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "确认并生效" }));
    await waitFor(() => expect(setArtifactStatus).toHaveBeenCalledWith(
      "space-b", "draft-state", "active", expect.any(AbortSignal),
    ));
    expect(saveFlyleaf).not.toHaveBeenCalled();
  });

  it("does not silently replace an unconfirmed learner edit with a later Nana draft", async () => {
    const user = userEvent.setup();
    const generatedAt = new Date(Date.now() + 1_000).toISOString();
    const listDraftPage = vi.fn()
      .mockResolvedValueOnce(emptyDrafts)
      .mockResolvedValue({
        ...emptyDrafts,
        items: [{ artifact_id: "draft-state", kind: "student_state", title: "Suggestion", status: "draft", updated_at: generatedAt }],
        total: 1, returned: 1, kindCounts: { student_state: 1 },
      });
    const loadArtifactDetail = vi.fn().mockResolvedValue({
      artifactId: "draft-state", kind: "student_state", title: "Suggestion", version: 1,
      status: "draft", review: {}, envelope: { payload: { ...active.payload, goals: ["小娜的目标"] } },
    });
    renderPage(repository({
      loadFlyleaf: vi.fn().mockResolvedValue({ active }),
      listDraftPage,
      loadArtifactDetail,
    }));

    const goals = screen.getByRole("textbox", { name: "我的目标" });
    await waitFor(() => expect(goals).toHaveValue("Pass the exam"));
    await user.clear(goals);
    await user.type(goals, "我自己正在写的目标");
    await user.click(screen.getByRole("button", { name: "请小娜帮我拟一版" }));
    window.dispatchEvent(new Event("study-learning-event"));

    await waitFor(() => expect(loadArtifactDetail).toHaveBeenCalledWith("space-b", "draft-state", expect.any(AbortSignal)));
    expect(goals).toHaveValue("我自己正在写的目标");

    const adopt = await screen.findByRole("button", { name: "采用小娜建议" });
    await user.click(adopt);
    expect(goals).toHaveValue("小娜的目标");
    expect(screen.getByRole("button", { name: "请小娜帮我拟一版" })).toBeInTheDocument();
  });

  it("saves a learner-edited Nana suggestion as the one canonical active contract", async () => {
    const user = userEvent.setup();
    localStorage.setItem("kabuqina.study.flyleaf-nana-suggestion.v1:space-b", JSON.stringify({
      artifactId: "draft-state",
      payloadFingerprint: JSON.stringify({ goals: "小娜的目标", preferences: "", constraints: "" }),
      form: { goals: "小娜的目标", preferences: "", constraints: "" },
    }));
    const saved = { ...active, artifact_id: "state-2", payload: { ...active.payload, goals: ["共同修改的目标"] } };
    const saveFlyleaf = vi.fn().mockResolvedValue(saved);
    const setArtifactStatus = vi.fn().mockResolvedValue(undefined);
    renderPage(repository({ loadFlyleaf: vi.fn().mockResolvedValue({ active }), saveFlyleaf, setArtifactStatus }));

    await user.click(await screen.findByRole("button", { name: "采用小娜建议" }));
    const goals = screen.getByRole("textbox", { name: "我的目标" });
    expect(goals).toHaveValue("小娜的目标");
    await user.clear(goals);
    await user.type(goals, "共同修改的目标");
    await user.click(screen.getByRole("button", { name: "确认并生效" }));

    await waitFor(() => expect(saveFlyleaf).toHaveBeenCalledWith(
      "space-b",
      expect.objectContaining({ goals: ["共同修改的目标"] }),
      expect.any(AbortSignal),
    ));
    await waitFor(() => expect(setArtifactStatus).toHaveBeenCalledWith(
      "space-b", "draft-state", "rejected", expect.any(AbortSignal),
    ));
    expect(setArtifactStatus).not.toHaveBeenCalledWith(
      "space-b", "draft-state", "active", expect.anything(),
    );
  });

  it("keeps legacy local storage when migration fails", async () => {
    localStorage.setItem(LEGACY_STUDY_CONTEXT_STORAGE_KEY, JSON.stringify({ course: "Legacy calculus" }));
    const migrateLegacyContext = vi.fn().mockRejectedValue(new Error("offline"));
    renderPage(repository({ migrateLegacyContext }));
    await waitFor(() => expect(migrateLegacyContext).toHaveBeenCalled());
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(localStorage.getItem(LEGACY_STUDY_CONTEXT_STORAGE_KEY)).toContain("Legacy calculus");
  });
});
