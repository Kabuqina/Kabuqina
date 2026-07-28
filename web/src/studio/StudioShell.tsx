// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowLeft, FolderOpen, MessageCircle, Plus, Trash2 } from "lucide-react";
import { useI18n } from "../lib/i18n";
import { GatherFromStudy } from "./GatherFromStudy";
import { buildStudioChatHandoff, persistPendingStudioHandoff } from "../lib/studioChatHandoff";
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
  onGathered,
  onDeleteProject,
  busy,
}: {
  projects: StudioProject[];
  currentProjectId: string | null;
  onSelectProject: (id: string) => void;
  onCreateProject: () => void;
  onSaveBrief: (projectId: string, brief: string) => void;
  onGathered?: () => void;
  onDeleteProject?: (project: StudioProject) => void;
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
            <ProjectDesk
              project={current}
              onSaveBrief={onSaveBrief}
              onGathered={onGathered}
              onDeleteProject={onDeleteProject}
              busy={busy}
            />
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
  onGathered,
  onDeleteProject,
  busy,
}: {
  project: StudioProject;
  onSaveBrief: (projectId: string, brief: string) => void;
  onGathered?: () => void;
  onDeleteProject?: (project: StudioProject) => void;
  busy: boolean;
}) {
  const { t } = useI18n();
  const nav = useNavigate();
  const [draft, setDraft] = useState(project.brief);
  const [gathering, setGathering] = useState(false);
  const dirty = draft.trim() !== project.brief.trim();

  /**
   * 从项目内进入 Studio Chat（架构 §3.3）。作用域由这次显式转交建立——
   * 全局 Chat 仍然默认自由会话，不会因为你有项目就自动绑上去（§8.10）。
   */
  const askInProject = () => {
    const handoff = buildStudioChatHandoff(project);
    persistPendingStudioHandoff(handoff);
    nav("/chat", { state: { studioHandoff: handoff } });
  };

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
          <button
            type="button"
            className="kq-studio-secondary"
            onClick={() => setGathering(true)}
            disabled={busy}
          >
            {t("studio.gatherCta")}
          </button>
        </div>
      </section>

      <section className="kq-studio-card">
        <h2>{t("studio.chatTitle")}</h2>
        <p className="kq-studio-muted">{t("studio.chatLead")}</p>
        <div className="kq-studio-actions">
          <button type="button" className="kq-studio-secondary" onClick={askInProject}>
            {t("studio.chatCta")}
          </button>
        </div>
      </section>

      {onDeleteProject ? (
        <section className="kq-studio-card kq-studio-card--quiet">
          <h2>{t("studio.deleteTitle")}</h2>
          {/* chatHistoryDeleted: false 是后端对用户的承诺，界面必须说出来。 */}
          <p className="kq-studio-muted">{t("studio.deleteLead")}</p>
          <div className="kq-studio-actions">
            <button
              type="button"
              className="kq-studio-danger"
              onClick={() => onDeleteProject(project)}
              disabled={busy}
            >
              <Trash2 aria-hidden />
              {t("studio.deleteCta")}
            </button>
          </div>
        </section>
      ) : null}

      {gathering ? (
        <GatherFromStudy
          projectId={project.id}
          onClose={() => setGathering(false)}
          onGathered={() => onGathered?.()}
        />
      ) : null}
    </div>
  );
}
