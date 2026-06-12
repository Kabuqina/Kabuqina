// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { BookOpenText, Code2, FileSearch, FileText, GraduationCap, Palette, PanelRightClose } from "lucide-react";
import { useState, type CSSProperties, type ReactNode } from "react";
import { useI18n } from "../lib/i18n";
import { cn } from "../lib/cn";
import { PPT_VISUAL_MASTERS, type PptVisualMaster } from "./pptx/visualMasters";

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
  onStartPrompt?: (prompt: string) => void;
  goal?: string | null;
  materials: WorkspaceItem[];
  outputs: WorkspaceItem[];
  activeTool?: string | null;
  activity: WorkspaceActivity[];
};

// PPT_VISUAL_MASTERS + PptVisualMaster now live in ./pptx/visualMasters (shared with the renderer).

// Target languages for formula→code. Mirrors OFFERED_LANGUAGES in
// hermes_core/tools/math_expression_tools.py (SymPy canonical core, then printer).
const MATH_TARGET_LANGUAGES = [
  { id: "python", label: "Python" },
  { id: "numpy", label: "NumPy" },
  { id: "javascript", label: "JavaScript" },
  { id: "octave", label: "MATLAB/Octave" },
  { id: "fortran", label: "Fortran" },
] as const;
type MathLanguageId = (typeof MATH_TARGET_LANGUAGES)[number]["id"];
type PptMasterPreviewStyle = CSSProperties & {
  "--kq-ppt-bg": string;
  "--kq-ppt-title": string;
  "--kq-ppt-accent": string;
  "--kq-ppt-accent-2": string;
  "--kq-ppt-muted": string;
  "--kq-ppt-pattern": string;
};

function pptMasterPreviewStyle(master: PptVisualMaster): PptMasterPreviewStyle {
  return {
    "--kq-ppt-bg": master.palette.background,
    "--kq-ppt-title": master.palette.title,
    "--kq-ppt-accent": master.palette.accent,
    "--kq-ppt-accent-2": master.palette.accent2,
    "--kq-ppt-muted": master.palette.muted,
    "--kq-ppt-pattern": master.palette.pattern,
  };
}

function WorkspaceSectionHeading({ children }: { children: ReactNode }) {
  return (
    <h3 className="workspace-section-heading kq-section-heading inline-flex px-3 py-1.5 text-sm font-semibold leading-snug tracking-normal dark:border-l-[#9b87b8] dark:bg-zinc-800/40 dark:text-zinc-200">
      {children}
    </h3>
  );
}

function WorkspaceSection({ sectionId, title, children }: {
  sectionId: string;
  title: string;
  children?: ReactNode;
}) {
  return (
    <section
      data-workspace-section={sectionId}
      className="kq-workspace-card dark:border-zinc-800 dark:bg-zinc-900/60"
    >
      <WorkspaceSectionHeading>{title}</WorkspaceSectionHeading>
      {children}
    </section>
  );
}

function WorkspaceActionButton({
  icon,
  label,
  onClick,
}: {
  icon: ReactNode;
  label: string;
  onClick?: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="kq-quick-action justify-start rounded-lg px-3 py-2.5 text-left text-[15px] leading-snug transition"
    >
      {icon}
      {label}
    </button>
  );
}

function PptVisualMasterPreview({ master }: { master: PptVisualMaster }) {
  return (
    <div
      className={cn("kq-ppt-master-preview", `kq-ppt-master-preview--${master.id}`)}
      style={pptMasterPreviewStyle(master)}
      aria-label={`${master.name} preview`}
    >
      <div className="kq-ppt-master-slide">
        <div className="kq-ppt-master-kicker" />
        <div className="kq-ppt-master-title" />
        <div className="kq-ppt-master-body">
          <span />
          <span />
          <span />
        </div>
        <div className="kq-ppt-master-visual">
          <i />
          <i />
          <i />
        </div>
      </div>
      <div className="min-w-0">
        <p className="truncate text-[12px] font-semibold leading-snug text-[var(--kq-color-strong)]">
          {master.name}
        </p>
        <p className="mt-0.5 text-[11px] leading-snug text-[var(--kq-color-muted)]">
          {master.note}
        </p>
        <div className="kq-ppt-master-swatches" aria-hidden>
          {master.palette.swatches.map((color) => (
            <span key={color} style={{ background: color }} />
          ))}
        </div>
      </div>
    </div>
  );
}

