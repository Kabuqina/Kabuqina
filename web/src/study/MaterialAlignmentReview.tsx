// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useState } from "react";
import { useI18n } from "../lib/i18n";
import {
  readMaterialAlignment,
  sectionTitles,
  type AlignmentAttachment,
  type AlignmentGroup,
  type MaterialAlignmentPayload,
  type MaterialRole,
} from "./materialAlignment";

/**
 * 多材料对齐的确认界面（架构 §2.1.2 / 账本 B-9）。
 *
 * 小娜做的是**声明对应**而不是发明结构，所以这里每一条都必须让学生能核对：
 * 骨架给理由、每条挂靠写「来源 → 骨架的哪一节」并给理由、挂不上的显式列出、
 * 归不了课的也列出。**学生不确认，什么都不生效。**
 *
 * 三条红线在这个界面上的落法：
 * - 不显示任何覆盖率/百分比——契约里根本没有 coverage 字段，前端也不许自己算；
 * - 挂不上的与归不了课的都要出现，不藏；
 * - "确认"只确认这批判断，不代表课程本已经建好（激活的边界见账本 B-9）。
 */
export function MaterialAlignmentReview({
  envelope,
  onConfirm,
  onReject,
  busy = false,
}: {
  envelope: unknown;
  /** 省略时不渲染动作行——宿主（如草稿箱）已经有自己的确认/拒绝按钮。 */
  onConfirm?: () => void;
  onReject?: () => void;
  busy?: boolean;
}) {
  const { t } = useI18n();
  const payload = readMaterialAlignment(envelope);

  if (!payload) {
    // 读不出就说读不出，不要拿半个 payload 渲染出一个看起来像判断的东西。
    return (
      <p className="kq-study-muted" role="alert">
        {t("study.alignUnreadable")}
      </p>
    );
  }

  return (
    <div className="kq-align-review">
      <p className="kq-study-muted">{t("study.alignLead")}</p>

      {payload.course_groups.map((group) => (
        <AlignmentGroupView key={group.group_id || group.proposed_title} group={group} payload={payload} />
      ))}

      {payload.ungrouped.length ? (
        <section className="kq-align-block kq-align-block--gap">
          <h3>{t("study.alignUngrouped")}</h3>
          <p className="kq-study-muted">{t("study.alignUngroupedLead")}</p>
          <ul>
            {payload.ungrouped.map((item) => {
              const material = payload.materials.find((m) => m.material_id === item.material_id);
              return (
                <li key={item.material_id}>
                  <strong>{material?.title ?? item.material_id}</strong>
                  <small>{item.reason}</small>
                </li>
              );
            })}
          </ul>
        </section>
      ) : null}

      {onConfirm || onReject ? (
        <div className="kq-align-actions">
          {onConfirm ? (
            <button type="button" className="kq-align-primary" onClick={onConfirm} disabled={busy}>
              {t("study.alignConfirm")}
            </button>
          ) : null}
          {onReject ? (
            <button type="button" className="kq-align-secondary" onClick={onReject} disabled={busy}>
              {t("study.alignReject")}
            </button>
          ) : null}
        </div>
      ) : null}
      <p className="kq-study-muted">{t("study.alignConfirmNote")}</p>
    </div>
  );
}

function AlignmentGroupView({
  group,
  payload,
}: {
  group: AlignmentGroup;
  payload: MaterialAlignmentPayload;
}) {
  const { t } = useI18n();
  const skeletonMaterial = payload.materials.find(
    (m) => m.material_id === group.skeleton.material_id,
  );
  const sections = sectionTitles(skeletonMaterial);

  return (
    <section className="kq-align-block">
      <header>
        <h3>{group.proposed_title}</h3>
        <p className="kq-study-muted">{group.rationale}</p>
      </header>

      {/* 骨架：提名 + 理由。目录只来自这一份真实文件。 */}
      <div className="kq-align-skeleton">
        <span className="kq-align-tag">{t("study.alignSkeleton")}</span>
        <div>
          <strong>{skeletonMaterial?.title ?? group.skeleton.material_id}</strong>
          <small>{group.skeleton.reason}</small>
          <small>
            {t("study.alignSectionCount", { count: skeletonMaterial?.structure.length ?? 0 })}
          </small>
        </div>
      </div>

      {group.attachments.map((attachment) => (
        <AttachmentView
          key={attachment.material_id}
          attachment={attachment}
          title={
            payload.materials.find((m) => m.material_id === attachment.material_id)?.title
            ?? attachment.material_id
          }
          sections={sections}
        />
      ))}
    </section>
  );
}

function roleLabelKey(role: MaterialRole): string {
  return `study.alignRole.${role}`;
}

function AttachmentView({
  attachment,
  title,
  sections,
}: {
  attachment: AlignmentAttachment;
  title: string;
  sections: ReturnType<typeof sectionTitles>;
}) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const shown = open ? attachment.mappings : attachment.mappings.slice(0, 3);
  const hidden = attachment.mappings.length - shown.length;

  return (
    <div className="kq-align-attachment">
      <div className="kq-align-attachment-head">
        <strong>{title}</strong>
        <span className="kq-align-tag">{t(roleLabelKey(attachment.role))}</span>
      </div>
      <small className="kq-study-muted">{attachment.role_reason}</small>

      {shown.length ? (
        <ul className="kq-align-mappings">
          {shown.map((mapping, index) => {
            const target = sections.get(mapping.target_section_id);
            return (
              <li key={`${mapping.source_locator}:${index}`}>
                {/* 可核对的断言：学生点开两边就能验证。 */}
                <span className="kq-align-arrow">
                  {mapping.source_locator} → {target?.title ?? mapping.target_section_id}
                </span>
                <small>{mapping.reason}</small>
              </li>
            );
          })}
        </ul>
      ) : null}

      {hidden > 0 ? (
        <button type="button" className="kq-align-more" onClick={() => setOpen(true)}>
          {t("study.alignShowAll", { count: hidden })}
        </button>
      ) : null}

      {attachment.unaligned.length ? (
        <div className="kq-align-gaps">
          <span>{t("study.alignUnaligned")}</span>
          <ul>
            {attachment.unaligned.map((gap, index) => (
              <li key={`${gap.source_locator}:${index}`}>
                <span>{gap.source_locator}</span>
                <small>{gap.reason}</small>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}
