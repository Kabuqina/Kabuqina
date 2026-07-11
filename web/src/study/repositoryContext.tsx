// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { createContext, useContext, type ReactNode } from "react";
import { studyRepository, type StudyRepository } from "./repository";

const StudyRepositoryContext = createContext<StudyRepository>(studyRepository);

export function StudyRepositoryProvider({
  repository,
  children,
}: {
  repository: StudyRepository;
  children: ReactNode;
}) {
  return (
    <StudyRepositoryContext.Provider value={repository}>
      {children}
    </StudyRepositoryContext.Provider>
  );
}

export function useStudyRepository(): StudyRepository {
  return useContext(StudyRepositoryContext);
}
