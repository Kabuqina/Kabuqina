// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import type { LoadPackageStatus } from "../../chat/chat-api";

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}

export function packageTitle(pkg: LoadPackageStatus, t: (path: string) => string): string {
  const key = `settings.loadPackage.${pkg.id}.title`;
  const value = t(key);
  return value === key ? pkg.title : value;
}

export function packageDescription(pkg: LoadPackageStatus, t: (path: string) => string): string {
  const key = `settings.loadPackage.${pkg.id}.desc`;
  const value = t(key);
  return value === key ? pkg.description : value;
}

export function loadPackageError(e: unknown, t: (path: string, vars?: Record<string, string>) => string): string {
  const msg = String(e);
  if (msg.includes("desktop_bridge_unavailable")) {
    return t("settings.loadPackagesDesktopOnly");
  }
  return msg;
}

export function activeLoadPackageDownloads(packages: LoadPackageStatus[]): LoadPackageStatus[] {
  return packages.filter((pkg) => pkg.job?.status === "running");
}
