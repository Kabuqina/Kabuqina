// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import React, { useCallback, useEffect, useId, useState } from "react";
import { AlertTriangle, Check, Copy, FileText, Info, Lightbulb } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeHighlight from "rehype-highlight";
import rehypeKatex from "rehype-katex";
import "katex/dist/katex.min.css";
import { cn } from "../lib/cn";
import { useI18n } from "../lib/i18n";
import { useResolvedTheme } from "../lib/useResolvedTheme";

const HLJS_STYLE_ID = "hljs-theme";

const READ_CALLOUTS = {
  "[!SOURCE]": {
    label: "Source",
    Icon: FileText,
    className: "border-sky-200 bg-sky-50/80 text-sky-900 dark:border-sky-500/30 dark:bg-sky-500/10 dark:text-sky-100",
    iconClassName: "text-sky-600 dark:text-sky-300",
  },
  "[!WARNING]": {
    label: "Warning",
    Icon: AlertTriangle,
    className:
      "border-amber-200 bg-amber-50/90 text-amber-950 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-100",
    iconClassName: "text-amber-600 dark:text-amber-300",
  },
  "[!NOTE]": {
    label: "Note",
    Icon: Info,
    className: "border-zinc-200 bg-zinc-50/90 text-zinc-800 dark:border-[var(--kq-color-border)] dark:bg-[var(--kq-glass-bg-subtle)] dark:text-[var(--kq-color-strong)]",
    iconClassName: "text-zinc-500 dark:text-[var(--kq-color-ink)]",
  },
  "[!TIP]": {
    label: "Tip",
    Icon: Lightbulb,
    className:
      "border-emerald-200 bg-emerald-50/80 text-emerald-950 dark:border-emerald-500/30 dark:bg-emerald-500/10 dark:text-emerald-100",
    iconClassName: "text-emerald-600 dark:text-emerald-300",
  },
} as const;

type ReadCalloutMarker = keyof typeof READ_CALLOUTS;

type Props = {
  text: string;
  className?: string;
};

type HastNode = {
  type?: string;
  tagName?: string;
  value?: string;
  properties?: Record<string, unknown>;
  children?: HastNode[];
};

type MathCopyOptions = {
  copyLabel: string;
};

function isHastElement(node: HastNode | undefined): node is HastNode & { properties: Record<string, unknown> } {
  return node?.type === "element";
}

function hastClassList(node: HastNode): string[] {
  const value = node.properties?.className;
  if (Array.isArray(value)) return value.map(String);
  if (typeof value === "string") return value.split(/\s+/).filter(Boolean);
  return [];
}

function hastText(node: HastNode | undefined): string {
  if (!node) return "";
  if (node.type === "text") return String(node.value ?? "");
  return (node.children ?? []).map(hastText).join("");
}

function findMathTex(node: HastNode | undefined): string {
  if (!node) return "";
  if (
    isHastElement(node) &&
    node.tagName === "annotation" &&
    String(node.properties.encoding ?? "") === "application/x-tex"
  ) {
    return hastText(node).trim();
  }
  for (const child of node.children ?? []) {
    const tex = findMathTex(child);
    if (tex) return tex;
  }
  return "";
}

function rehypeMathCopy(options: MathCopyOptions) {
  return (tree: HastNode) => {
    const visit = (node: HastNode) => {
      const children = node.children;
      if (!Array.isArray(children)) return;
      for (let index = 0; index < children.length; index += 1) {
        const child = children[index];
        visit(child);
        if (!isHastElement(child)) continue;
        if (!hastClassList(child).includes("katex-display")) continue;
        const tex = findMathTex(child);
        if (!tex) continue;
        children[index] = {
          type: "element",
          tagName: "div",
          properties: { className: ["kq-math-copy-card"] },
          children: [
            {
              type: "element",
              tagName: "div",
              properties: { className: ["kq-math-copy-toolbar"] },
              children: [
                {
                  type: "element",
                  tagName: "button",
                  properties: {
                    type: "button",
                    className: ["kq-math-copy-button"],
                    "aria-label": options.copyLabel,
                    title: options.copyLabel,
                    "data-kq-copy-tex": tex,
                  },
                  children: [{ type: "text", value: options.copyLabel }],
                },
              ],
            },
            child,
          ],
        };
      }
    };
    visit(tree);
  };
}

