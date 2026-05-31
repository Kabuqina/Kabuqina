import React, { useEffect } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import { cn } from "../lib/cn";
import { usePrefersDark } from "../lib/usePrefersDark";

type Props = {
  text: string;
  className?: string;
};

export default function ChatMarkdown({ text, className = "" }: Props) {
  const isDark = usePrefersDark();
  useEffect(() => {
    if (isDark) {
      void import("highlight.js/styles/github-dark.css");
    } else {
      void import("highlight.js/styles/github.css");
    }
  }, [isDark]);
  return (
    <div
      className={`chat-md min-w-0 max-w-full text-sm leading-[1.6] text-zinc-800 [overflow-wrap:anywhere] dark:text-zinc-200 ${className}`}
    >
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeHighlight]}
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
            ) as React.ReactElement<{ className?: string }> | undefined;
            const lang = (codeEl?.props?.className ?? "").replace("language-", "");
            return (
              <div className={cn(
                "my-3 rounded-xl overflow-hidden border shadow-sm",
                isDark
                  ? "border-[var(--kq-glass-border)]"
                  : "border-zinc-200/80"
              )}
                style={{ background: isDark ? "var(--kq-glass-bg)" : "rgba(255,255,255,0.5)" }}
              >
                {lang && (
                  <div className="flex items-center justify-between px-3 py-1.5 text-[11px] font-mono uppercase tracking-wide"
                    style={{
                      background: isDark ? "var(--kq-glass-bg-subtle)" : "rgba(245,240,247,0.7)",
                      color: isDark ? "var(--kq-color-muted)" : "rgba(90,74,106,0.7)",
                      borderBottom: isDark ? "1px solid var(--kq-glass-border)" : "1px solid rgba(232,224,237,0.5)",
                    }}
                  >
                    <span>{lang}</span>
                  </div>
                )}
                <pre className={cn(
                  "p-4 overflow-x-auto font-mono text-xs leading-relaxed",
                  isDark
                    ? "bg-[var(--kq-color-surface)] text-[var(--kq-color-ink)]"
                    : "bg-zinc-50 text-zinc-800"
                )}>
                  {children}
                </pre>
              </div>
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
            <div className="overflow-x-auto my-3 rounded-xl border border-zinc-200/80 dark:border-zinc-700/60">
              <table className="w-full text-left border-collapse text-sm">
                {children}
              </table>
            </div>
          ),
          thead: ({ children }) => (
            <thead className="bg-zinc-100/80 dark:bg-zinc-800/60">{children}</thead>
          ),
          tr: ({ children }) => (
            <tr className="border-b border-zinc-200/60 dark:border-zinc-700/40 last:border-b-0">{children}</tr>
          ),
          th: ({ children }) => (
            <th className="px-3 py-2 font-semibold whitespace-nowrap text-zinc-700 dark:text-zinc-200">{children}</th>
          ),
          td: ({ children }) => (
            <td className="px-3 py-2 whitespace-pre-wrap break-words text-zinc-600 dark:text-zinc-300">{children}</td>
          ),
          blockquote: ({ children }) => (
            <blockquote className="border-l-2 border-zinc-300 dark:border-zinc-600 pl-3 my-2 text-zinc-600 dark:text-zinc-400">
              {children}
            </blockquote>
          ),
        }}
      >
        {text}
      </ReactMarkdown>
    </div>
  );
}
