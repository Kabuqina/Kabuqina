// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

// Renders assistant Markdown (with GFM tables, fenced code, and LaTeX math) to a
// static HTML string for the offline chat export. The PDF/HTML export is printed
// by a headless Chromium with no network and no base URL, so math is emitted as
// native MathML (`output: "mathml"`) — Chromium renders it with a system math
// font and we avoid shipping the ~300KB of KaTeX web fonts. Syntax-highlight
// colors travel inline via HIGHLIGHT_CSS.
//
// Kept separate from chatExport.ts on purpose: that module is plain TS exercised
// by a Node test harness that cannot resolve React/CSS imports, whereas this file
// only runs inside the browser/Tauri bundle.

import { renderToStaticMarkup } from "react-dom/server";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import rehypeHighlight from "rehype-highlight";
import githubCss from "highlight.js/styles/github.css?inline";

/** highlight.js light theme, inlined so exported files highlight code offline. */
export const HIGHLIGHT_CSS: string = githubCss;

/** Render one assistant turn's Markdown source to a self-contained HTML string. */
export function renderChatMarkdownToHtml(text: string): string {
  return renderToStaticMarkup(
    <ReactMarkdown
      remarkPlugins={[remarkGfm, remarkMath]}
      rehypePlugins={[rehypeHighlight, [rehypeKatex, { output: "mathml" }]]}
    >
      {text}
    </ReactMarkdown>,
  );
}
