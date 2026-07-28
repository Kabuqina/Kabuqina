// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { Coffee } from "lucide-react";
import { defaultDeskArtAssets } from "./desk/artAssets";
import { DeskBookend } from "./desk/DeskBookend";
import { DeskCup } from "./desk/DeskCup";
import type { DeskBookstand } from "./desk/types";
import { ScratchNotebook } from "./ScratchNotebook";
import type { StudySpaceSummary } from "./repository";
import "./desk/desk.css";

/**
 * 杂记本摊开时的书桌（design-qa Iteration 10）。
 *
 * 它**不走** `DeskScene`：那张书桌的一切都围着当前练习转（步骤、作答面、检查、
 * 卡片盒），而杂记本一样都没有。硬塞一个 variant 只会让两边都变糊。这里共用的是
 * 书立、纸张与杯子——也就是"同一张桌子"该共用的那些东西。
 *
 * 刻意缺席：五个生命周期分页、笔记本页眉、卡片盒、书堆、任何计数或徽章。
 * 小娜还在——一本不要求你的本子，不等于一本没人陪你的本子。
 */
export function ScratchDesk({
  spaceId,
  spaces,
  switchingSpace,
  onSelectSpace,
  onNewBook,
  onAskNana,
}: {
  spaceId: string;
  spaces: StudySpaceSummary[];
  switchingSpace?: boolean;
  onSelectSpace: (spaceId: string) => void;
  onNewBook: () => void;
  onAskNana: () => void;
}) {
  const courses = spaces.filter((space) => space.kind !== "scratch");
  const scratch = spaces.find((space) => space.kind === "scratch");
  const bookstand: DeskBookstand = {
    title: "我的课程本",
    hint: "换课就是换一本本子。",
    books: courses.map((space) => ({ id: space.id, name: space.title, current: false })),
    newBookLabel: "开新本",
    scratch: scratch ? { id: scratch.id, name: scratch.title, current: scratch.id === spaceId } : null,
  };

  return (
    <div className="kq-desk" data-density="overview" data-scratch="true">
      <div className="kd-canvas">
        <main className="kd-desk">
          <DeskBookend
            art={defaultDeskArtAssets}
            bookstand={bookstand}
            disabled={switchingSpace}
            onSelectSpace={onSelectSpace}
            onNewBook={onNewBook}
            onFutureFeature={() => undefined}
          />
          <section className="kd-center-stage">
            <article className="kd-notebook kd-notebook--scratch">
              <ScratchNotebook spaceId={spaceId} courses={courses} />
            </article>
          </section>
          <aside className="kd-right-objects" aria-label="小娜">
            <DeskCup art={defaultDeskArtAssets} onAskTutor={onAskNana} />
          </aside>
          {/* 杂记本没有卡片，所以窄窗工具条上只剩小娜（Iteration 12）。 */}
          <nav className="kd-narrow-tools" aria-label="窄窗书桌工具">
            <button type="button" onClick={onAskNana}>
              <Coffee aria-hidden /> 小娜
            </button>
          </nav>
        </main>
      </div>
    </div>
  );
}
