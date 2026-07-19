// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { BookOpenText, PackageOpen } from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { ResourcePackContent } from "../chat/study/ResourceRenderer";
import {
  cmdStudyArtifactDetail,
  type StudyResourceArtifact,
} from "../chat/study/study-api";
import { AppScaffold } from "../components/AppScaffold";
import { BackButton } from "../components/ui/BackButton";
import { useI18n } from "../lib/i18n";

function sourceLabel(source: string | Record<string, unknown>): string {
  if (typeof source === "string") return source;
  const label = source.source_label ?? source.label ?? source.origin;
  return typeof label === "string" ? label : "";
}

export function ResourceDetailPage() {
  const { locale } = useI18n();
  const nav = useNavigate();
  const { artifactId = "" } = useParams();
  const [artifact, setArtifact] = useState<StudyResourceArtifact | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    if (!artifactId) {
      setError(locale === "en" ? "Invalid resource address." : "资源地址无效。");
      return;
    }
    setArtifact(null);
    setError("");
    void cmdStudyArtifactDetail(artifactId)
      .then((result) => {
        if (!cancelled) setArtifact(result.artifact);
      })
      .catch((reason) => {
        if (!cancelled) setError(reason instanceof Error ? reason.message : String(reason));
      });
    return () => {
      cancelled = true;
    };
  }, [artifactId, locale]);

  const sources = artifact?.source_refs.map(sourceLabel).filter(Boolean) ?? [];

  return (
    <AppScaffold surface="chat" className="flex h-full min-h-0 flex-col">
      <header className="hd-topbar flex h-12 shrink-0 items-center gap-3 border-b px-3">
        <BackButton onClick={() => nav("/chat")} className="-ml-1">
          {locale === "en" ? "Back to study" : "返回学习"}
        </BackButton>
        <BookOpenText className="h-4 w-4 text-[var(--kq-color-primary-dark)]" aria-hidden />
        <span className="truncate text-sm font-semibold text-[var(--kq-color-strong)]">
          {artifact?.title || (locale === "en" ? "Resource detail" : "资源详情")}
        </span>
      </header>

      <main className="min-h-0 flex-1 overflow-y-auto">
        {error ? (
          <div className="mx-auto mt-16 max-w-xl rounded-2xl border border-red-300/60 bg-red-50/80 p-6 text-sm text-red-700 dark:bg-red-500/10 dark:text-red-200">
            {error}
          </div>
        ) : !artifact ? (
          <div className="flex min-h-[50vh] items-center justify-center text-sm text-[var(--kq-color-muted)]">
            {locale === "en" ? "Loading resource…" : "正在加载资源…"}
          </div>
        ) : (
          <div className="mx-auto w-full max-w-6xl px-4 py-9 sm:px-7 sm:py-12 lg:px-10">
            <header className="mb-8 rounded-2xl border border-[var(--kq-glass-border)] bg-[var(--kq-glass-bg-subtle)] px-5 py-6 sm:px-8">
              <div className="flex flex-wrap items-center gap-2 text-xs text-[var(--kq-color-muted)]">
                <PackageOpen className="h-4 w-4 text-[var(--kq-color-primary-dark)]" aria-hidden />
                <span>{locale === "en" ? "Learning resource pack" : "学习资源包"}</span>
                <span
                  className={artifact.status === "active"
                    ? "rounded-full bg-emerald-500/15 px-2 py-0.5 text-emerald-700 dark:text-emerald-300"
                    : "rounded-full bg-amber-500/15 px-2 py-0.5 text-amber-700 dark:text-amber-300"}
                >
                  {artifact.status === "active"
                    ? (locale === "en" ? "Active" : "已激活")
                    : (locale === "en" ? "Pending review" : "待审核")}
                </span>
              </div>
              <h1 className="mt-4 break-words text-3xl font-bold leading-tight tracking-tight text-[var(--kq-color-strong)] sm:text-4xl">
                {artifact.title}
              </h1>
              {sources.length ? (
                <p className="mt-4 text-sm leading-6 text-[var(--kq-color-muted)]">
                  {locale === "en" ? "Sources: " : "来源："}{sources.join(" · ")}
                </p>
              ) : null}
            </header>
            <ResourcePackContent artifact={artifact} />
          </div>
        )}
      </main>
    </AppScaffold>
  );
}
