// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { ExternalLink, Image as ImageIcon } from "lucide-react";

import { cn } from "../../lib/cn";
import { useI18n } from "../../lib/i18n";
import ChatMarkdown from "../ChatMarkdown";
import type {
  ResourceImage,
  ResourceMindmapNode,
  ResourcePackResource,
  StudyArtifact,
  StudyResourceArtifact,
} from "./study-api";

export type ResourceKind = "mindmap" | "reading" | "video_script" | "doc";

const RESOURCE_KINDS = new Set<ResourceKind>(["mindmap", "reading", "video_script", "doc"]);

export function normalizeResourceKind(value: unknown): ResourceKind {
  return typeof value === "string" && RESOURCE_KINDS.has(value as ResourceKind)
    ? (value as ResourceKind)
    : "doc";
}

export function resourcePackKind(artifact: Pick<StudyArtifact, "payload">): ResourceKind {
  const payload = artifact.payload;
  const explicit = payload?.resource_type;
  if (typeof explicit === "string" && RESOURCE_KINDS.has(explicit as ResourceKind)) {
    return explicit as ResourceKind;
  }
  return normalizeResourceKind(payload?.resources?.[0]?.resource_type);
}

function resourceKind(resource: ResourcePackResource, fallback: ResourceKind): ResourceKind {
  const explicit = resource.resource_type;
  return typeof explicit === "string" && RESOURCE_KINDS.has(explicit as ResourceKind)
    ? (explicit as ResourceKind)
    : fallback;
}

function toNodeArray(outline: ResourcePackResource["outline"]): ResourceMindmapNode[] {
  if (!outline) return [];
  return Array.isArray(outline) ? outline : [outline];
}

function MindmapNodes({ nodes, depth = 0 }: { nodes: ResourceMindmapNode[]; depth?: number }) {
  return (
    <ul
      className={cn(
        "space-y-2",
        depth > 0 && "ml-5 border-l border-[var(--kq-glass-border)] pl-4",
      )}
    >
      {nodes.map((node, index) => {
        const label = node.label || node.title || "";
        const children = Array.isArray(node.children) ? node.children : [];
        return (
          <li key={`${depth}-${index}-${label}`} className="min-w-0">
            <div className="flex items-start gap-2 text-[15px] leading-7 text-[var(--kq-color-ink)]">
              <span
                className={cn(
                  "mt-[11px] h-1.5 w-1.5 shrink-0 rounded-full",
                  depth === 0 ? "bg-[var(--kq-color-primary-dark)]" : "bg-[var(--kq-color-muted)]/60",
                )}
                aria-hidden
              />
              <span className="break-words">{label}</span>
            </div>
            {children.length ? <MindmapNodes nodes={children} depth={depth + 1} /> : null}
          </li>
        );
      })}
    </ul>
  );
}

function mermaidMarkdown(value: string): string {
  const source = value.trim();
  if (!source) return "";
  return source.startsWith("```") ? source : `\`\`\`mermaid\n${source}\n\`\`\``;
}

function imageRecord(value: ResourceImage | string): ResourceImage | null {
  if (typeof value === "string") return value.trim() ? { src: value.trim() } : null;
  if (!value || typeof value !== "object") return null;
  const src = typeof value.src === "string" ? value.src.trim() : "";
  const url = typeof value.url === "string" ? value.url.trim() : "";
  if (!src && !url) return null;
  return { ...value, src: src || url };
}

function ResourceImages({ images }: { images: ResourcePackResource["images"] }) {
  const { locale } = useI18n();
  const rows = (images ?? []).map(imageRecord).filter((image): image is ResourceImage => Boolean(image));
  if (!rows.length) return null;
  return (
    <section className="mt-7" aria-label={locale === "en" ? "Illustrations" : "配图"}>
      <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-[var(--kq-color-strong)]">
        <ImageIcon className="h-4 w-4 text-[var(--kq-color-primary-dark)]" aria-hidden />
        {locale === "en" ? "Illustrations" : "配图"}
      </div>
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        {rows.map((image, index) => (
          <figure key={`${image.src}-${index}`} className="overflow-hidden rounded-xl border border-[var(--kq-glass-border)] bg-white/60 shadow-sm dark:bg-white/[0.03]">
            <img
              src={image.src}
              alt={image.alt || ""}
              loading="lazy"
              className="max-h-[540px] w-full object-contain"
            />
            {image.caption ? (
              <figcaption className="border-t border-[var(--kq-glass-border)] px-4 py-3 text-sm leading-6 text-[var(--kq-color-muted)]">
                {image.caption}
              </figcaption>
            ) : null}
          </figure>
        ))}
      </div>
    </section>
  );
}

