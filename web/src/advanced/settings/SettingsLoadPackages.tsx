// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowRight, Package } from "lucide-react";
import { useI18n } from "../../lib/i18n";
import { Section } from "../../components/ui/Section";
import { Button } from "../../components/ui/Button";
import { StatusBanner } from "../../components/ui/StatusBanner";
import { cmdLoadPackages, type LoadPackageStatus } from "../../chat/chat-api";
import { activeLoadPackageDownloads, formatBytes, loadPackageError } from "./loadPackageUi";

export function SettingsLoadPackages() {
  const { t } = useI18n();
  const nav = useNavigate();
  const [packages, setPackages] = useState<LoadPackageStatus[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const next = await cmdLoadPackages();
      setPackages(next.packages);
    } catch (e) {
      setError(loadPackageError(e, t));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const summary = useMemo(() => {
    const installed = packages.filter((pkg) => pkg.downloaded).length;
    const running = activeLoadPackageDownloads(packages).length;
    const totalSize = packages.reduce((sum, pkg) => sum + (pkg.downloaded ? pkg.size : 0), 0);
    return { installed, running, totalSize };
  }, [packages]);

  return (
    <Section icon={Package} title={t("settings.loadPackagesTitle")} desc={t("settings.loadPackagesDesc")}>
      <div className="space-y-3 text-sm text-[var(--kq-color-ink)] dark:text-zinc-300">
        {loading ? (
          <p className="text-[var(--kq-color-muted)] dark:text-zinc-400">{t("settings.loadPackagesChecking")}</p>
        ) : (
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="min-w-0 space-y-1">
              <p className="font-medium text-[var(--kq-color-strong)] dark:text-zinc-100">
                {t("settings.loadPackagesSummary", {
                  installed: String(summary.installed),
                  total: String(packages.length),
                })}
              </p>
              <p className="text-xs text-[var(--kq-color-muted)] dark:text-zinc-400">
                {summary.running > 0
                  ? t("settings.loadPackagesRunning", { count: String(summary.running) })
                  : t("settings.loadPackagesDisk", { size: formatBytes(summary.totalSize) })}
              </p>
            </div>
            <Button onClick={() => nav("/settings/load-packages")}>
              {t("settings.loadPackagesOpen")}
              <ArrowRight className="h-4 w-4" />
            </Button>
          </div>
        )}
        {error ? <StatusBanner variant="error" title={error} /> : null}
      </div>
    </Section>
  );
}
