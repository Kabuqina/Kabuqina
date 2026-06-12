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
  // Canonical planner rules — slide_type / layout vocabulary, placeholder
  // discipline, the four-layer flow, and the per-structure must-cover outlines —
  // now live in the agent system prompt (hermes_core
  // build_deliverable_planner_prompt), shared by the desk and gateway children.
  // Keep these quick-action prompts thin: intent + structure id + the dynamic
  // visual-master selection the system prompt cannot know at click time.
  const pptFlowReminder =
    "按系统提示中的“学生交付物四层流程”执行：读取材料 → material_index_build → 生成带 slide_type / notes / 证据占位的 Markdown 大纲 → review_outline 让我确认 → pptx_write 输出到 workspace 并返回路径。";
  const pptVisualMasterRule =
    `视觉母版：我已选择 ${selectedPptVisualMaster.name}。review_outline 通过后调用 pptx_write 时必须同时传入 template 和 visual_master，visual_master 使用 "${selectedPptVisualMaster.id}"。`;
  const paperToPptPrompt = buildPptPrompt([
    "请把我上传的论文、文献 PDF 或粘贴的论文内容转换成论文/文献汇报 PPT（structure=paper_report，template=paper_report）。",
    pptFlowReminder,
    pptVisualMasterRule,
  ]);
  const courseToPptPrompt = buildPptPrompt([
    "请把我提供的课程笔记、章节要点、学习材料或粘贴的内容转换成课程学习汇报 PPT（structure=course_report，template=course_report）。",
    pptFlowReminder,
    pptVisualMasterRule,
  ]);
  const codeToPptPrompt = buildPptPrompt([
    "请把我提供的代码项目或课设材料转换成课设答辩 PPT（structure=code_defense，template=code_defense）。",
    pptFlowReminder,
    pptVisualMasterRule,
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
