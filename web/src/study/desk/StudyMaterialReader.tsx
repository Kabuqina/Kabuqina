// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { ChevronLeft, ChevronRight, X } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import ChatMarkdown from "../../chat/ChatMarkdown";
import {
  cmdStudyMaterialReader,
  type StudyMaterialReaderNode,
  type StudyMaterialReaderResponse,
} from "../../chat/study/study-api";

const READER_POSITION_PREFIX = "kabuqina.study.material-reader.v1";
const PAGE_WINDOW = 6;

type ReaderCommand = typeof cmdStudyMaterialReader;

function positionKey(spaceId: string, artifactId: string): string {
  return `${READER_POSITION_PREFIX}:${spaceId}:${artifactId}`;
}

function readPosition(spaceId: string, artifactId: string): number {
  if (typeof window === "undefined") return 1;
  try {
    const value = Number(window.localStorage.getItem(positionKey(spaceId, artifactId)) || 1);
    return Number.isInteger(value) && value > 0 ? value : 1;
  } catch {
    return 1;
  }
}

function writePosition(spaceId: string, artifactId: string, page: number): void {
  try {
    window.localStorage.setItem(positionKey(spaceId, artifactId), String(page));
  } catch {
    // Reading position is recovery metadata, never a reason to interrupt reading.
  }
}

export type ReaderPage = { page: number; text: string };

export function parseReaderPages(content: string, fallbackPage: number): ReaderPage[] {
  const marker = /<!--\s*page:(\d+)\s*-->/g;
  const matches = [...content.matchAll(marker)];
  if (!matches.length) return [{ page: fallbackPage, text: content.trim() }];
  return matches.map((match, index) => {
    const start = (match.index ?? 0) + match[0].length;
    const end = matches[index + 1]?.index ?? content.length;
    return { page: Number(match[1]), text: content.slice(start, end).trim() };
  });
}

function ReaderOutline({
  nodes,
  pageStart,
  pageEnd,
  onJump,
  depth = 0,
}: {
  nodes: StudyMaterialReaderNode[];
  pageStart: number;
  pageEnd: number;
  onJump: (page: number) => void;
  depth?: number;
}) {
  return (
    <>
      {nodes.map((node, index) => {
        const key = node.id || `${depth}:${node.title}:${index}`;
        const active = Boolean(node.page && node.page >= pageStart && node.page <= pageEnd);
        return (
          <div className="kq-material-toc-node" key={key} style={{ "--reader-depth": depth } as React.CSSProperties}>
            {node.page ? (
              <button type="button" aria-current={active ? "location" : undefined} onClick={() => onJump(node.page!)}>
                <span>{node.title}</span>
                <small>p.{node.page}</small>
              </button>
            ) : <span className="kq-material-toc-label">{node.title}</span>}
            {node.children?.length ? (
              <ReaderOutline
                nodes={node.children}
                pageStart={pageStart}
                pageEnd={pageEnd}
                onJump={onJump}
                depth={depth + 1}
              />
            ) : null}
          </div>
        );
      })}
    </>
  );
}

