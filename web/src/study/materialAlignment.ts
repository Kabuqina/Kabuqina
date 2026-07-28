// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

/**
 * 多材料对齐提案的客户端形状（架构 §2.1.2 / 账本 B-9）。
 *
 * 字段严格照后端 `hermes_core/learning/material_alignment_contract.py` 的
 * `validate_material_alignment_payload`——那边会拒绝任何不合形状的 payload，
 * 所以这里只做**读取侧的窄化**，不自己发明字段。
 *
 * 特别注意：契约里**没有** coverage 一类字段，后端明令禁止。前端也不得自己算一个
 * "已对齐 N/M" 出来——那是覆盖率换皮（§2.1.2 红线 4）。
 */

export const MATERIAL_ROLES = ["explanation", "practice", "assessment", "reference"] as const;
export type MaterialRole = (typeof MATERIAL_ROLES)[number];

export type AlignmentSection = { section_id: string; title: string; locator: string };

export type AlignmentMaterial = {
  material_id: string;
  title: string;
  source_ref: string;
  structure: AlignmentSection[];
};

export type AlignmentSkeleton = {
  material_id: string;
  reason: string;
  role: MaterialRole;
  role_reason: string;
};

export type AlignmentMapping = {
  source_locator: string;
  target_section_id: string;
  reason: string;
};

export type AlignmentGap = { source_locator: string; reason: string };

export type AlignmentAttachment = {
  material_id: string;
  role: MaterialRole;
  role_reason: string;
  mappings: AlignmentMapping[];
  unaligned: AlignmentGap[];
};

export type AlignmentGroup = {
  group_id: string;
  proposed_title: string;
  rationale: string;
  material_ids: string[];
  skeleton: AlignmentSkeleton;
  attachments: AlignmentAttachment[];
};

export type AlignmentUngrouped = { material_id: string; reason: string };

export type MaterialAlignmentPayload = {
  schema_version: number;
  batch_id: string;
  materials: AlignmentMaterial[];
  course_groups: AlignmentGroup[];
  ungrouped: AlignmentUngrouped[];
};

function isRole(value: unknown): value is MaterialRole {
  return typeof value === "string" && (MATERIAL_ROLES as readonly string[]).includes(value);
}

/**
 * 从 artifact envelope 里取出对齐提案。**读不出就返回 null**，宁可显示"读不到"，
 * 也不要拿半个 payload 渲染出一个看起来像判断的东西。
 */
export function readMaterialAlignment(envelope: unknown): MaterialAlignmentPayload | null {
  if (!envelope || typeof envelope !== "object") return null;
  const raw = envelope as Record<string, unknown>;
  const payload = (raw.payload ?? raw) as Record<string, unknown>;
  const materials = payload.materials;
  const groups = payload.course_groups;
  if (!Array.isArray(materials) || !Array.isArray(groups) || !groups.length) return null;

  const parsedMaterials: AlignmentMaterial[] = [];
  for (const item of materials) {
    if (!item || typeof item !== "object") return null;
    const m = item as Record<string, unknown>;
    if (typeof m.material_id !== "string" || typeof m.title !== "string") return null;
    parsedMaterials.push({
      material_id: m.material_id,
      title: m.title,
      source_ref: typeof m.source_ref === "string" ? m.source_ref : "",
      structure: Array.isArray(m.structure)
        ? (m.structure as AlignmentSection[]).filter(
            (s) => s && typeof s.section_id === "string" && typeof s.title === "string",
          )
        : [],
    });
  }

  const parsedGroups: AlignmentGroup[] = [];
  for (const item of groups) {
    if (!item || typeof item !== "object") return null;
    const g = item as Record<string, unknown>;
    const skeleton = g.skeleton as Record<string, unknown> | undefined;
    if (!skeleton || typeof skeleton.material_id !== "string" || !isRole(skeleton.role)) return null;
    parsedGroups.push({
      group_id: typeof g.group_id === "string" ? g.group_id : "",
      proposed_title: typeof g.proposed_title === "string" ? g.proposed_title : "",
      rationale: typeof g.rationale === "string" ? g.rationale : "",
      material_ids: Array.isArray(g.material_ids) ? (g.material_ids as string[]) : [],
      skeleton: {
        material_id: skeleton.material_id,
        reason: typeof skeleton.reason === "string" ? skeleton.reason : "",
        role: skeleton.role,
        role_reason: typeof skeleton.role_reason === "string" ? skeleton.role_reason : "",
      },
      attachments: Array.isArray(g.attachments)
        ? (g.attachments as unknown[]).flatMap((a) => {
            if (!a || typeof a !== "object") return [];
            const att = a as Record<string, unknown>;
            if (typeof att.material_id !== "string" || !isRole(att.role)) return [];
            return [
              {
                material_id: att.material_id,
                role: att.role,
                role_reason: typeof att.role_reason === "string" ? att.role_reason : "",
                mappings: Array.isArray(att.mappings) ? (att.mappings as AlignmentMapping[]) : [],
                unaligned: Array.isArray(att.unaligned) ? (att.unaligned as AlignmentGap[]) : [],
              },
            ];
          })
        : [],
    });
  }

  return {
    schema_version: typeof payload.schema_version === "number" ? payload.schema_version : 1,
    batch_id: typeof payload.batch_id === "string" ? payload.batch_id : "",
    materials: parsedMaterials,
    course_groups: parsedGroups,
    ungrouped: Array.isArray(payload.ungrouped)
      ? (payload.ungrouped as AlignmentUngrouped[]).filter(
          (u) => u && typeof u.material_id === "string",
        )
      : [],
  };
}

/** 骨架那一节的标题，用来把 `target_section_id` 还原成学生看得懂的名字。 */
export function sectionTitles(
  material: AlignmentMaterial | undefined,
): Map<string, AlignmentSection> {
  const map = new Map<string, AlignmentSection>();
  for (const section of material?.structure ?? []) map.set(section.section_id, section);
  return map;
}
