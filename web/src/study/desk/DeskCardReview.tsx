// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useEffect, useRef, useState } from "react";
import type { StudyFlashcard } from "../../chat/study/study-api";

export type DeskCardGrade = "again" | "hard" | "good" | "easy";

const GRADES: Array<{ grade: DeskCardGrade; key: string; label: string }> = [
  { grade: "again", key: "1", label: "再来" },
  { grade: "hard", key: "2", label: "困难" },
  { grade: "good", key: "3", label: "掌握" },
  { grade: "easy", key: "4", label: "轻松" },
];

export function DeskCardReview({
  card,
  index,
  total,
  pending,
  error,
  onGrade,
  onClose,
}: {
  card: StudyFlashcard;
  index: number;
  total: number;
  pending: boolean;
  error: string | null;
  onGrade: (grade: DeskCardGrade) => void;
  onClose: () => void;
}) {
  const surface = useRef<HTMLElement>(null);
  const [revealed, setRevealed] = useState(false);
  useEffect(() => {
    setRevealed(false);
    const frame = requestAnimationFrame(() => surface.current?.focus());
    return () => cancelAnimationFrame(frame);
  }, [card.item_id]);
  const handleKey = (event: React.KeyboardEvent<HTMLElement>) => {
    if (event.repeat || pending || event.target !== event.currentTarget) return;
    if (event.key === " " && !revealed) {
      event.preventDefault();
      setRevealed(true);
      return;
    }
    const grade = GRADES.find((item) => item.key === event.key)?.grade;
    if (revealed && grade) {
      event.preventDefault();
      onGrade(grade);
    }
  };
  return (
    <main className="kd-panel-layout">
      <article ref={surface} className="kd-panel-card kd-review-card" tabIndex={0} onKeyDown={handleKey} aria-labelledby="kd-review-title">
        <header className="kd-panel-heading">
          <div>
            <p className="kd-page-kicker">卡片复习 · {index + 1} / {total}</p>
            <h1 id="kd-review-title">{card.front}</h1>
          </div>
          <button type="button" onClick={onClose}>结束复习</button>
        </header>
        {revealed ? (
          <>
            <div className="kd-card-answer"><strong>答案</strong><p>{card.back}</p>{card.hint ? <small>{card.hint}</small> : null}</div>
            <div className="kd-grade-row">
              {GRADES.map((item) => (
                <button type="button" key={item.grade} disabled={pending} onClick={() => onGrade(item.grade)}>
                  <kbd>{item.key}</kbd>{item.label}
                </button>
              ))}
            </div>
          </>
        ) : (
          <button type="button" className="kd-primary" onClick={() => setRevealed(true)}>显示答案 <kbd>Space</kbd></button>
        )}
        {pending ? <p role="status">正在保存复习结果…</p> : null}
        {error ? <p role="alert" className="kd-operation-error">{error}</p> : null}
      </article>
    </main>
  );
}
