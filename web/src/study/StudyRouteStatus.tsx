// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import type { ReactNode } from "react";

export function StudyRouteStatus({ children, alert = false }: { children: ReactNode; alert?: boolean }) {
  return <main className="kq-study-route-status" role={alert ? "alert" : undefined}>{children}</main>;
}
