// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import type { DeskArtAssets } from "./artAssets";
import type { DeskBookstand } from "./types";

/**
 * 书立（原型 `Bookend`）。课程名长在本子的标签上，**换课＝换一本本子**——
 * 所以它长在笔记本的上边缘，当前那本与纸面连成一体，而不是待在左边一条常驻栏里。
 *
 * 这条替换了 v0.4 的左侧课程栏（`DeskLeftObjects` 的书立那一节）。
 */
export function DeskBookend({
  art,
  bookstand,
  disabled,
  onSelectSpace,
  onNewBook,
  onFutureFeature,
}: {
  art: DeskArtAssets;
  bookstand: DeskBookstand;
  disabled?: boolean;
  onSelectSpace?: (spaceId: string) => void;
  onNewBook?: () => void;
  onFutureFeature: () => void;
}) {
  const Plus = art.plus;
  return (
    <nav className="kd-bookend" aria-label={bookstand.title}>
      {bookstand.books.map((book) => (
        <button
          className="kd-book-pill"
          key={book.id}
          type="button"
          aria-current={book.current ? "page" : undefined}
          aria-disabled={book.current || undefined}
          disabled={disabled && !book.current}
          onClick={() => {
            if (book.current) return;
            if (onSelectSpace) onSelectSpace(book.id);
            else onFutureFeature();
          }}
        >
          <span className="kd-book-pill-spine" aria-hidden="true" />
          {book.name}
        </button>
      ))}
      <button
        className="kd-book-pill kd-book-pill--new"
        type="button"
        onClick={onNewBook ?? onFutureFeature}
      >
        <Plus />
        {bookstand.newBookLabel}
      </button>
      {/* 杂记本被推到最右端（margin-left: auto）：它不是课程，不站在课程那一排里。 */}
      {bookstand.scratch ? (
        <button
          className="kd-book-pill kd-book-pill--scratch"
          type="button"
          aria-current={bookstand.scratch.current ? "page" : undefined}
          aria-disabled={bookstand.scratch.current || undefined}
          disabled={disabled && !bookstand.scratch.current}
          onClick={() => {
            if (bookstand.scratch?.current) return;
            if (onSelectSpace && bookstand.scratch) onSelectSpace(bookstand.scratch.id);
            else onFutureFeature();
          }}
        >
          <span className="kd-book-pill-spine" aria-hidden="true" />
          {bookstand.scratch.name}
        </button>
      ) : null}
    </nav>
  );
}
