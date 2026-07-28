// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { beforeEach, describe, expect, it } from "vitest";
import {
  bindStudioHandoff,
  buildStudioChatHandoff,
  buildStudioChatPrompt,
  clearPendingStudioHandoff,
  clearSessionStudioHandoff,
  getStudioChatHandoffFromLocation,
  parseStudioChatHandoff,
  persistPendingStudioHandoff,
  readPendingStudioHandoff,
  readSessionStudioHandoff,
  resolveStudioChatSessionId,
} from "./studioChatHandoff";

const PROJECT = {
  id: "p1",
  title: "极限概念分享",
  brief: "讲给没学过极限的同学",
  sources: [{ title: "教材 §2.3 极限的运算法则" }, { title: "未定式自测" }],
};

beforeEach(() => window.localStorage.clear());

describe("studioChatHandoff", () => {
  it("reuses one deterministic session per project", () => {
    expect(resolveStudioChatSessionId("p1")).toBe(resolveStudioChatSessionId("p1"));
    expect(resolveStudioChatSessionId("p1")).not.toBe(resolveStudioChatSessionId("p2"));
    expect(buildStudioChatHandoff(PROJECT).sessionId).toBe(resolveStudioChatSessionId("p1"));
  });

  it("round-trips through pending storage", () => {
    const handoff = buildStudioChatHandoff(PROJECT);
    persistPendingStudioHandoff(handoff);
    expect(readPendingStudioHandoff()).toEqual(handoff);
    clearPendingStudioHandoff();
    expect(readPendingStudioHandoff()).toBeNull();
  });

  it("binds and releases a session scope", () => {
    const handoff = buildStudioChatHandoff(PROJECT);
    bindStudioHandoff(handoff);
    expect(readSessionStudioHandoff(handoff.sessionId)?.projectId).toBe("p1");
    clearSessionStudioHandoff(handoff.sessionId);
    expect(readSessionStudioHandoff(handoff.sessionId)).toBeNull();
  });

  it("refuses anything that is not an explicit studio handoff (§8.3)", () => {
    // 作用域只能由显式转交建立，绝不从别的形状猜出来。
    expect(parseStudioChatHandoff(null)).toBeNull();
    expect(parseStudioChatHandoff({ version: 1, mode: "study", sessionId: "s", projectId: "p" })).toBeNull();
    expect(parseStudioChatHandoff({ version: 2, mode: "studio", sessionId: "s", projectId: "p" })).toBeNull();
    expect(parseStudioChatHandoff({ version: 1, mode: "studio", sessionId: "", projectId: "p" })).toBeNull();
    expect(getStudioChatHandoffFromLocation({ studyHandoff: { version: 1, mode: "study" } })).toBeNull();
  });

  it("reads a handoff off navigation state", () => {
    const handoff = buildStudioChatHandoff(PROJECT);
    expect(getStudioChatHandoffFromLocation({ studioHandoff: handoff })?.projectId).toBe("p1");
  });

  it("falls back to /studio when a return target is missing", () => {
    const parsed = parseStudioChatHandoff({
      version: 1,
      mode: "studio",
      sessionId: "studio:p1",
      projectId: "p1",
    });
    expect(parsed?.returnTarget).toEqual({ path: "/studio", fallbackPath: "/studio" });
  });

  it("describes the project without writing the student's argument for them", () => {
    const prompt = buildStudioChatPrompt(buildStudioChatHandoff(PROJECT));
    expect(prompt).toContain("极限概念分享");
    expect(prompt).toContain("讲给没学过极限的同学");
    expect(prompt).toContain("教材 §2.3 极限的运算法则");
    // 开场只描述项目，不代学生表达观点。
    expect(prompt).not.toMatch(/请写|帮我写|生成一份|直接给我/);
  });

  it("omits empty brief and sources instead of emitting blank lines", () => {
    const prompt = buildStudioChatPrompt(
      buildStudioChatHandoff({ id: "p2", title: "空项目", brief: "", sources: [] }),
    );
    expect(prompt).toBe("我在做一个项目：空项目");
  });
});
