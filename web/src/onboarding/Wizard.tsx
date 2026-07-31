// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useEffect } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import { clearDraft } from "../lib/store";
import { Welcome } from "./steps/Welcome";
import { PickBrain } from "./steps/PickBrain";
import { GetAccessPass } from "./steps/GetAccessPass";
import { SectionPlaceholderStep } from "./steps/SectionPlaceholderStep";
import { ShellFrame } from "./ShellFrame";

function FinishOnboarding() {
  useEffect(() => clearDraft(), []);
  return <Navigate to="/study" replace />;
}

/**
 * Shell setup wizard. First-run setup now follows the Quick Start path directly.
 */
export function Wizard() {
  return (
    <ShellFrame>
      <Routes>
        <Route path="welcome" element={<Welcome />} />
        <Route path="brain" element={<PickBrain />} />
        <Route path="pass" element={<GetAccessPass />} />
        <Route path="tts" element={<SectionPlaceholderStep id="tts" />} />
        <Route path="stt" element={<SectionPlaceholderStep id="stt" />} />
        <Route path="terminal" element={<SectionPlaceholderStep id="terminal" />} />
        <Route path="tools" element={<SectionPlaceholderStep id="tools" />} />
        <Route path="agent" element={<SectionPlaceholderStep id="agent" />} />
        <Route path="done" element={<FinishOnboarding />} />
        <Route path="*" element={<Navigate to="welcome" replace />} />
      </Routes>
    </ShellFrame>
  );
}
