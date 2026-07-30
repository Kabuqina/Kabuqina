// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import type { DeskArtAssets } from "./artAssets";
import type { DeskMaterials } from "./types";

/**
 * 书桌右侧（原型 `ReviewCards`）：书堆 + 今天要复习。杯子是独立物件（`DeskCup`）。
 *
 * 书堆的形态是**参考书立着、需要时抽一本**，刻意不是一个可浏览的知识库空间：
 * 一根书脊＝一个文件（你导入的那一份），不是章节。章节是文件里的位置，
 * 打开文件时跳到那儿——所以"整本"始终看得到。
 *
 * v0.4 的左侧课程栏（书立）已经搬到笔记本上边缘，见 `DeskBookend`。
 */
export interface DeskRightObjectsProps {
  art: DeskArtAssets;
  materials: DeskMaterials;
  dueCount: number;
  stackIndexOpen: boolean;
  onToggleStackIndex: () => void;
  onFutureFeature: () => void;
  onOpenMaterials?: (materialId?: string) => void;
  onRemoveMaterial?: (materialId: string, title: string) => void;
  onImportMaterial?: () => void;
  onReviewCards?: () => void;
}

export function DeskRightObjects({
  art,
  materials,
  dueCount,
  stackIndexOpen,
  onToggleStackIndex,
  onFutureFeature,
  onOpenMaterials,
  onRemoveMaterial,
  onImportMaterial,
  onReviewCards,
}: DeskRightObjectsProps) {
  const Archive = art.archive;
  const Layers = art.layers;
  const Plus = art.plus;
  const openMaterial = (id: string) => {
    if (onOpenMaterials) onOpenMaterials(id);
    else onFutureFeature();
  };

  return (
    <>
      <section className="kd-object kd-book-stack">
        <h2>{materials.title}</h2>
        <div className="kd-spines">
          {materials.items.map((item) => (
            <button
              className="kd-book-spine"
              key={item.id}
              type="button"
              title={item.title}
              onClick={() => openMaterial(item.id)}
            >
              {item.title}
            </button>
          ))}
          <button
            className="kd-book-spine kd-book-spine--add"
            type="button"
            aria-label="放一本资料进来"
            title="放一本资料进来"
            onClick={onImportMaterial ?? onFutureFeature}
          >
            <Plus />
          </button>
        </div>
        {materials.unavailable ? (
          <p className="kd-stack-empty" role="status">材料暂时无法读取</p>
        ) : null}
        {/* 贴在书堆上的目录：可翻开核对，不占一个入口。 */}
        {materials.items.length ? (
          <button
            className="kd-stack-index"
            type="button"
            aria-expanded={stackIndexOpen}
            onClick={onToggleStackIndex}
          >
            <Layers />
            小娜从这些书里读到的
          </button>
        ) : null}
        {stackIndexOpen ? (
          <ul className="kd-stack-index-list">
            {materials.items.map((item) => (
              <li key={item.id}>
                <span className="kd-stack-index-title">{item.title}</span>
                <span>{item.status}</span>
                {onRemoveMaterial ? (
                  <button
                    type="button"
                    className="kd-stack-remove"
                    aria-label={`从本课移出 ${item.title}`}
                    onClick={() => onRemoveMaterial(item.id, item.title)}
                  >
                    移出
                  </button>
                ) : null}
              </li>
            ))}
          </ul>
        ) : null}
      </section>

      <section className="kd-object kd-card-box">
        <h2><Archive /> 今天要复习</h2>
        <div className="kd-due-count">{dueCount}</div>
        <p>张卡片 · 随时可以停</p>
        <button type="button" disabled={!dueCount} onClick={onReviewCards ?? onFutureFeature}>
          {dueCount ? "开始复习" : "今天已复习完"}
        </button>
      </section>
    </>
  );
}
