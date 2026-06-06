// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import type { SetupMode } from "../lib/store";

/**
 * Shell wizard step ids (same order as post-model sections in
 * `hermes/hermes_cli/setup.py` SETUP_SECTIONS: tts, terminal, gateway, tools, agent),
 * with preamble: welcome, brain, pass.
 */
export const SHELL_WIZARD_STEPS = [
  "welcome",
  "brain",
  "pass",
  "gateway",
  "tts",
  "stt",
  "terminal",
  "tools",
  "agent",
] as const;

export type ShellWizardStepId = (typeof SHELL_WIZARD_STEPS)[number];

const QUICK_STEPS: readonly ShellWizardStepId[] = [
  "welcome",
  "brain",
  "pass",
  "gateway",
] as const;

export function getStepsForMode(setupMode: SetupMode | null): readonly ShellWizardStepId[] {
  void setupMode;
  return QUICK_STEPS;
}

export function isStepInMode(step: ShellWizardStepId, setupMode: SetupMode | null): boolean {
  return getStepsForMode(setupMode).includes(step);
}

export function stepToPath(id: ShellWizardStepId): string {
  return `/onboarding/${id}`;
}

/**
 * After saving API credentials on `pass`, continue through the Quick Start gateway section.
 */
export function getNextPathAfterPass(setupMode: SetupMode): string {
  void setupMode;
  return stepToPath("gateway");
}

export function getIndexInFlow(step: ShellWizardStepId, setupMode: SetupMode | null): number {
  const list = getStepsForMode(setupMode);
  const i = list.indexOf(step);
  return i >= 0 ? i : 0;
}

export function getBackPath(current: ShellWizardStepId, setupMode: SetupMode | null): string | null {
  if (current === "welcome") return "/chat";
  const list = getStepsForMode(setupMode);
  const i = list.indexOf(current);
  if (i <= 0) return null;
  return stepToPath(list[i - 1]!);
}

export function getNextPath(
  current: ShellWizardStepId,
  setupMode: SetupMode | null
): string | "complete" {
  const list = getStepsForMode(setupMode);
  const i = list.indexOf(current);
  if (i < 0 || i >= list.length - 1) return "complete";
  return stepToPath(list[i + 1]!);
}

export function isLastStep(current: ShellWizardStepId, setupMode: SetupMode | null): boolean {
  const list = getStepsForMode(setupMode);
  return list.length > 0 && list[list.length - 1] === current;
}

export function slugFromPathname(pathname: string): ShellWizardStepId {
  const seg = (pathname.split("/").pop() || "welcome") as string;
  if ((SHELL_WIZARD_STEPS as readonly string[]).includes(seg)) {
    return seg as ShellWizardStepId;
  }
  return "welcome";
}

/**
 * If URL points at a section Quick Start no longer uses, send user to a valid step.
 */
export function getRedirectForInvalidUrlStep(
  pathStep: ShellWizardStepId,
  setupMode: SetupMode | null
): string | null {
  if (isStepInMode(pathStep, setupMode)) return null;
  if (
    pathStep === "tts" ||
      pathStep === "stt" ||
      pathStep === "terminal" ||
      pathStep === "tools" ||
    pathStep === "agent"
  ) {
    return stepToPath("gateway");
  }
  return null;
}
