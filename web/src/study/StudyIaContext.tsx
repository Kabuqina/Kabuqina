// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { createContext, useContext, useMemo, type ReactNode } from "react";
import { createStudyIaRecorder, localStudyIaSink, type StudyIaRecorder, type StudyIaSink } from "./iaEvents";

const defaultRecorder = createStudyIaRecorder();
const StudyIaContext = createContext<StudyIaRecorder>(defaultRecorder);

export function StudyIaProvider({ children, sink = localStudyIaSink }: { children: ReactNode; sink?: StudyIaSink }) {
  const recorder = useMemo(() => createStudyIaRecorder(sink), [sink]);
  return <StudyIaContext.Provider value={recorder}>{children}</StudyIaContext.Provider>;
}

export function useStudyIa(): StudyIaRecorder {
  return useContext(StudyIaContext);
}
