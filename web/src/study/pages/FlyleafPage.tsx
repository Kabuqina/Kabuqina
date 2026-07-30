// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Coffee, RotateCcw } from "lucide-react";
import type { StudyStudentStatePayload } from "../../chat/study/study-api";
import { useI18n } from "../../lib/i18n";
import { STUDY_LEARNING_EVENT } from "../learningEvent";
import { migrateLegacyStudyContext } from "../legacyStudyContextMigration";
import { RequestCoordinator, type Loadable } from "../loadable";
import type { StudyArtifactDetail, StudyDraftPage, StudyFlyleafSnapshot } from "../repository";
import { useStudyDrafts } from "../DraftContext";
import { useStudyRepository } from "../repositoryContext";

const EDIT_PREFIX = "kabuqina.study.flyleaf-edit.v1";
const NANA_REQUEST_PREFIX = "kabuqina.study.flyleaf-nana-request.v1";
const NANA_SOURCE_PREFIX = "kabuqina.study.flyleaf-nana-source.v1";
const NANA_SUGGESTION_PREFIX = "kabuqina.study.flyleaf-nana-suggestion.v1";
const NANA_REQUEST_TTL_MS = 2 * 60 * 60 * 1000;

type FlyleafForm = {
  goals: string;
  preferences: string;
  constraints: string;
};

type NanaRequest = {
  requestedAt: string;
  requestedAtMs: number;
  existingDraftIds: string[];
  formFingerprint: string;
  canAutoAdopt: boolean;
};

type NanaSource = { artifactId: string; payloadFingerprint: string };
type NanaSuggestion = NanaSource & { form: FlyleafForm };

function formFromPayload(payload?: StudyStudentStatePayload): FlyleafForm {
  return {
    goals: (payload?.goals ?? []).join("；"),
    preferences: Object.values(payload?.preferences ?? {}).join("；"),
    constraints: (payload?.constraints ?? []).join("；"),
  };
}

function lines(value: string): string[] {
  return value.split(/\r?\n|；|;/).map((item) => item.trim()).filter(Boolean).slice(0, 24);
}

function payloadFromForm(form: FlyleafForm, active?: StudyStudentStatePayload): StudyStudentStatePayload {
  const preferences = lines(form.preferences);
  return {
    course: active?.course ?? "",
    goals: lines(form.goals),
    preferences: Object.fromEntries(preferences.map((value, index) => [`preference_${index + 1}`, value])),
    constraints: lines(form.constraints),
    // These legacy fields are intentionally not shown on Flyleaf, but editing
    // the learning contract must not silently erase migrated data.
    progress_notes: active?.progress_notes ?? [],
    current_stage: active?.current_stage ?? "",
    next_adjustment: active?.next_adjustment ?? "",
  };
}

function readEdit(spaceId: string): FlyleafForm | null {
  try {
    const raw = window.localStorage.getItem(`${EDIT_PREFIX}:${spaceId}`);
    if (!raw) return null;
    const value = JSON.parse(raw) as Partial<FlyleafForm>;
    return typeof value.goals === "string" && typeof value.preferences === "string" && typeof value.constraints === "string"
      ? { goals: value.goals.slice(0, 12000), preferences: value.preferences.slice(0, 12000), constraints: value.constraints.slice(0, 12000) }
      : null;
  } catch {
    return null;
  }
}

function writeEdit(spaceId: string, form: FlyleafForm): void {
  try {
    window.localStorage.setItem(`${EDIT_PREFIX}:${spaceId}`, JSON.stringify(form));
  } catch { /* recovery only */ }
}

function clearEdit(spaceId: string): void {
  try { window.localStorage.removeItem(`${EDIT_PREFIX}:${spaceId}`); } catch { /* recovery only */ }
}

function formFingerprint(form: FlyleafForm): string {
  return JSON.stringify(form);
}

function draftPage(state: Loadable<StudyDraftPage>): StudyDraftPage | null {
  if (state.status === "ready") return state.data;
  if (state.status === "loading" || state.status === "error") return state.previous ?? null;
  return null;
}