function ResourceSection({
  fallbackKind,
  index,
  resource,
}: {
  fallbackKind: ResourceKind;
  index: number;
  resource: ResourcePackResource;
}) {
  const { locale } = useI18n();
  const kind = resourceKind(resource, fallbackKind);
  const content = typeof resource.content_markdown === "string" ? resource.content_markdown.trim() : "";
  const purpose = typeof resource.purpose === "string" ? resource.purpose.trim() : "";
  const nodes = toNodeArray(resource.outline);
  const mermaid = typeof resource.mermaid === "string" ? mermaidMarkdown(resource.mermaid) : "";
  const scenes = Array.isArray(resource.scenes) ? resource.scenes : [];
  const typeLabels: Record<ResourceKind, string> = {
    doc: locale === "en" ? "Guide" : "讲解文档",
    mindmap: locale === "en" ? "Mind map" : "思维导图",
    reading: locale === "en" ? "Reading" : "拓展阅读",
    video_script: locale === "en" ? "Video script" : "视频脚本",
  };
  const metadata = [
    resource.difficulty
      ? `${locale === "en" ? "Difficulty" : "难度"}：${resource.difficulty}`
      : "",
    resource.credibility
      ? `${locale === "en" ? "Credibility" : "可信度"}：${resource.credibility}`
      : "",
    resource.reason
      ? `${locale === "en" ? "Why this resource" : "推荐理由"}：${resource.reason}`
      : "",
  ].filter(Boolean);

  return (
    <article className="rounded-2xl border border-[var(--kq-glass-border)] bg-white/70 px-5 py-6 shadow-[0_16px_50px_rgba(50,38,62,0.06)] dark:bg-white/[0.035] sm:px-8 sm:py-8">
      <header className="mb-6 border-b border-[var(--kq-glass-border)] pb-5">
        <div className="mb-2 flex flex-wrap items-center gap-2">
          <span className="rounded-full bg-[var(--kq-hover-bg)] px-2.5 py-1 text-xs font-medium text-[var(--kq-color-muted)]">
            {typeLabels[kind]}
          </span>
          <span className="text-xs text-[var(--kq-color-muted)]">
            {locale === "en" ? `Resource ${index + 1}` : `资源 ${index + 1}`}
          </span>
        </div>
        <h2 className="break-words text-xl font-semibold leading-tight tracking-tight text-[var(--kq-color-strong)] sm:text-2xl">
          {resource.title || (locale === "en" ? `Resource ${index + 1}` : `资源 ${index + 1}`)}
        </h2>
        {purpose ? (
          <p className="mt-3 max-w-3xl text-[15px] leading-7 text-[var(--kq-color-muted)] sm:text-base">
            {purpose}
          </p>
        ) : null}
        {metadata.length ? (
          <div className="mt-4 flex flex-wrap gap-2">
            {metadata.map((item) => (
              <span key={item} className="rounded-lg border border-[var(--kq-glass-border)] px-2.5 py-1 text-xs leading-5 text-[var(--kq-color-muted)]">
                {item}
              </span>
            ))}
          </div>
        ) : null}
        {resource.url ? (
          <a
            href={resource.url}
            target="_blank"
            rel="noreferrer"
            className="mt-4 inline-flex max-w-full items-center gap-1.5 break-all text-sm text-sky-600 underline decoration-sky-500/30 underline-offset-4 hover:decoration-sky-500 dark:text-sky-400"
          >
            <ExternalLink className="h-3.5 w-3.5 shrink-0" aria-hidden />
            {resource.url}
          </a>
        ) : null}
      </header>

      {content ? <ChatMarkdown text={content} variant="article" /> : null}

      {kind === "mindmap" && mermaid ? <ChatMarkdown text={mermaid} variant="article" /> : null}
      {kind === "mindmap" && nodes.length ? (
        <div className={cn("rounded-xl bg-[var(--kq-hover-bg)] p-4 sm:p-5", mermaid && "mt-6")}>
          <MindmapNodes nodes={nodes} />
        </div>
      ) : null}

      {kind === "video_script" && scenes.length ? (
        <ol className={cn("grid grid-cols-1 gap-4", content && "mt-7")}>
          {scenes.map((scene, sceneIndex) => (
            <li key={sceneIndex} className="rounded-xl border border-[var(--kq-glass-border)] bg-[var(--kq-hover-bg)]/60 p-4 sm:p-5">
              <div className="mb-3 text-sm font-semibold text-[var(--kq-color-strong)]">
                {locale === "en" ? `Scene ${sceneIndex + 1}` : `场景 ${sceneIndex + 1}`}
              </div>
              <div className="grid gap-3 text-[15px] leading-7">
                {scene.narration ? (
                  <div>
                    <span className="mr-2 font-medium text-[var(--kq-color-muted)]">
                      {locale === "en" ? "Narration" : "旁白"}
                    </span>
                    <span className="text-[var(--kq-color-ink)]">{scene.narration}</span>
                  </div>
                ) : null}
                {scene.visual ? (
                  <div>
                    <span className="mr-2 font-medium text-[var(--kq-color-muted)]">
                      {locale === "en" ? "Visual" : "画面"}
                    </span>
                    <span className="text-[var(--kq-color-ink)]">{scene.visual}</span>
                  </div>
                ) : null}
                {scene.caption ? (
                  <div>
                    <span className="mr-2 font-medium text-[var(--kq-color-muted)]">
                      {locale === "en" ? "Caption" : "字幕"}
                    </span>
                    <span className="text-[var(--kq-color-ink)]">{scene.caption}</span>
                  </div>
                ) : null}
              </div>
            </li>
          ))}
        </ol>
      ) : null}

      <ResourceImages images={resource.images} />
    </article>
  );
}

export function ResourcePackContent({ artifact }: { artifact: StudyResourceArtifact }) {
  const { locale } = useI18n();
  const resources = artifact.payload.resources ?? [];
  const fallbackKind = resourcePackKind(artifact);
  if (!resources.length) {
    return (
      <div className="rounded-2xl border border-dashed border-[var(--kq-glass-border)] px-6 py-14 text-center text-sm text-[var(--kq-color-muted)]">
        {locale === "en" ? "This resource pack has no renderable content." : "这个资源包暂时没有可展示的内容。"}
      </div>
    );
  }
  return (
    <div className="grid gap-7">
      {resources.map((resource, index) => (
        <ResourceSection
          key={`${resource.title || "resource"}-${index}`}
          fallbackKind={fallbackKind}
          index={index}
          resource={resource}
        />
      ))}
    </div>
  );
}