function reactNodeText(node: React.ReactNode): string {
  if (node == null || typeof node === "boolean") return "";
  if (typeof node === "string" || typeof node === "number") return String(node);
  if (Array.isArray(node)) return node.map(reactNodeText).join("");
  if (React.isValidElement<{ children?: React.ReactNode }>(node)) {
    return reactNodeText(node.props.children);
  }
  return "";
}

async function copyToClipboard(text: string): Promise<void> {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text);
    return;
  }

  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.setAttribute("readonly", "");
  textarea.style.position = "fixed";
  textarea.style.left = "-9999px";
  document.body.appendChild(textarea);
  textarea.select();
  document.execCommand("copy");
  textarea.remove();
}

function CodeBlock({
  children,
  code,
  isDark,
  lang,
}: {
  children: React.ReactNode;
  code: string;
  isDark: boolean;
  lang: string;
}) {
  const { t } = useI18n();
  const [done, setDone] = useState(false);
  const canCopy = code.trim().length > 0;

  const onCopy = useCallback(() => {
    if (!canCopy) return;
    void copyToClipboard(code.replace(/\n$/, "")).then(() => {
      setDone(true);
      window.setTimeout(() => setDone(false), 1600);
    });
  }, [canCopy, code]);

  return (
    <div
      className={cn(
        "my-3 overflow-hidden rounded-xl border shadow-sm",
        isDark ? "border-[var(--kq-glass-border)]" : "border-zinc-200/80"
      )}
      style={{ background: isDark ? "var(--kq-glass-bg)" : "rgba(255,255,255,0.5)" }}
    >
      <div
        className="flex items-center justify-between gap-3 px-3 py-1.5 text-[11px] font-mono uppercase tracking-wide"
        style={{
          background: isDark ? "var(--kq-glass-bg-subtle)" : "rgba(245,240,247,0.7)",
          color: isDark ? "var(--kq-color-muted)" : "rgba(90,74,106,0.7)",
          borderBottom: isDark ? "1px solid var(--kq-glass-border)" : "1px solid rgba(232,224,237,0.5)",
        }}
      >
        <span className="min-w-0 truncate">{lang || "code"}</span>
        <button
          type="button"
          disabled={!canCopy}
          onClick={onCopy}
          aria-label={done ? t("chat.copied") : t("chat.copy")}
          title={done ? t("chat.copied") : t("chat.copy")}
          className={cn(
            "inline-flex h-6 shrink-0 items-center gap-1 rounded-md px-2 text-[11px] normal-case transition",
            isDark
              ? "text-[var(--kq-color-muted)] hover:bg-white/10 hover:text-[var(--kq-color-strong)]"
              : "text-zinc-500 hover:bg-white/80 hover:text-zinc-800",
            !canCopy && "cursor-not-allowed opacity-50"
          )}
        >
          {done ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
          <span>{done ? t("chat.copied") : t("chat.copy")}</span>
        </button>
      </div>
      <pre
        className={cn(
          "overflow-x-auto p-4 font-mono text-xs leading-relaxed",
          isDark
            ? "bg-[var(--kq-color-surface)] text-[var(--kq-color-ink)]"
            : "bg-zinc-50 text-zinc-800"
        )}
      >
        {children}
      </pre>
    </div>
  );
}

function MermaidBlock({ code, isDark }: { code: string; isDark: boolean }) {
  const reactId = useId().replace(/[^a-zA-Z0-9_-]/g, "");
  const [svg, setSvg] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    const source = code.trim();
    if (!source) {
      setSvg("");
      setError("");
      return;
    }
    const render = async () => {
      try {
        const mermaid = (await import("mermaid")).default;
        mermaid.initialize({
          startOnLoad: false,
          securityLevel: "strict",
          theme: isDark ? "dark" : "default",
          fontFamily: "Microsoft YaHei UI, Inter, sans-serif",
        });
        const result = await mermaid.render(`kq-mermaid-${reactId}-${Date.now()}`, source);
        if (cancelled) return;
        setSvg(result.svg);
        setError("");
      } catch (err) {
        if (cancelled) return;
        setSvg("");
        setError(err instanceof Error ? err.message : "Mermaid render failed");
      }
    };
    void render();
    return () => {
      cancelled = true;
    };
  }, [code, isDark, reactId]);

  return (
    <div
      className={cn(
        "my-3 overflow-hidden rounded-xl border px-3 py-3 shadow-sm",
        isDark ? "border-[var(--kq-glass-border)] bg-[var(--kq-glass-bg)]" : "border-zinc-200/80 bg-white/60",
      )}
    >
      {svg ? (
        <div
          className="kq-mermaid-diagram overflow-x-auto [&_svg]:mx-auto [&_svg]:max-w-full"
          dangerouslySetInnerHTML={{ __html: svg }}
        />
      ) : (
        <pre className="overflow-x-auto whitespace-pre-wrap break-words text-xs leading-relaxed text-[var(--kq-color-muted)]">
          {error ? `Mermaid 图解渲染失败：${error}\n\n${code}` : code}
        </pre>
      )}
    </div>
  );
}