function detailData(state: Loadable<StudyArtifactDetail> | undefined): StudyArtifactDetail | null {
  if (state?.status === "ready") return state.data;
  if (state?.status === "loading" || state?.status === "error") return state.previous ?? null;
  return null;
}

function storageRead<T>(key: string): T | null {
  try {
    const raw = window.localStorage.getItem(key);
    return raw ? JSON.parse(raw) as T : null;
  } catch {
    return null;
  }
}

function storageWrite(key: string, value: unknown): void {
  try { window.localStorage.setItem(key, JSON.stringify(value)); } catch { /* recovery only */ }
}

function storageRemove(key: string): void {
  try { window.localStorage.removeItem(key); } catch { /* recovery only */ }
}

function readNanaRequest(spaceId: string): NanaRequest | null {
  const key = `${NANA_REQUEST_PREFIX}:${spaceId}`;
  const value = storageRead<Partial<NanaRequest>>(key);
  if (
    !value
    || typeof value.requestedAt !== "string"
    || typeof value.requestedAtMs !== "number"
    || !Array.isArray(value.existingDraftIds)
    || !value.existingDraftIds.every((id) => typeof id === "string")
    || typeof value.formFingerprint !== "string"
    || typeof value.canAutoAdopt !== "boolean"
    || Date.now() - value.requestedAtMs > NANA_REQUEST_TTL_MS
  ) {
    storageRemove(key);
    return null;
  }
  return value as NanaRequest;
}

function readNanaSource(spaceId: string): NanaSource | null {
  const value = storageRead<Partial<NanaSource>>(`${NANA_SOURCE_PREFIX}:${spaceId}`);
  return value && typeof value.artifactId === "string" && typeof value.payloadFingerprint === "string"
    ? value as NanaSource
    : null;
}

function readNanaSuggestion(spaceId: string): NanaSuggestion | null {
  const value = storageRead<Partial<NanaSuggestion>>(`${NANA_SUGGESTION_PREFIX}:${spaceId}`);
  if (!value || typeof value.artifactId !== "string" || typeof value.payloadFingerprint !== "string") return null;
  const form = value.form as Partial<FlyleafForm> | undefined;
  return form && typeof form.goals === "string" && typeof form.preferences === "string" && typeof form.constraints === "string"
    ? value as NanaSuggestion
    : null;
}