export function StudyMaterialReader({
  spaceId,
  artifactId,
  initialPage,
  onClose,
  readMaterial = cmdStudyMaterialReader,
}: {
  spaceId: string;
  artifactId: string;
  initialPage?: number;
  onClose: () => void;
  readMaterial?: ReaderCommand;
}) {
  const [requestedPage, setRequestedPage] = useState(() => initialPage ?? readPosition(spaceId, artifactId));
  const [data, setData] = useState<StudyMaterialReaderResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const bodyRef = useRef<HTMLDivElement>(null);
  const loadGenerationRef = useRef(0);
  const initialRequestedPageRef = useRef(requestedPage);

  const load = useCallback((page: number) => {
    const start = Math.max(1, page);
    setRequestedPage(start);
    setLoading(true);
    setError(false);
    const generation = ++loadGenerationRef.current;
    void readMaterial(spaceId, artifactId, start, start + PAGE_WINDOW - 1)
      .then((next) => {
        if (loadGenerationRef.current !== generation) return;
        setData(next);
        writePosition(spaceId, artifactId, next.pageStart);
        requestAnimationFrame(() => {
          if (typeof bodyRef.current?.scrollTo === "function") {
            bodyRef.current.scrollTo({ top: 0 });
          }
        });
      })
      .catch(() => {
        if (loadGenerationRef.current === generation) setError(true);
      })
      .finally(() => {
        if (loadGenerationRef.current === generation) setLoading(false);
      });
  }, [artifactId, readMaterial, spaceId]);

  useEffect(() => {
    load(initialRequestedPageRef.current);
    return () => { loadGenerationRef.current += 1; };
  }, [load]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const pages = parseReaderPages(data?.content ?? "", data?.pageStart ?? requestedPage);
  const currentStart = data?.pageStart ?? requestedPage;
  const currentEnd = data?.pageEnd ?? currentStart;
  const totalPages = Math.max(1, data?.totalPages ?? currentEnd);

  return (
    <aside className="kq-study-side-panel kq-study-material-reader" aria-label="摊开的材料">
      <header className="kq-study-side-panel__header">
        <div>
          <span className="kq-study-side-panel__eyebrow">
            {data ? `你导入的 · ${data.filename} · 共 ${data.totalPages} 页` : "正在抽出这本资料"}
          </span>
          <h2>{data?.title || "课程材料"}</h2>
        </div>
        <button type="button" className="kq-study-side-panel__close" aria-label="放回去" onClick={onClose}>
          <X aria-hidden />
        </button>
      </header>

      {data?.outline?.length ? (
        <nav className="kq-material-toc" aria-label="这份文件的章节">
          <ReaderOutline
            nodes={data.outline}
            pageStart={currentStart}
            pageEnd={currentEnd}
            onJump={(page) => load(page)}
          />
        </nav>
      ) : null}

      <div className="kq-material-reader-nav" aria-label="阅读页码">
        <button type="button" aria-label="上一组页面" disabled={currentStart <= 1 || loading} onClick={() => load(Math.max(1, currentStart - PAGE_WINDOW))}>
          <ChevronLeft aria-hidden />
        </button>
        <span>第 {currentStart}–{currentEnd} 页 / 共 {totalPages} 页</span>
        <button type="button" aria-label="下一组页面" disabled={currentEnd >= totalPages || loading} onClick={() => load(currentEnd + 1)}>
          <ChevronRight aria-hidden />
        </button>
      </div>

      <div
        ref={bodyRef}
        className="kq-material-reader-body"
        onScroll={(event) => {
          const root = event.currentTarget;
          const threshold = root.getBoundingClientRect().top + 40;
          let visible = currentStart;
          root.querySelectorAll<HTMLElement>("[data-reader-page]").forEach((section) => {
            if (section.getBoundingClientRect().top <= threshold) {
              visible = Number(section.dataset.readerPage || visible);
            }
          });
          writePosition(spaceId, artifactId, visible);
        }}
      >
        {loading && !data ? <p className="kq-study-side-panel__status" role="status">正在翻到第 {requestedPage} 页…</p> : null}
        {error ? (
          <div className="kq-study-side-panel__alert" role="alert">
            <p>这几页暂时没有摊开，原文件没有受到影响。</p>
            <button type="button" onClick={() => load(requestedPage)}>再试一次</button>
          </div>
        ) : null}
        {!error && data && !data.content.trim() ? (
          <p className="kq-study-side-panel__status">这几页没有提取到可读文字，可以从目录换一节再看。</p>
        ) : null}
        {!error ? pages.map((page) => (
          <section key={page.page} className="kq-material-reader-page" data-reader-page={page.page}>
            <span>第 {page.page} 页</span>
            <ChatMarkdown text={page.text || "（本页没有提取到文字）"} className="kq-material-reader-markdown" />
          </section>
        )) : null}
      </div>
    </aside>
  );
}

export default StudyMaterialReader;
