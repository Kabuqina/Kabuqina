// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useEffect, useState } from "react";
import { BookOpenText, Network } from "lucide-react";
import { useNavigate, useParams } from "react-router-dom";
import { AppScaffold } from "../components/AppScaffold";
import { BackButton } from "../components/ui/BackButton";
import ChatMarkdown from "../chat/ChatMarkdown";
import {
  cmdStudyKnowledgeConcept,
  type KnowledgeConceptDetail,
} from "../chat/study/study-api";
import { useI18n } from "../lib/i18n";

export function KnowledgeConceptPage() {
  const { locale } = useI18n();
  const nav = useNavigate();
  const { artifactId = "", conceptIndex = "" } = useParams();
  const [concept, setConcept] = useState<KnowledgeConceptDetail | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    setConcept(null);
    setError("");
    const index = Number(conceptIndex);
    if (!artifactId || !Number.isInteger(index) || index < 0) {
      setError(locale === "zh" ? "知识点地址无效" : "Invalid concept address");
      return;
    }
    void cmdStudyKnowledgeConcept(artifactId, index)
      .then((result) => {
        if (!cancelled) setConcept(result.concept);
      })
      .catch((reason) => {
        if (!cancelled) setError(reason instanceof Error ? reason.message : String(reason));
      });
    return () => {
      cancelled = true;
    };
  }, [artifactId, conceptIndex, locale]);

  const articleBody = concept && concept.content_markdown.trim() !== concept.explanation.trim()
    ? concept.content_markdown
    : "";

  return (
    <AppScaffold surface="chat" className="flex h-full min-h-0 flex-col">
      <header className="hd-topbar flex h-12 shrink-0 items-center gap-3 border-b px-3">
        <BackButton onClick={() => nav("/study/knowledge-graph")} className="-ml-1">
          {locale === "zh" ? "返回图谱" : "Back to graph"}
        </BackButton>
        <Network className="h-4 w-4 text-[var(--kq-color-primary-dark)]" />
        <span className="truncate text-sm font-semibold text-[var(--kq-color-strong)]">
          {locale === "zh" ? "知识点详情" : "Concept detail"}
        </span>
      </header>
      <div className="min-h-0 flex-1 overflow-y-auto">
        {error ? (
          <div className="mx-auto mt-16 max-w-xl rounded-2xl border border-red-300/60 bg-red-50/80 p-6 text-sm text-red-700 dark:bg-red-500/10 dark:text-red-200">
            {error}
          </div>
        ) : !concept ? (
          <div className="flex min-h-[50vh] items-center justify-center text-sm text-[var(--kq-color-muted)]">
            {locale === "zh" ? "正在加载知识点…" : "Loading concept…"}
          </div>
        ) : (
          <article className="mx-auto w-full max-w-4xl px-5 py-10 sm:px-8 sm:py-14">
            <div className="flex flex-wrap items-center gap-2 text-xs text-[var(--kq-color-muted)]">
              <BookOpenText className="h-4 w-4" />
              {concept.specialty ? <span>{concept.specialty}</span> : null}
              {concept.course ? <span>· {concept.course}</span> : null}
              {concept.module ? <span>· {concept.module}</span> : null}
            </div>
            <h1 className="mt-4 text-3xl font-bold tracking-tight text-[var(--kq-color-strong)] sm:text-4xl">
              {concept.term}
            </h1>
            <p className="mt-4 max-w-3xl text-base leading-7 text-[var(--kq-color-muted)]">
              {concept.explanation}
            </p>

            {concept.prerequisites.length || concept.related.length ? (
              <div className="mt-7 grid gap-4 rounded-2xl border border-[var(--kq-color-border)] bg-[var(--kq-glass-bg-subtle)] p-4 sm:grid-cols-2">
                <div>
                  <h2 className="text-xs font-semibold uppercase tracking-wide text-[var(--kq-color-muted)]">
                    {locale === "zh" ? "前置知识" : "Prerequisites"}
                  </h2>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {concept.prerequisites.length ? concept.prerequisites.map((item) => (
                      <span key={item} className="rounded-full bg-amber-500/12 px-2.5 py-1 text-xs text-amber-700 dark:text-amber-300">
                        {item}
                      </span>
                    )) : <span className="text-xs text-[var(--kq-color-muted)]">—</span>}
                  </div>
                </div>
                <div>
                  <h2 className="text-xs font-semibold uppercase tracking-wide text-[var(--kq-color-muted)]">
                    {locale === "zh" ? "关联知识" : "Related concepts"}
                  </h2>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {concept.related.length ? concept.related.map((item) => (
                      <span key={item} className="rounded-full bg-sky-500/12 px-2.5 py-1 text-xs text-sky-700 dark:text-sky-300">
                        {item}
                      </span>
                    )) : <span className="text-xs text-[var(--kq-color-muted)]">—</span>}
                  </div>
                </div>
              </div>
            ) : null}

            {articleBody ? (
              <div className="mt-10 border-t border-[var(--kq-color-border)] pt-8">
                <ChatMarkdown text={articleBody} variant="article" />
              </div>
            ) : null}
          </article>
        )}
      </div>
    </AppScaffold>
  );
}