export function FlyleafPage({ spaceId }: { spaceId: string }) {
  const { t } = useI18n();
  const repository = useStudyRepository();
  const drafts = useStudyDrafts();
  const pageRegion = useRef<HTMLElement>(null);
  const requests = useRef(new RequestCoordinator());
  const mutations = useRef(new RequestCoordinator());
  const migrationAttempted = useRef("");
  const [snapshot, setSnapshot] = useState<Loadable<StudyFlyleafSnapshot>>({ status: "idle" });
  const [form, setForm] = useState<FlyleafForm>({ goals: "", preferences: "", constraints: "" });
  const [pending, setPending] = useState(false);
  const [nanaSource, setNanaSource] = useState<NanaSource | null>(() => readNanaSource(spaceId));
  const [nanaSuggestion, setNanaSuggestion] = useState<NanaSuggestion | null>(() => readNanaSuggestion(spaceId));

  const data = snapshot.status === "ready"
    ? snapshot.data
    : snapshot.status === "loading" || snapshot.status === "error"
      ? snapshot.previous
      : undefined;
  const activePayload = data?.active?.payload;
  const baseline = useMemo(() => formFromPayload(activePayload), [activePayload]);

  const load = useCallback(() => {
    const request = requests.current.begin();
    setSnapshot((current) => ({ status: "loading", ...(current.status === "ready" ? { previous: current.data } : {}) }));
    void repository.loadFlyleaf(spaceId, request.signal).then(
      (next) => {
        if (!requests.current.isCurrent(request.generation)) return;
        setSnapshot({ status: "ready", data: next });
        const recovered = readEdit(spaceId);
        setForm(recovered ?? formFromPayload(next.active?.payload));
        setNanaSource(readNanaSource(spaceId));
        setNanaSuggestion(readNanaSuggestion(spaceId));
      },
      (error) => {
        if (!requests.current.isCurrent(request.generation)) return;
        setSnapshot((current) => ({ status: "error", error, ...(current.status === "loading" && current.previous ? { previous: current.previous } : {}) }));
      },
    );
  }, [repository, spaceId]);

  const migrateLegacy = useCallback(() => {
    const request = mutations.current.begin();
    void migrateLegacyStudyContext((legacy) => repository.migrateLegacyContext(spaceId, legacy, request.signal)).then(
      (migrated) => {
        if (!mutations.current.isCurrent(request.generation) || !migrated) return;
        load();
        window.dispatchEvent(new Event(STUDY_LEARNING_EVENT));
      },
      () => undefined,
    );
  }, [load, repository, spaceId]);

  useEffect(() => {
    const activeRequests = requests.current;
    const activeMutations = mutations.current;
    pageRegion.current?.focus();
    load();
    if (migrationAttempted.current !== spaceId) {
      migrationAttempted.current = spaceId;
      migrateLegacy();
    }
    return () => { activeRequests.cancel(); activeMutations.cancel(); };
  }, [load, migrateLegacy, spaceId]);

  const draftItems = draftPage(drafts.snapshot)?.items ?? [];
  const requestedNanaDraft = (() => {
    const request = readNanaRequest(spaceId);
    if (!request) return null;
    return [...draftItems]
      .filter((item) => item.kind === "student_state"
        && !request.existingDraftIds.includes(item.artifact_id)
        && Boolean(item.updated_at)
        && String(item.updated_at) >= request.requestedAt)
      .sort((a, b) => `${b.updated_at}:${b.artifact_id}`.localeCompare(`${a.updated_at}:${a.artifact_id}`))[0] ?? null;
  })();

  useEffect(() => {
    if (requestedNanaDraft) drafts.openDetail(requestedNanaDraft.artifact_id);
  }, [drafts, requestedNanaDraft]);

  useEffect(() => {
    if (snapshot.status !== "ready" || !requestedNanaDraft) return;
    const request = readNanaRequest(spaceId);
    const detail = detailData(drafts.details[requestedNanaDraft.artifact_id]);
    if (!request || !detail) return;
    const payload = detail.envelope.payload;
    if (!payload || typeof payload !== "object" || Array.isArray(payload)) return;
    const suggested = formFromPayload(payload as StudyStudentStatePayload);
    const source = { artifactId: requestedNanaDraft.artifact_id, payloadFingerprint: formFingerprint(suggested) };
    if (!request.canAutoAdopt || formFingerprint(form) !== request.formFingerprint) {
      const pendingSuggestion = { ...source, form: suggested };
      setNanaSuggestion(pendingSuggestion);
      storageWrite(`${NANA_SUGGESTION_PREFIX}:${spaceId}`, pendingSuggestion);
      storageRemove(`${NANA_REQUEST_PREFIX}:${spaceId}`);
      return;
    }
    setForm(suggested);
    writeEdit(spaceId, suggested);
    setNanaSource(source);
    setNanaSuggestion(null);
    storageWrite(`${NANA_SOURCE_PREFIX}:${spaceId}`, source);
    storageRemove(`${NANA_SUGGESTION_PREFIX}:${spaceId}`);
    storageRemove(`${NANA_REQUEST_PREFIX}:${spaceId}`);
  }, [drafts.details, form, requestedNanaDraft, snapshot.status, spaceId]);

  const updateField = (field: keyof FlyleafForm, value: string) => {
    setForm((current) => {
      const next = { ...current, [field]: value };
      writeEdit(spaceId, next);
      return next;
    });
  };

  const confirmForm = () => {
    if (pending) return;
    const request = mutations.current.begin();
    setPending(true);
    void (async () => {
      if (nanaSource && formFingerprint(form) === nanaSource.payloadFingerprint) {
        const activated = await drafts.activate(nanaSource.artifactId);
        if (!activated) throw new Error("Nana draft activation failed");
        const active = (await repository.loadFlyleaf(spaceId, request.signal)).active;
        if (!active) throw new Error("Flyleaf activation did not return a state");
        return active;
      }
      const active = await repository.saveFlyleaf(spaceId, payloadFromForm(form, activePayload), request.signal);
      if (nanaSource) void drafts.reject(nanaSource.artifactId);
      if (nanaSuggestion) void drafts.reject(nanaSuggestion.artifactId);
      return active;
    })().then(
      (active) => {
        if (!mutations.current.isCurrent(request.generation)) return;
        clearEdit(spaceId);
        storageRemove(`${NANA_SOURCE_PREFIX}:${spaceId}`);
        storageRemove(`${NANA_SUGGESTION_PREFIX}:${spaceId}`);
        setNanaSource(null);
        setNanaSuggestion(null);
        setSnapshot({ status: "ready", data: { active } });
        setForm(formFromPayload(active.payload));
        setPending(false);
        window.dispatchEvent(new Event(STUDY_LEARNING_EVENT));
      },
      () => {
        if (!mutations.current.isCurrent(request.generation)) return;
        setPending(false);
      },
    );
  };

  const abandon = () => {
    clearEdit(spaceId);
    storageRemove(`${NANA_REQUEST_PREFIX}:${spaceId}`);
    storageRemove(`${NANA_SOURCE_PREFIX}:${spaceId}`);
    storageRemove(`${NANA_SUGGESTION_PREFIX}:${spaceId}`);
    if (nanaSource) void drafts.reject(nanaSource.artifactId);
    if (nanaSuggestion) void drafts.reject(nanaSuggestion.artifactId);
    setNanaSource(null);
    setNanaSuggestion(null);
    setForm(baseline);
  };

  const askNana = () => {
    if (nanaSuggestion) {
      setForm(nanaSuggestion.form);
      writeEdit(spaceId, nanaSuggestion.form);
      const source = { artifactId: nanaSuggestion.artifactId, payloadFingerprint: nanaSuggestion.payloadFingerprint };
      setNanaSource(source);
      storageWrite(`${NANA_SOURCE_PREFIX}:${spaceId}`, source);
      setNanaSuggestion(null);
      storageRemove(`${NANA_SUGGESTION_PREFIX}:${spaceId}`);
      return;
    }
    const requestedAtMs = Date.now();
    storageWrite(`${NANA_REQUEST_PREFIX}:${spaceId}`, {
      requestedAt: new Date(requestedAtMs).toISOString(),
      requestedAtMs,
      existingDraftIds: draftItems.filter((item) => item.kind === "student_state").map((item) => item.artifact_id),
      formFingerprint: formFingerprint(form),
      canAutoAdopt: formFingerprint(form) === formFingerprint(baseline),
    } satisfies NanaRequest);
    document.getElementById("kd-cup-chat")?.click();
  };

  return (
    <section ref={pageRegion} className="kq-study-content-page" aria-label={t("study.pageFlyleaf")} tabIndex={-1}>
      <article className="kq-study-flyleaf-simple">
        <label>
          <span>我的目标</span>
          <input value={form.goals} onChange={(event) => updateField("goals", event.currentTarget.value)} />
        </label>
        <label>
          <span>我的偏好</span>
          <input value={form.preferences} onChange={(event) => updateField("preferences", event.currentTarget.value)} />
        </label>
        <label>
          <span>时间与约束</span>
          <input value={form.constraints} onChange={(event) => updateField("constraints", event.currentTarget.value)} />
        </label>
        <div className="kq-study-inline-actions">
          <button type="button" className="kq-study-primary-link" disabled={pending} onClick={confirmForm}>{pending ? "正在确认…" : "确认并生效"}</button>
          <button type="button" disabled={pending} onClick={abandon}><RotateCcw aria-hidden /> 放弃修改</button>
          <button type="button" className="kq-study-secondary-link" onClick={askNana}><Coffee aria-hidden /> {nanaSuggestion ? "采用小娜建议" : "请小娜帮我拟一版"}</button>
        </div>
      </article>
    </section>
  );
}
