// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

export type DeskAttachmentPayload = { name: string; mime: string; data: string };

export const DESK_UI_PERSIST_PREFIX = "__hermesdesk_ui__:";

export type ParsedDeskUserContent = {
  text: string;
  attachments?: DeskAttachmentPayload[];
};

function contentToPlainString(content: unknown): string {
  if (content == null) {
    return "";
  }
  if (typeof content === "string") {
    return content;
  }
  if (Array.isArray(content)) {
    return content
      .map((c) => {
        if (typeof c === "string") {
          return c;
        }
        if (c && typeof c === "object" && "text" in c) {
          return String((c as { text?: unknown }).text ?? "");
        }
        return "";
      })
      .filter(Boolean)
      .join("\n");
  }
  if (typeof content === "object" && "text" in (content as object)) {
    return String((content as { text?: unknown }).text);
  }
  try {
    return JSON.stringify(content);
  } catch {
    return String(content);
  }
}

/** Parse desk UI persist envelope (or legacy ``[N image(s)]`` placeholders) from session DB rows. */
export function parseDeskUserContent(content: unknown): ParsedDeskUserContent {
  if (typeof content === "string" && content.startsWith(DESK_UI_PERSIST_PREFIX)) {
    try {
      const parsed = JSON.parse(content.slice(DESK_UI_PERSIST_PREFIX.length)) as {
        text?: unknown;
        attachments?: unknown;
      };
      const text = typeof parsed.text === "string" ? parsed.text.trim() : "";
      const attachments: DeskAttachmentPayload[] = [];
      if (Array.isArray(parsed.attachments)) {
        for (const item of parsed.attachments) {
          if (!item || typeof item !== "object") {
            continue;
          }
          const rec = item as Record<string, unknown>;
          const name = typeof rec.name === "string" ? rec.name : "image";
          const mime = typeof rec.mime === "string" ? rec.mime : "";
          const data = typeof rec.data === "string" ? rec.data : "";
          if (mime.startsWith("image/") && data) {
            attachments.push({ name, mime, data });
          }
        }
      }
      return { text, attachments: attachments.length ? attachments : undefined };
    } catch {
      // fall through to plain-text handling
    }
  }

  const text = contentToPlainString(content).trim();
  const legacyImageOnly = /^\[(\d+) image\(s\)\]$/.exec(text);
  if (legacyImageOnly) {
    return {
      text: `（${legacyImageOnly[1]} 张图片，历史记录中无法预览）`,
    };
  }
  return { text };
}