function parseMarkdownCallout(children: React.ReactNode): { marker: ReadCalloutMarker; body: string } | null {
  const raw = reactNodeText(children).replace(/\r\n/g, "\n").trim();
  const match = raw.match(/^\[!(SOURCE|WARNING|NOTE|TIP)\]\s*/i);
  if (!match) return null;
  const marker = `[!${match[1].toUpperCase()}]` as ReadCalloutMarker;
  return {
    marker,
    body: raw.slice(match[0].length).trim(),
  };
}

function MarkdownCallout({ children }: { children: React.ReactNode }) {
  const callout = parseMarkdownCallout(children);
  if (!callout) {
    return (
      <blockquote className="border-l-2 border-[var(--kq-color-primary)]/40 pl-3 my-2 text-[var(--kq-color-muted)]">
        {children}
      </blockquote>
    );
  }

  const config = READ_CALLOUTS[callout.marker];
  const Icon = config.Icon;
  return (
    <aside
      className={cn(
        "my-3 rounded-lg border px-3 py-2 shadow-sm",
        config.className
      )}
    >
      <div className="mb-1 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide">
        <Icon className={cn("h-3.5 w-3.5", config.iconClassName)} aria-hidden />
        <span>{config.label}</span>
      </div>
      {callout.body ? (
        <div className="whitespace-pre-wrap break-words text-sm leading-[1.55] [overflow-wrap:anywhere]">
          {callout.body}
        </div>
      ) : null}
    </aside>
  );
}

