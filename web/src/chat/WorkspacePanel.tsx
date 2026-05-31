import { AlarmClock, BookOpenText, CheckCircle2, Code2, Download, FileSearch, FileText, FolderKanban, GraduationCap, PanelRightClose, Wrench } from "lucide-react";
import type { ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { useI18n } from "../lib/i18n";
import { cn } from "../lib/cn";

export type WorkspaceItem = {
  id: string;
  label: string;
  detail?: string;
};

export type WorkspaceActivity = {
  id: string;
  label: string;
  detail?: string;
  running?: boolean;
};

type WorkspacePanelProps = {
  className?: string;
  onCollapse: () => void;
  onOrganizeDesktop?: () => void;
  onStartPrompt?: (prompt: string) => void;
  goal?: string | null;
  materials: WorkspaceItem[];
  outputs: WorkspaceItem[];
  activeTool?: string | null;
  activity: WorkspaceActivity[];
};

function WorkspaceSectionHeading({ children }: { children: ReactNode }) {
  return (
    <h3 className="workspace-section-heading kq-section-heading inline-flex px-3 py-1.5 text-sm font-semibold leading-snug tracking-normal dark:border-l-[#9b87b8] dark:bg-zinc-800/40 dark:text-zinc-200">
      {children}
    </h3>
  );
}

function WorkspaceSection({
  sectionId,
  title,
  body,
  children,
}: {
  sectionId: string;
  title: string;
  body: string;
  children?: ReactNode;
}) {
  return (
    <section
      data-workspace-section={sectionId}
      className="kq-workspace-card dark:border-zinc-800 dark:bg-zinc-900/60"
    >
      <WorkspaceSectionHeading>{title}</WorkspaceSectionHeading>
      {children ?? (
        <p className="kq-workspace-body mt-3 dark:text-zinc-300">
          {body}
        </p>
      )}
    </section>
  );
}

function WorkspaceItemList({
  items,
  icon,
}: {
  items: WorkspaceItem[];
  icon: "file" | "output";
}) {
  const Icon = icon === "output" ? CheckCircle2 : FileText;
  return (
    <ul className="mt-3 space-y-2">
      {items.map((item) => (
        <li key={item.id} className="min-w-0">
          <div className="flex min-w-0 items-start gap-2">
            <Icon className="mt-0.5 h-4 w-4 shrink-0 text-zinc-500 dark:text-zinc-400" aria-hidden />
            <div className="min-w-0">
              <div className="truncate text-sm font-medium text-zinc-800 dark:text-zinc-100" title={item.label}>
                {item.label}
              </div>
              {item.detail ? (
                <div className="mt-0.5 truncate text-[13px] leading-snug text-zinc-600 dark:text-zinc-400" title={item.detail}>
                  {item.detail}
                </div>
              ) : null}
            </div>
          </div>
        </li>
      ))}
    </ul>
  );
}

export function WorkspacePanel({
  className,
  onCollapse,
  onOrganizeDesktop,
  onStartPrompt,
  goal,
  materials,
  outputs,
  activeTool,
  activity,
}: WorkspacePanelProps) {
  const { t } = useI18n();
  const nav = useNavigate();
  const studentPptQualityRules =
    "质量要求：默认生成高质量可交付 PPT，而不是纯文字摘要。Markdown 大纲中每页必须标注 slide_type（agenda / claim_bullets / diagram / table / screenshot_placeholder / chart_placeholder / qa_backup / closing 之一）、页面标题、3-5 条要点、讲稿提示 notes、证据对象或占位说明。没有真实截图或图表时，不要假装已经插入素材，改用 screenshot_placeholder 或 chart_placeholder，并写清楚应替换成什么真实材料。至少包含 1 页 qa_backup 备用答辩页。";
  const paperToPptPrompt =
    `请把我上传的论文、文献 PDF 或粘贴的论文内容转换成论文/文献汇报 PPT。${studentPptQualityRules}论文/文献汇报必须覆盖：研究背景/问题、研究方法或系统框架 diagram、关键实现或分析证据、结果/测试/实验汇总、创新点或贡献、局限与展望、老师可能追问 qa_backup。流程必须是：1) 先使用 pdf_read_precise 或可用文件工具读取材料；2) 调用 material_index_build 生成通用素材索引（素材索引用于整理 sections / tables / figures / screenshots / evidence / uncertain_parts / generation_hints，不是 PPT 专属）；3) 根据素材索引生成高质量可交付 Markdown PPT 大纲，包含每页 slide_type、标题、要点、证据/占位、notes；4) 调用 review_outline 让我在前端选择“通过 / 补充要求 / 自行编辑”；5) 我确认后再调用 pptx_write 生成 .pptx 文件到 workspace，slides 使用结构化字段，并返回文件路径。模板使用 paper_report。`;
  const courseToPptPrompt =
    `请把我提供的课程笔记、章节要点、学习材料或粘贴的内容转换成课程学习汇报 PPT。${studentPptQualityRules}课程汇报必须覆盖：知识结构图 diagram、关键概念解释、案例/例题/应用场景、对比 table 或流程 diagram、学习总结/个人收获、难点或易错点 qa_backup。流程必须是：1) 先使用可用文件工具读取材料；2) 调用 material_index_build 生成通用素材索引（素材索引用于整理 sections / tables / figures / screenshots / evidence / uncertain_parts / generation_hints，不是 PPT 专属）；3) 根据素材索引生成高质量可交付 Markdown PPT 大纲，包含每页 slide_type、标题、要点、证据/占位、notes；4) 调用 review_outline 让我在前端选择“通过 / 补充要求 / 自行编辑”；5) 我确认后再调用 pptx_write 生成 .pptx 文件到 workspace，slides 使用结构化字段，并返回文件路径。模板使用 course_report。`;
  const codeToPptPrompt =
    `请把我提供的代码项目或课设材料转换成课设答辩 PPT。${studentPptQualityRules}课设答辩必须覆盖：项目背景与目标、总体架构 diagram、模块调用/数据流/核心实现流程 diagram、运行结果 screenshot_placeholder 或真实截图、测试结果 table、问题与解决方案、部署运行说明或核心代码说明 qa_backup。流程必须是：1) 阅读项目结构、README、关键代码和结果材料；2) 调用 material_index_build 生成通用素材索引（素材索引用于整理 sections / tables / figures / screenshots / code_files / evidence / uncertain_parts / generation_hints，不是 PPT 专属）；3) 根据素材索引生成高质量可交付 Markdown PPT 大纲，覆盖项目背景、目标、架构、关键实现、运行结果、问题与改进，并包含每页 slide_type、证据/占位、notes；4) 调用 review_outline 让我确认“通过 / 补充要求 / 自行编辑”；5) 我确认后再调用 pptx_write 生成 .pptx 文件到 workspace，slides 使用结构化字段，并返回文件路径。模板使用 code_defense。`;
  const precisePdfPrompt =
    "请对我上传或指定的 PDF 做精确识别和结构化总结。优先使用 pdf_read_precise，保留标题、页码、表格和公式线索；如果公式或扫描页识别不可靠，请明确标注不确定处，并建议是否启用更精确的 OCR/公式识别模式。";

  return (
    <aside
      className={cn(
        "kq-workspace-panel flex w-64 shrink-0 flex-col border-l dark:border-zinc-700 dark:bg-zinc-950/40",
        className,
      )}
    >
      <div className="flex h-14 items-center justify-between border-b border-[#e8e0ed]/80 px-4 dark:border-zinc-800">
        <h2 className="text-base font-semibold tracking-normal text-[var(--kq-color-strong)] dark:text-zinc-100">
          {t("chat.workspaceTitle")}
        </h2>
        <button
          type="button"
          onClick={onCollapse}
          className="kq-soft-icon-btn inline-flex h-8 w-8 items-center justify-center rounded-md transition dark:hover:bg-zinc-800 dark:hover:text-zinc-100"
          aria-label={t("chat.workspaceCollapse")}
          title={t("chat.workspaceCollapse")}
        >
          <PanelRightClose className="h-4 w-4" aria-hidden />
        </button>
      </div>

      <div className="min-h-0 flex-1 space-y-4 overflow-y-auto px-4 py-4">
        <section data-workspace-section="workspace.quickActions">
          <WorkspaceSectionHeading>{t("chat.workspaceQuickActions")}</WorkspaceSectionHeading>
          <div className="mt-3 grid gap-2">
            <button
              type="button"
              onClick={() => nav("/settings/cron", { state: { cronBackTo: "/chat" } })}
              className="kq-quick-action justify-start rounded-lg px-3 py-2.5 text-left text-[15px] leading-snug transition"
            >
              <AlarmClock className="kq-color-icon-alarm mr-2 inline h-4 w-4" aria-hidden />
              {t("cron.title")}
            </button>
            <button
              type="button"
              onClick={onOrganizeDesktop}
              className="kq-quick-action justify-start rounded-lg px-3 py-2.5 text-left text-[15px] leading-snug transition"
            >
              <FolderKanban className="kq-color-icon-folder mr-2 inline h-4 w-4" aria-hidden />
              {t("chat.workspaceOrganizeDesktop")}
            </button>
            <button
              type="button"
              onClick={() => onStartPrompt?.(courseToPptPrompt)}
              className="kq-quick-action justify-start rounded-lg px-3 py-2.5 text-left text-[15px] leading-snug transition"
            >
              <GraduationCap className="kq-color-icon-course mr-2 inline h-4 w-4" aria-hidden />
              {t("chat.workspaceCourseToPpt")}
            </button>
            <button
              type="button"
              onClick={() => onStartPrompt?.(paperToPptPrompt)}
              className="kq-quick-action justify-start rounded-lg px-3 py-2.5 text-left text-[15px] leading-snug transition"
            >
              <BookOpenText className="kq-color-icon-book mr-2 inline h-4 w-4" aria-hidden />
              {t("chat.workspacePaperToPpt")}
            </button>
            <button
              type="button"
              onClick={() => onStartPrompt?.(codeToPptPrompt)}
              className="kq-quick-action justify-start rounded-lg px-3 py-2.5 text-left text-[15px] leading-snug transition"
            >
              <Code2 className="kq-color-icon-pen mr-2 inline h-4 w-4" aria-hidden />
              {t("chat.workspaceCodeToPpt")}
            </button>
            <button
              type="button"
              onClick={() => onStartPrompt?.(precisePdfPrompt)}
              className="kq-quick-action justify-start rounded-lg px-3 py-2.5 text-left text-[15px] leading-snug transition"
            >
              <FileSearch className="kq-color-icon-download mr-2 inline h-4 w-4" aria-hidden />
              {t("chat.workspacePrecisePdf")}
            </button>
            <button
              type="button"
              onClick={() => nav("/export")}
              className="kq-quick-action justify-start rounded-lg px-3 py-2.5 text-left text-[15px] leading-snug transition"
            >
              <Download className="kq-color-icon-download mr-2 inline h-4 w-4" aria-hidden />
              {t("chat.exportButton")}
            </button>
          </div>
        </section>

        <WorkspaceSection
          sectionId="workspace.currentGoal"
          title={t("chat.workspaceCurrentGoal")}
          body={t("chat.workspaceGoalEmpty")}
        >
          {goal || activeTool || activity.length ? (
            <div className="mt-3 space-y-3">
              {goal ? (
                <p className="kq-workspace-body dark:text-zinc-200">{goal}</p>
              ) : null}
              {activeTool ? (
                <div className="flex min-w-0 items-center gap-2 text-[13px] leading-snug text-zinc-700 dark:text-zinc-300">
                  <Wrench className="h-3.5 w-3.5 shrink-0 text-sky-600 dark:text-sky-400" aria-hidden />
                  <span className="truncate">{activeTool.replace(/_/g, " ")}</span>
                </div>
              ) : null}
              {activity.length ? (
                <ul className="space-y-1.5">
                  {activity.map((item) => (
                    <li key={item.id} className="min-w-0 text-[13px] leading-snug text-zinc-600 dark:text-zinc-400">
                      <span
                        className={cn(
                          "mr-1 inline-block h-1.5 w-1.5 rounded-full align-middle",
                          item.running ? "bg-amber-500 dark:bg-amber-300" : "bg-emerald-500 dark:bg-emerald-400",
                        )}
                        aria-hidden
                      />
                      <span className="font-medium text-zinc-600 dark:text-zinc-300">{item.label.replace(/_/g, " ")}</span>
                      {item.detail ? <span className="ml-1">{item.detail}</span> : null}
                    </li>
                  ))}
                </ul>
              ) : null}
            </div>
          ) : undefined}
        </WorkspaceSection>
        <WorkspaceSection
          sectionId="workspace.materials"
          title={t("chat.workspaceMaterials")}
          body={t("chat.workspaceMaterialsEmpty")}
        >
          {materials.length ? <WorkspaceItemList items={materials} icon="file" /> : undefined}
        </WorkspaceSection>
        <WorkspaceSection
          sectionId="workspace.outputs"
          title={t("chat.workspaceOutputs")}
          body={t("chat.workspaceOutputsEmpty")}
        >
          {outputs.length ? <WorkspaceItemList items={outputs} icon="output" /> : undefined}
        </WorkspaceSection>
      </div>
    </aside>
  );
}
