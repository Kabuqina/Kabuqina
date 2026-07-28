// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useI18n } from "../lib/i18n";
import { parseLearnArtifact } from "./learnArtifact";
import { MaterialAlignmentReview } from "./MaterialAlignmentReview";
import type { StudyArtifactDetail } from "./repository";

function TextList({ title, values }: { title: string; values: string[] }) {
  if (!values.length) return null;
  return <section className="kq-study-learn-copy"><h4>{title}</h4><ul>{values.map((value, index) => <li key={`${index}:${value}`}>{value}</li>)}</ul></section>;
}

/** Render only the narrow, validated M5 payload contract. */
export function LearnArtifactContent({ detail, degraded = false }: { detail: StudyArtifactDetail; degraded?: boolean }) {
  const { t } = useI18n();
  // 对齐提案不属于 M5 的 learn payload 契约，先分流；否则会被判成 degraded。
  // 动作交给宿主（草稿箱已有确认/拒绝），这里只负责把判断摊开给学生核对。
  if (detail.kind === "material_alignment") {
    return <MaterialAlignmentReview envelope={detail.envelope} />;
  }
  const content = parseLearnArtifact(detail);
  if (!content || degraded) return <p className="kq-study-page-error" role="alert">{t("study.learnDraftDegraded")}</p>;
  if (content.kind === "knowledge_base") {
    return <section className="kq-study-learn-copy"><h4>{t("study.learnConcepts")}</h4><dl>{content.concepts.map((concept) => <div key={concept.term}><dt>{concept.term}</dt><dd>{concept.explanation}</dd></div>)}</dl></section>;
  }
  if (content.kind === "resource_pack") {
    return <section className="kq-study-learn-copy"><ul>{content.resources.map((resource) => <li key={`${resource.title}:${resource.purpose}`}><strong>{resource.title}</strong><p><span>{t("study.learnResourcePurpose")}</span>{resource.purpose}</p>{resource.credibility ? <p><span>{t("study.learnResourceCredibility")}</span>{resource.credibility}</p> : null}</li>)}</ul></section>;
  }
  return <section className="kq-study-learn-copy"><h4>{t("study.learnTutoringGoal")}</h4><p>{content.goal}</p><TextList title={t("study.learnHints")} values={content.hints} /><TextList title={t("study.learnMisconceptions")} values={content.misconceptions} /><TextList title={t("study.learnNextSteps")} values={content.nextSteps} /></section>;
}
