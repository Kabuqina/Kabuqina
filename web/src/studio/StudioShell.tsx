// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useState } from "react";
import { Link } from "react-router-dom";
import { ArrowLeft, FolderOpen, MessageCircle, Plus } from "lucide-react";
import { useI18n } from "../lib/i18n";
import type { StudioProject } from "./studio-api";

/**
 * Studio 空间。架构 §3.3 本轮只冻结整体布局，不冻结中央工作面的最终形态
 * （画布 / 编辑器 / 时间线 / 页面列表都还没决定）：
 *
 * - 左：项目册，切换与新建；
 * - 中：当前 Project 的稳定工作面，先呈现 Brief 与下一步；
 * - 右：来源与连接，显示可追溯的只读快照。
 *
 * 与 Study 共用同一产品 shell 与纸张语言，但**不伪装成课程本**——
 * Studio 的容器是项目册不是书立，主对象是观点不是知识核。
 */
export function StudioShell({
  projects,
  currentProjectId,
  onSelectProject,
  onCreateProject,
  onSaveBrief,
  busy,
}: {
  projects: StudioProject[];
  currentProjectId: string | null;
  onSelectProject: (id: string) => void;
  onCreateProject: () => void;
  onSaveBrief: (projectId: string, brief: string) => void;
  busy: boolean;
}) {
  const { t } = useI18n();
  const current = projects.find((p) => p.id === currentProjectId) ?? null;

  return (
    <div className="kq-studio-shell">
      <header className="kq-study-topbar">
        <Link className="kq-study-icon-link" to="/chat" aria-label={t("studio.backToChat")}>
          <ArrowLeft aria-hidden />
        </Link>
        <span className="kq-studio-title">{t("studio.title")}</span>
        <div className="kq-study-topbar-actions">
          <Link className="kq-study-top-action" to="/study">
            <FolderOpen aria-hidden />
            <span>{t("studio.toStudy")}</span>
          </Link>
          <Link className="kq-study-top-action" to="/chat">
            <MessageCircle aria-hidden />
            <span>{t("studio.askNana")}</span>
          </Link>
        </div>
      </header>

      <div className="kq-studio-body">
        {/* 左：项目册 */}
        <nav className="kq-studio-rail" aria-label={t("studio.projectsLabel")}>
          <h2 className="kq-studio-rail-title">{t("studio.projectsLabel")}</h2>
          {projects.length ? (
            <ul className="kq-studio-project-list">
              {projects.map((project) => (
                <li key={project.id}>
                  <button
                    type="button"
                    className="kq-studio-project"
                    aria-current={project.id === currentProjectId ? "true" : undefined}
                    onClick={() => onSelectProject(project.id)}
                  >
                    <strong>{project.title}</strong>
                    <small>{project.brief ? project.brief : t("studio.briefEmptyShort")}</small>
                  </button>
                </li>
              ))}
            </ul>
          ) : null}
          <button type="button" className="kq-studio-new" onClick={onCreateProject} disabled={busy}>
            <Plus aria-hidden />
            <span>{t("studio.newProject")}</span>
          </button>
        </nav>

        {/* 中：当前项目的工作面 */}
        <main className="kq-studio-main">
          {current ? (
            <ProjectDesk project={current} onSaveBrief={onSaveBrief} busy={busy} />
          ) : (
            <div className="kq-studio-empty">
              <h2>{t("studio.emptyTitle")}</h2>
              <p>{t("studio.emptyLead")}</p>
              <button type="button" className="kq-studio-new" onClick={onCreateProject} disabled={busy}>
                <Plus aria-hidden />
                <span>{t("studio.newProject")}</span>
              </button>
            </div>
          )}
        </main>

        {/* 右：来源与连接 */}
        <aside className="kq-studio-sources" aria-label={t("studio.sourcesLabel")}>
          <h2 className="kq-studio-rail-title">{t("studio.sourcesLabel")}</h2>
          {current && current.sources.length ? (
            <ul className="kq-studio-source-list">
              {current.sources.map((source) => (
                <li key={source.id} className="kq-studio-source">
                  <strong>{source.title}</strong>
                  <small>{source.origin}</small>
                </li>
              ))}
            </ul>
          ) : (
            <p className="kq-studio-muted">{t("studio.sourcesEmpty")}</p>
          )}
        </aside>
      </div>
    </div>
  );
}

/**
 * 项目从表达目标开始，不从文件格式开始——所以工作面第一件事是 Brief，
 * 而不是"选择导出格式"。
 */
function ProjectDesk({
  project,
  onSaveBrief,
  busy,
}: {
  project: StudioProject;
  onSaveBrief: (projectId: string, brief: string) => void;
  busy: boolean;
}) {
  const { t } = useI18n();
  const [draft, setDraft] = useState(project.brief);
  const dirty = draft.trim() !== project.brief.trim();

  return (
    <div className="kq-studio-page">
      <h1 className="kq-studio-project-title">{project.title}</h1>

      <section className="kq-studio-card">
        <h2>{t("studio.briefTitle")}</h2>
        <p className="kq-studio-muted">{t("studio.briefLead")}</p>
        <textarea
          className="kq-studio-brief"
          value={draft}
          onChange={(event) => setDraft(event.currentTarget.value)}
          placeholder={t("studio.briefPlaceholder")}
          rows={4}
        />
        <div className="kq-studio-actions">
          <button
            type="button"
            className="kq-studio-primary"
            disabled={!dirty || busy}
            onClick={() => onSaveBrief(project.id, draft.trim())}
          >
            {t("studio.briefSave")}
          </button>
        </div>
      </section>

      {/* 取材由 Studio 侧发起（架构 §4.1：Study 不向外推送）。 */}
      <section className="kq-studio-card">
        <h2>{t("studio.gatherTitle")}</h2>
        <p className="kq-studio-muted">{t("studio.gatherLead")}</p>
        <div className="kq-studio-actions">
          <button type="button" className="kq-studio-secondary" disabled>
            {t("studio.gatherCta")}
          </button>
          <span className="kq-studio-muted">{t("studio.gatherPending")}</span>
        </div>
      </section>
    </div>
  );
}