export function WorkspacePanel({
  className,
  onCollapse,
  onStartPrompt,
}: WorkspacePanelProps) {
  const { t } = useI18n();
  const [pptVisualMaster, setPptVisualMaster] = useState<(typeof PPT_VISUAL_MASTERS)[number]["id"]>("soft_editorial");
  const selectedPptVisualMaster =
    PPT_VISUAL_MASTERS.find((item) => item.id === pptVisualMaster) ?? PPT_VISUAL_MASTERS[0];
  const [mathLanguage, setMathLanguage] = useState<MathLanguageId>("python");
  const selectedMathLanguage =
    MATH_TARGET_LANGUAGES.find((item) => item.id === mathLanguage) ?? MATH_TARGET_LANGUAGES[0];
  const buildPptPrompt = (sections: string[]) => sections.join("\n\n");
  const studentPptQualityRules =
    "质量要求：默认生成高质量可交付 PPT，而不是纯文字摘要。Markdown 大纲中每页必须标注 slide_type（agenda / claim_bullets / diagram / table / screenshot_placeholder / chart_placeholder / qa_backup / closing 之一）、页面标题、3-5 条要点、讲稿提示 notes、证据对象或占位说明。没有真实截图或图表时，不要假装已经插入素材，改用 screenshot_placeholder 或 chart_placeholder，并写清楚应替换成什么真实材料。至少包含 1 页 qa_backup 备用答辩页。每页会按内容自动选择版式；若某页需要特定设计，可在该 slide 上额外指定 layout（hero_statement / standard_bullets / two_column_bullets / comparison_cards / process_flow_horizontal / process_flow_vertical / data_table / media_placeholder / section_divider 之一），不指定则由渲染器根据该页内容自动挑选。";
  const pptVisualMasterRule =
    `视觉母版：用户已选择 ${selectedPptVisualMaster.name}（visual_master=${selectedPptVisualMaster.id}）。在 review_outline 通过后，调用 pptx_write 时必须传入 template 和 visual_master 两个参数；visual_master 使用 "${selectedPptVisualMaster.id}"。`;
  const paperToPptPrompt = buildPptPrompt([
    "请把我上传的论文、文献 PDF 或粘贴的论文内容转换成论文/文献汇报 PPT。",
    studentPptQualityRules,
    pptVisualMasterRule,
    "论文/文献汇报必须覆盖：研究背景/问题、研究方法或系统框架 diagram、关键实现或分析证据、结果/测试/实验汇总、创新点或贡献、局限与展望、老师可能追问 qa_backup。",
    "流程必须是：1) 先使用 pdf_read_precise 或可用文件工具读取材料；2) 调用 material_index_build 生成通用素材索引（素材索引用于整理 sections / tables / figures / screenshots / evidence / uncertain_parts / generation_hints，不是 PPT 专属）；3) 根据素材索引生成高质量可交付 Markdown PPT 大纲，包含每页 slide_type、标题、要点、证据/占位、notes；4) 调用 review_outline 让我在前端选择“通过 / 补充要求 / 自行编辑”；5) 我确认后再调用 pptx_write 生成 .pptx 文件到 workspace，slides 使用结构化字段，并返回文件路径。",
    `模板使用 paper_report，视觉母版使用 ${selectedPptVisualMaster.id}。`,
  ]);
  const courseToPptPrompt = buildPptPrompt([
    "请把我提供的课程笔记、章节要点、学习材料或粘贴的内容转换成课程学习汇报 PPT。",
    studentPptQualityRules,
    pptVisualMasterRule,
    "课程汇报必须覆盖：知识结构图 diagram、关键概念解释、案例/例题/应用场景、对比 table 或流程 diagram、学习总结/个人收获、难点或易错点 qa_backup。",
    "流程必须是：1) 先使用可用文件工具读取材料；2) 调用 material_index_build 生成通用素材索引（素材索引用于整理 sections / tables / figures / screenshots / evidence / uncertain_parts / generation_hints，不是 PPT 专属）；3) 根据素材索引生成高质量可交付 Markdown PPT 大纲，包含每页 slide_type、标题、要点、证据/占位、notes；4) 调用 review_outline 让我在前端选择“通过 / 补充要求 / 自行编辑”；5) 我确认后再调用 pptx_write 生成 .pptx 文件到 workspace，slides 使用结构化字段，并返回文件路径。",
    `模板使用 course_report，视觉母版使用 ${selectedPptVisualMaster.id}。`,
  ]);
  const codeToPptPrompt = buildPptPrompt([
    "请把我提供的代码项目或课设材料转换成课设答辩 PPT。",
    studentPptQualityRules,
    pptVisualMasterRule,
    "课设答辩必须覆盖：项目背景与目标、总体架构 diagram、模块调用/数据流/核心实现流程 diagram、运行结果 screenshot_placeholder 或真实截图、测试结果 table、问题与解决方案、部署运行说明或核心代码说明 qa_backup。",
    "流程必须是：1) 阅读项目结构、README、关键代码和结果材料；2) 调用 material_index_build 生成通用素材索引（素材索引用于整理 sections / tables / figures / screenshots / code_files / evidence / uncertain_parts / generation_hints，不是 PPT 专属）；3) 根据素材索引生成高质量可交付 Markdown PPT 大纲，覆盖项目背景、目标、架构、关键实现、运行结果、问题与改进，并包含每页 slide_type、证据/占位、notes；4) 调用 review_outline 让我确认“通过 / 补充要求 / 自行编辑”；5) 我确认后再调用 pptx_write 生成 .pptx 文件到 workspace，slides 使用结构化字段，并返回文件路径。",
    `模板使用 code_defense，视觉母版使用 ${selectedPptVisualMaster.id}。`,
  ]);
  const codeToFormulaPrompt =
    [
      "请把我提供的代码转换成清晰的数学公式表达。",
      "请先识别变量、输入输出、循环/递推/损失函数/约束条件，再用 LaTeX 给出对应公式；如果代码语义不完整，请列出需要我补充的上下文。",
      "最后必须给出语义核对清单：变量含义、维度/定义域、边界条件、输出范围或不变量，并说明这些公式是否覆盖原代码的全部关键分支。",
    ].join("\n\n");
  const formulaToCodePrompt = [
    `请把我提供的数学公式转换成 ${selectedMathLanguage.label} 代码，并加入公式语义校验层。`,
    `调用 math_formula_to_code 时使用 language="${selectedMathLanguage.id}"。该工具会先用 SymPy 把公式规范化为标准表达式，再用 SymPy 的代码打印器转成目标语言，并用 NumPy lambdify 对照 SymPy evalf 做数值自检（结果在 validation 字段）。`,
    "先输出 semantic_contract：逐条列出变量含义、维度、定义域/取值范围、前提条件、输出范围、不变量，以及结论必须满足的开闭区间或边界要求。",
    "必须生成并运行可执行测试：至少覆盖一个正常样例、一个边界/端点样例、一个反例或失败样例；如果公式有解析解或已知性质，加入 property/随机测试。",
    "测试通过条件不能只看数值误差，还必须逐条检查 semantic_contract。例如存在 c ∈ (a,b) 时，必须断言 a < c < b，端点不能标绿。",
    "如果无法自动验证某条语义约束，请明确标为 needs_human_check，不要把结果包装成完全通过。",
  ].join("\n\n");
  const mathFormulaExtractPrompt =
    "请从我上传的图片、PDF 或文档中提取数学公式。优先使用可用的精确读取/公式识别工具，输出 LaTeX、公式含义和所在页码或位置；识别不确定的符号请明确标注，并给出需要人工确认的候选。";

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
        <WorkspaceSection sectionId="workspace.reportPpt" title={t("chat.workspaceReportPpt")}>
          <div className="mt-3 grid gap-2">
            <WorkspaceActionButton
              onClick={() => onStartPrompt?.(courseToPptPrompt)}
              icon={<GraduationCap className="kq-color-icon-course mr-2 inline h-4 w-4" aria-hidden />}
              label={t("chat.workspaceCourseToPpt")}
            />
            <WorkspaceActionButton
              onClick={() => onStartPrompt?.(paperToPptPrompt)}
              icon={<BookOpenText className="kq-color-icon-book mr-2 inline h-4 w-4" aria-hidden />}
              label={t("chat.workspacePaperToPpt")}
            />
            <WorkspaceActionButton
              onClick={() => onStartPrompt?.(codeToPptPrompt)}
              icon={<Code2 className="kq-color-icon-pen mr-2 inline h-4 w-4" aria-hidden />}
              label={t("chat.workspaceCodeToPpt")}
            />
            <label className="kq-workspace-body grid gap-1.5 text-[13px] leading-snug text-zinc-700 dark:text-zinc-300">
              <span className="inline-flex items-center gap-1.5 font-medium">
                <Palette className="h-3.5 w-3.5 text-violet-600 dark:text-violet-300" aria-hidden />
                {t("chat.workspacePptVisualMaster")}
              </span>
              <select
                value={pptVisualMaster}
                onChange={(event) => setPptVisualMaster(event.currentTarget.value as typeof pptVisualMaster)}
                className="rounded-md border border-[#e8e0ed] bg-white px-2 py-1.5 text-sm text-zinc-800 outline-none transition focus:border-violet-400 focus:ring-2 focus:ring-violet-100 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100 dark:focus:border-violet-500 dark:focus:ring-violet-950/60"
              >
                {PPT_VISUAL_MASTERS.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name}
                  </option>
                ))}
              </select>
            </label>
            <PptVisualMasterPreview master={selectedPptVisualMaster} />
          </div>
        </WorkspaceSection>

        <WorkspaceSection sectionId="workspace.mathAbility" title={t("chat.workspaceMathAbility")}>
          <div className="mt-3 grid gap-2">
            <label className="kq-workspace-body grid gap-1.5 text-[13px] leading-snug text-zinc-700 dark:text-zinc-300">
              <span className="inline-flex items-center gap-1.5 font-medium">
                <Code2 className="h-3.5 w-3.5 text-violet-600 dark:text-violet-300" aria-hidden />
                {t("chat.workspaceMathLanguage")}
              </span>
              <select
                value={mathLanguage}
                onChange={(event) => setMathLanguage(event.currentTarget.value as MathLanguageId)}
                className="rounded-md border border-[#e8e0ed] bg-white px-2 py-1.5 text-sm text-zinc-800 outline-none transition focus:border-violet-400 focus:ring-2 focus:ring-violet-100 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100 dark:focus:border-violet-500 dark:focus:ring-violet-950/60"
              >
                {MATH_TARGET_LANGUAGES.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.label}
                  </option>
                ))}
              </select>
            </label>
            <WorkspaceActionButton
              onClick={() => onStartPrompt?.(codeToFormulaPrompt)}
              icon={<Code2 className="kq-color-icon-pen mr-2 inline h-4 w-4" aria-hidden />}
              label={t("chat.workspaceCodeToFormula")}
            />
            <WorkspaceActionButton
              onClick={() => onStartPrompt?.(formulaToCodePrompt)}
              icon={<FileText className="kq-color-icon-book mr-2 inline h-4 w-4" aria-hidden />}
              label={t("chat.workspaceFormulaToCode")}
            />
            <WorkspaceActionButton
              onClick={() => onStartPrompt?.(mathFormulaExtractPrompt)}
              icon={<FileSearch className="kq-color-icon-download mr-2 inline h-4 w-4" aria-hidden />}
              label={t("chat.workspaceMathFormulaExtract")}
            />
          </div>
        </WorkspaceSection>

      </div>
    </aside>
  );
}
