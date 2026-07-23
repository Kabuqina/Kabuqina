// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import type { DeskArtAssets } from "./artAssets";
import type { DeskBookstand, DeskMaterials } from "./types";

export interface DeskObjectsProps {
  art: DeskArtAssets;
  bookstand: DeskBookstand;
  materials: DeskMaterials;
  dueCount: number;
  onFutureFeature: () => void;
  onSelectSpace?: (spaceId: string) => void;
  onOpenMaterials?: () => void;
  onReviewCards?: () => void;
  onNewBook?: () => void;
}

export function DeskLeftObjects({
  art,
  bookstand,
  materials,
  onFutureFeature,
  onSelectSpace,
  onOpenMaterials,
  onNewBook,
}: DeskObjectsProps) {
  const Library = art.library;
  const Book = art.book;
  const Plus = art.plus;
  const Layers = art.layers;
  return (
    <aside className="kd-left-objects" aria-label="课程与本课材料">
      <section className="kd-object kd-bookstand">
        <h2><Library /> {bookstand.title}</h2>
        <p>{bookstand.hint}</p>
        <div className="kd-book-row">
          {bookstand.books.map((book) => (
            <button
              key={book.id}
              type="button"
              aria-current={book.current ? "true" : undefined}
              aria-disabled={book.current || undefined}
              onClick={() => {
                if (book.current) return;
                if (onSelectSpace) onSelectSpace(book.id);
                else onFutureFeature();
              }}
            >
              <Book /> {book.name}
            </button>
          ))}
        </div>
        <button type="button" onClick={onNewBook ?? onFutureFeature}>
          <Plus /> {bookstand.newBookLabel}
        </button>
      </section>

      <section className="kd-object kd-materials">
        <h2><Layers /> {materials.title}</h2>
        <p>{materials.hint}</p>
        <div className="kd-material-list">
          {materials.items.map((item) => (
            <button key={item} type="button" onClick={onOpenMaterials ?? onFutureFeature}>{item}</button>
          ))}
        </div>
      </section>
    </aside>
  );
}

export function DeskRightObjects({ art, dueCount, onFutureFeature, onReviewCards }: DeskObjectsProps) {
  const Archive = art.archive;
  return (
    <section className="kd-object kd-card-box">
      <h2><Archive /> 本课卡片盒</h2>
      <div className="kd-due-count">{dueCount}</div>
      <p>张今日到期 · 不打断当前练习</p>
      <button type="button" onClick={onReviewCards ?? onFutureFeature}>到安全节点后复习</button>
    </section>
  );
}