export default function ChatMarkdown({ text, className = "" }: Props) {
  const { t } = useI18n();
  const isDark = useResolvedTheme() === "dark";

  const handleMarkdownClick = useCallback(
    (event: React.MouseEvent<HTMLDivElement>) => {
      const target = event.target;
      if (!(target instanceof Element)) return;
      const button = target.closest("[data-kq-copy-tex]");
      if (!(button instanceof HTMLButtonElement)) return;
      const tex = button.dataset.kqCopyTex ?? "";
      if (!tex.trim()) return;
      void copyToClipboard(tex).then(() => {
        const previous = button.textContent ?? t("chat.copyLatex");
        button.textContent = t("chat.copiedLatex");
        button.setAttribute("aria-label", t("chat.copiedLatex"));
        button.setAttribute("title", t("chat.copiedLatex"));
        window.setTimeout(() => {
          button.textContent = previous;
          button.setAttribute("aria-label", previous);
          button.setAttribute("title", previous);
        }, 1600);
      });
    },
    [t]
  );

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      const css = isDark
        ? (await import("highlight.js/styles/github-dark.css?inline")).default
        : (await import("highlight.js/styles/github.css?inline")).default;
      if (cancelled) return;
      let style = document.getElementById(HLJS_STYLE_ID) as HTMLStyleElement | null;
      if (!style) {
        style = document.createElement("style");
        style.id = HLJS_STYLE_ID;
        document.head.appendChild(style);
      }
      style.textContent = css;
    };
    load();
    return () => {
      cancelled = true;
    };
  }, [isDark]);

  return (
    <div
      className={`chat-md min-w-0 max-w-full text-sm leading-[1.6] text-[var(--kq-color-ink)] [overflow-wrap:anywhere] ${className}`}
      onClick={handleMarkdownClick}
    >
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={[
          rehypeHighlight,
          rehypeKatex,
          [rehypeMathCopy, { copyLabel: t("chat.copyLatex") }],
        ]}
        components={{
          a: ({ href, children }) => (
            <a
              href={href}
              target="_blank"
              rel="noreferrer"
              className="text-sky-600 dark:text-sky-400 underline underline-offset-2"
            >
              {children}
            </a>
          ),
          p: ({ children }) => (
            <p className="mb-2 last:mb-0 whitespace-pre-wrap break-words [overflow-wrap:anywhere]">
              {children}
            </p>
          ),
          ul: ({ children }) => (
            <ul className="list-disc pl-4 mb-2 space-y-1">{children}</ul>
          ),
          ol: ({ children }) => (
            <ol className="list-decimal pl-4 mb-2 space-y-1">{children}</ol>
          ),
          h1: ({ children }) => (
            <h1 className="text-base font-semibold mt-2 mb-1">{children}</h1>
          ),
          h2: ({ children }) => (
            <h2 className="text-sm font-semibold mt-2 mb-1">{children}</h2>
          ),
          h3: ({ children }) => (
            <h3 className="text-sm font-medium mt-2 mb-0.5">{children}</h3>
          ),
          pre: ({ children }) => {
            const codeEl = React.Children.toArray(children).find(
              (c) => React.isValidElement(c) && c.type === "code"
            ) as React.ReactElement<{ className?: string; children?: React.ReactNode }> | undefined;
            const lang = (codeEl?.props?.className ?? "").replace("language-", "");
            const code = reactNodeText(codeEl?.props?.children ?? children);
            if (lang === "mermaid") {
              return <MermaidBlock code={code} isDark={isDark} />;
            }
            return (
              <CodeBlock code={code} isDark={isDark} lang={lang}>
                {children}
              </CodeBlock>
            );
          },
          code: ({ className, children, ...rest }) => {
            const isBlock = (className ?? "").includes("language-");
            if (isBlock) {
              return (
                <code className={className} {...rest}>
                  {children}
                </code>
              );
            }
            return (
              <code className="hd-inline-code" {...rest}>
                {children}
              </code>
            );
          },
          table: ({ children }) => (
            <div className="overflow-x-auto my-3 rounded-xl border border-[var(--kq-glass-border)]">
              <table className="w-full text-left border-collapse text-sm">
                {children}
              </table>
            </div>
          ),
          thead: ({ children }) => (
            <thead className="bg-[var(--kq-hover-bg)]">{children}</thead>
          ),
          tr: ({ children }) => (
            <tr className="border-b border-[var(--kq-glass-border)] last:border-b-0">{children}</tr>
          ),
          th: ({ children }) => (
            <th className="px-3 py-2 font-semibold whitespace-nowrap text-[var(--kq-color-strong)]">{children}</th>
          ),
          td: ({ children }) => (
            <td className="px-3 py-2 whitespace-pre-wrap break-words text-[var(--kq-color-ink)]">{children}</td>
          ),
          blockquote: ({ children }) => <MarkdownCallout>{children}</MarkdownCallout>,
        }}
      >
        {text}
      </ReactMarkdown>
    </div>
  );
}
