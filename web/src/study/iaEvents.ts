// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

export const STUDY_IA_ENABLED_KEY = "kabuqina.telemetry.study-ia.enabled.v1";
export const STUDY_IA_AGGREGATE_KEY = "kabuqina.telemetry.study-ia.aggregate.v1";

export type StudyIaPage = "flyleaf" | "plan" | "learn" | "evaluate" | "practice";
export type StudyIaCountBucket = "zero" | "one" | "two_to_five" | "six_plus";

export type StudyIaEvent =
  | { name: "study.page.view"; page: StudyIaPage; action: "view" }
  | { name: "study.space.switch"; action: "switch"; success: boolean }
  | { name: "study.resume"; page: "plan"; action: "resume" }
  | { name: "study.wrongbook.open"; page: "evaluate"; action: "open"; success: boolean; count_bucket: StudyIaCountBucket }
  | { name: "study.wrongbook.retry"; page: "evaluate"; action: "retry" }
  | { name: "study.review.start"; page: "practice"; action: "start"; count_bucket: StudyIaCountBucket }
  | { name: "study.review.complete"; page: "practice"; action: "complete"; count_bucket: StudyIaCountBucket }
  | { name: "study.draft.reviewed"; action: "reviewed"; success: boolean };

export type StudyIaSink = (event: StudyIaEvent) => void | Promise<void>;
export type StudyIaRecordOptions = { dedupeKey?: string };
export type StudyIaRecorder = (event: StudyIaEvent, options?: StudyIaRecordOptions) => void;

type StudyIaAggregate = {
  version: 1;
  counters: Record<string, number>;
};

const PAGE_VALUES = new Set<StudyIaPage>(["flyleaf", "plan", "learn", "evaluate", "practice"]);
const BUCKET_VALUES = new Set<StudyIaCountBucket>(["zero", "one", "two_to_five", "six_plus"]);

function exactKeys(value: Record<string, unknown>, keys: readonly string[]): boolean {
  const present = Object.keys(value).sort();
  const expected = [...keys].sort();
  return present.length === expected.length && present.every((key, index) => key === expected[index]);
}

function validPage(value: unknown): value is StudyIaPage {
  return typeof value === "string" && PAGE_VALUES.has(value as StudyIaPage);
}

function validBucket(value: unknown): value is StudyIaCountBucket {
  return typeof value === "string" && BUCKET_VALUES.has(value as StudyIaCountBucket);
}

export function serializeStudyIaEvent(candidate: unknown): string | null {
  if (!candidate || typeof candidate !== "object" || Array.isArray(candidate)) return null;
  const event = candidate as Record<string, unknown>;
  switch (event.name) {
    case "study.page.view":
      if (!exactKeys(event, ["name", "page", "action"]) || !validPage(event.page) || event.action !== "view") return null;
      break;
    case "study.space.switch":
      if (!exactKeys(event, ["name", "action", "success"]) || event.action !== "switch" || typeof event.success !== "boolean") return null;
      break;
    case "study.resume":
      if (!exactKeys(event, ["name", "page", "action"]) || event.page !== "plan" || event.action !== "resume") return null;
      break;
    case "study.wrongbook.open":
      if (
        !exactKeys(event, ["name", "page", "action", "success", "count_bucket"])
        || event.page !== "evaluate"
        || event.action !== "open"
        || typeof event.success !== "boolean"
        || !validBucket(event.count_bucket)
      ) return null;
      break;
    case "study.wrongbook.retry":
      if (!exactKeys(event, ["name", "page", "action"]) || event.page !== "evaluate" || event.action !== "retry") return null;
      break;
    case "study.review.start":
    case "study.review.complete":
      if (
        !exactKeys(event, ["name", "page", "action", "count_bucket"])
        || event.page !== "practice"
        || event.action !== (event.name === "study.review.start" ? "start" : "complete")
        || !validBucket(event.count_bucket)
      ) return null;
      break;
    case "study.draft.reviewed":
      if (!exactKeys(event, ["name", "action", "success"]) || event.action !== "reviewed" || typeof event.success !== "boolean") return null;
      break;
    default:
      return null;
  }
  return JSON.stringify(event);
}

export function studyIaCountBucket(count: number): StudyIaCountBucket {
  if (!Number.isFinite(count) || count <= 0) return "zero";
  if (count < 2) return "one";
  if (count < 6) return "two_to_five";
  return "six_plus";
}

function browserStorage(): Storage | null {
  try {
    return typeof window === "undefined" ? null : window.localStorage;
  } catch {
    return null;
  }
}

export function getStudyIaEnabled(storage: Storage | null = browserStorage()): boolean {
  try {
    return storage?.getItem(STUDY_IA_ENABLED_KEY) === "true";
  } catch {
    return false;
  }
}

export function setStudyIaEnabled(enabled: boolean, storage: Storage | null = browserStorage()): void {
  try {
    if (!storage) return;
    if (enabled) storage.setItem(STUDY_IA_ENABLED_KEY, "true");
    else {
      storage.removeItem(STUDY_IA_ENABLED_KEY);
      storage.removeItem(STUDY_IA_AGGREGATE_KEY);
    }
  } catch {
    // Preferences and measurement are always fail-open.
  }
}

function readAggregate(storage: Storage): StudyIaAggregate {
  try {
    const parsed = JSON.parse(storage.getItem(STUDY_IA_AGGREGATE_KEY) ?? "null") as unknown;
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) throw new Error("invalid aggregate");
    const aggregate = parsed as Record<string, unknown>;
    if (aggregate.version !== 1 || !aggregate.counters || typeof aggregate.counters !== "object" || Array.isArray(aggregate.counters)) {
      throw new Error("invalid aggregate");
    }
    const counters: Record<string, number> = {};
    for (const [key, count] of Object.entries(aggregate.counters as Record<string, unknown>)) {
      if (serializeStudyIaEvent(JSON.parse(key)) !== key) continue;
      if (typeof count === "number" && Number.isSafeInteger(count) && count > 0) counters[key] = count;
    }
    return { version: 1, counters };
  } catch {
    return { version: 1, counters: {} };
  }
}

export const localStudyIaSink: StudyIaSink = (event) => {
  const storage = browserStorage();
  if (!storage || !getStudyIaEnabled(storage)) return;
  const serialized = serializeStudyIaEvent(event);
  if (!serialized) return;
  try {
    const aggregate = readAggregate(storage);
    const current = aggregate.counters[serialized] ?? 0;
    aggregate.counters[serialized] = current >= Number.MAX_SAFE_INTEGER ? current : current + 1;
    storage.setItem(STUDY_IA_AGGREGATE_KEY, JSON.stringify(aggregate));
  } catch {
    // Measurement must never interrupt a learning action.
  }
};

export function createStudyIaRecorder(sink: StudyIaSink = localStudyIaSink): StudyIaRecorder {
  const seen = new Set<string>();
  return (event, options) => {
    if (!serializeStudyIaEvent(event)) return;
    const dedupeKey = options?.dedupeKey;
    if (dedupeKey && seen.has(dedupeKey)) return;
    if (dedupeKey) {
      if (seen.size >= 256) seen.delete(seen.values().next().value!);
      seen.add(dedupeKey);
    }
    try {
      void Promise.resolve(sink(event)).catch(() => undefined);
    } catch {
      // A synchronous sink failure is fail-open too.
    }
  };
}
