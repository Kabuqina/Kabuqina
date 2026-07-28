// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useEffect, useRef, useState } from "react";
import { useI18n } from "../lib/i18n";
import { RequestCoordinator, type Loadable } from "./loadable";
import type { StudySpaceSummary } from "./repository";
import { useStudyRepository } from "./repositoryContext";
import type { StudyScratchNote, StudyScratchPage } from "../chat/study/study-api";

const SAVE_DEBOUNCE_MS = 600;

/**
 * 杂记本（design-qa Iteration 10 / 12）。
 *
 * **它是留白，不是待办箱。** 一张书桌不能到处都是课程、计划和证据——总得有一本
 * 什么都不要求你。所以这里刻意没有：五个生命周期分页、计划、任何计数或徽章、
 * 「待整理」标签、卡片盒、笔记本页眉。小娜还在。
 *
 * 归本是安静的可选动作：每条一个低强调的「归到某一本」，选中后这条从这里消失，
 * 并在目标课程里**仍是待审核 draft**（不直接激活，不动掌握度）。没有任何东西
 * 催你把这本清空。
 *
 * 明确不做：搜索、标签、排序、批量操作、条数。
 */
export function ScratchNotebook({
  spaceId,
  courses,
}: {
  spaceId: string;
  /** 只有课程本能收归本的条目；杂记本自己不在其中。 */
  courses: StudySpaceSummary[];
}) {
  const { t } = useI18n();
  const repository = useStudyRepository();
  const loadRequests = useRef(new RequestCoordinator());
  const saveTimer = useRef<number | undefined>(undefined);
  const saveController = useRef<AbortController | null>(null);
  const [page, setPage] = useState<Loadable<StudyScratchPage>>({ status: "idle" });
  const [pad, setPad] = useState("");
  const [filingId, setFilingId] = useState<string | null>(null);
  const [notes, setNotes] = useState<StudyScratchNote[]>([]);
  const [padError, setPadError] = useState(false);

  useEffect(() => {
    const coordinator = loadRequests.current;
    const request = coordinator.begin();
    setPage({ status: "loading" });
    void repository.loadScratch(spaceId, request.signal).then(
      (data) => {
        if (!coordinator.isCurrent(request.generation)) return;
        setPage({ status: "ready", data });
        setPad(data.pad);
        setNotes(data.notes);
      },
      (error) => {
        if (!coordinator.isCurrent(request.generation)) return;
        setPage({ status: "error", error });
      },
    );
    return () => coordinator.cancel();
  }, [repository, spaceId]);

  useEffect(() => () => {
    window.clearTimeout(saveTimer.current);
    saveController.current?.abort();
  }, []);

  const changePad = (value: string) => {
    setPad(value);
    setPadError(false);
    window.clearTimeout(saveTimer.current);
    saveTimer.current = window.setTimeout(() => {
      saveController.current?.abort();
      const controller = new AbortController();
      saveController.current = controller;
      void repository.saveScratchPad(spaceId, value, controller.signal).catch(() => {
        if (!controller.signal.aborted) setPadError(true);
      });
    }, SAVE_DEBOUNCE_MS);
  };

  const fileNote = (note: StudyScratchNote, target: StudySpaceSummary) => {
    setFilingId(null);
    // 先从纸上拿走：归本是学生的动作，界面不该在他点完之后还愣一下。
    setNotes((current) => current.filter((item) => item.id !== note.id));
    void repository.fileScratchNote(spaceId, note.id, target.id, new AbortController().signal)
      .catch(() => setNotes((current) => [note, ...current]));
  };

  if (page.status === "loading" || page.status === "idle") {
    return <p className="kq-scratch-status" role="status">{t("scratch.loading")}</p>;
  }
  if (page.status === "error") {
    return <p className="kq-scratch-status" role="alert">{t("scratch.unavailable")}</p>;
  }

  return (
    <section className="kq-scratch-page" aria-label={t("scratch.title")}>
      <textarea
        className="kq-scratch-pad"
        aria-label={t("scratch.padLabel")}
        value={pad}
        onChange={(event) => changePad(event.currentTarget.value)}
        placeholder={t("scratch.padPlaceholder")}
      />
      {padError ? (
        <p className="kq-scratch-status" role="alert">{t("scratch.padSaveFailed")}</p>
      ) : null}

      {notes.map((note) => (
        <article className="kq-scratch-note" key={note.id}>
          <p>{note.text}</p>
          <div className="kq-scratch-note-foot">
            {/* 来源行统一为「来源 · 时间」。 */}
            <span>{note.origin}</span>
            {filingId === note.id ? (
              <span className="kq-scratch-file-choice">
                {courses.map((course) => (
                  <button type="button" key={course.id} onClick={() => fileNote(note, course)}>
                    {course.title}
                  </button>
                ))}
                <button type="button" onClick={() => setFilingId(null)}>
                  {t("scratch.fileCancel")}
                </button>
              </span>
            ) : (
              <button
                className="kq-scratch-file"
                type="button"
                onClick={() => setFilingId(note.id)}
              >
                {t("scratch.file")}
              </button>
            )}
          </div>
        </article>
      ))}
    </section>
  );
}
