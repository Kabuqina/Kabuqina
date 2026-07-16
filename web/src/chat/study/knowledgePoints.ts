// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

// STUDY module — the kq-kp knowledge-point protocol (frontend side).
//
// The agent's learning-conduct contract (hermes_core/agent/prompt_builder.py,
// LEARNING_CONDUCT_GUIDANCE) asks the model to append one fenced block tagged
// `kq-kp` at the end of teaching/answer replies, containing a JSON array of
// the knowledge points the reply touched. This module strips those blocks
// from the message body and parses the points so ChatMessage can render them
// as chips that feed the repository-backed spaced-repetition deck.
//
// This parser is dependency-free and treats all input
// as untrusted: any malformed block degrades silently to "no points" and the
// block is still stripped from the rendered prose, never shown as raw JSON.

export const KNOWLEDGE_POINT_MAX = 8;
export const KNOWLEDGE_POINT_NAME_LIMIT = 80;
export const KNOWLEDGE_POINT_GIST_LIMIT = 300;
export const KNOWLEDGE_POINT_SOURCE_LIMIT = 120;

export type KnowledgePointConfidence = "confirmed" | "inferred";

export type KnowledgePoint = {
  name: string;
  gist: string;
  source: string;
  confidence: KnowledgePointConfidence;
};

export type SplitKnowledgePointsResult = {
  /** Message text with every kq-kp fenced block removed. */
  body: string;
  /** Points parsed from the last complete kq-kp block (possibly empty). */
  points: KnowledgePoint[];
};

// Matches a complete fenced block tagged kq-kp. The closing fence must be at
// line start (same shape the model was instructed to emit); an unterminated
// block — e.g. mid-stream — deliberately does not match so streaming text is
// left untouched until the fence closes.
const KQ_KP_BLOCK_RE = /^```kq-kp[ \t]*\r?\n([\s\S]*?)^```[ \t]*(?:\r?\n|$)/gim;

function stripControlChars(value: string): string {
  let out = "";
  for (let i = 0; i < value.length; i += 1) {
    const code = value.charCodeAt(i);
    const isC0 = code <= 0x1f && code !== 0x09 && code !== 0x0a && code !== 0x0d;
    const isC1 = code >= 0x7f && code <= 0x9f;
    if (isC0 || isC1) continue;
    out += value[i];
  }
  return out;
}

function cleanText(value: unknown, limit: number): string {
  if (typeof value !== "string") return "";
  return stripControlChars(value).replace(/\s+/g, " ").trim().slice(0, limit);
}

function normalizePoint(raw: unknown): KnowledgePoint | null {
  if (!raw || typeof raw !== "object") return null;
  const r = raw as Record<string, unknown>;
  const name = cleanText(r.name, KNOWLEDGE_POINT_NAME_LIMIT);
  const gist = cleanText(r.gist, KNOWLEDGE_POINT_GIST_LIMIT);
  if (!name || !gist) return null;
  return {
    name,
    gist,
    source: cleanText(r.source, KNOWLEDGE_POINT_SOURCE_LIMIT),
    confidence: r.confidence === "inferred" ? "inferred" : "confirmed",
  };
}

function parsePoints(payload: string): KnowledgePoint[] {
  let parsed: unknown;
  try {
    parsed = JSON.parse(payload);
  } catch {
    return [];
  }
  if (!Array.isArray(parsed)) return [];
  const out: KnowledgePoint[] = [];
  const seen = new Set<string>();
  for (const raw of parsed) {
    const point = normalizePoint(raw);
    if (!point) continue;
    const key = point.name.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(point);
    if (out.length >= KNOWLEDGE_POINT_MAX) break;
  }
  return out;
}

/**
 * Strip all complete kq-kp blocks from `text` and parse the last one. Safe on
 * streaming text: an unterminated block stays in the body untouched until its
 * closing fence arrives, then disappears into chips on the next pass.
 */
export function splitKnowledgePoints(text: unknown): SplitKnowledgePointsResult {
  if (typeof text !== "string" || !text.includes("```kq-kp")) {
    return { body: typeof text === "string" ? text : "", points: [] };
  }
  let lastPayload = "";
  const body = text
    .replace(KQ_KP_BLOCK_RE, (_match, payload: string) => {
      lastPayload = payload;
      return "";
    })
    .replace(/\n{3,}/g, "\n\n")
    .trimEnd();
  return { body, points: lastPayload ? parsePoints(lastPayload) : [] };
}

/**
 * Map a knowledge point onto the repository capture contract used by
 * "click chip → review deck".
 */
export function knowledgePointToCardInput(point: KnowledgePoint): {
  front: string;
  back: string;
  hint: string;
  tags: string[];
} {
  const tags = ["知识点"];
  if (point.source && point.source.toLowerCase() !== "model") tags.push(point.source);
  return { front: point.name, back: point.gist, hint: "", tags };
}
