// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import {
  BookOpenText,
  Braces,
  Code2,
  FileSearch,
  FileText,
  FolderOpen,
  GraduationCap,
  Languages,
  Loader2,
  Palette,
  PanelRight,
  Rocket,
  RotateCcw,
  Sigma,
  SquareArrowOutUpRight,
} from "lucide-react";
import { useCallback, useEffect, useRef, useState, type CSSProperties, type ReactNode } from "react";
import { invoke } from "@tauri-apps/api/core";
import { useI18n } from "../lib/i18n";
import { cn } from "../lib/cn";
import { PPT_VISUAL_MASTERS, type PptVisualMaster } from "./pptx/visualMasters";

export type WorkspaceItem = {
  id: string;
  label: string;
  detail?: string;
  // True while this specific file is still being produced by the in-flight turn.
  pending?: boolean;
};

type WorkspacePanelProps = {
  className?: string;
  onCollapse: () => void;
  onStartPrompt?: (prompt: string) => void;
  goal?: string | null;
  materials: WorkspaceItem[];
  outputs: WorkspaceItem[];
  activeTool?: string | null;
  // True while a turn is in flight. Deliverable files may still be mid-write, so
  // their open/reveal/regenerate actions stay disabled until 小娜 finishes replying.
  busy?: boolean;
};

// PPT_VISUAL_MASTERS + PptVisualMaster now live in ./pptx/visualMasters (shared with the renderer).

// Target languages for formula→code. Mirrors OFFERED_LANGUAGES in
// hermes_core/tools/math_expression_tools.py (SymPy canonical core, then printer).
const MATH_TARGET_LANGUAGES = [
  { id: "python", label: "Python" },
  { id: "numpy", label: "NumPy" },
  { id: "javascript", label: "JavaScript" },
  { id: "octave", label: "MATLAB/Octave" },
  { id: "cpp17", label: "C++17" },
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

// File extension → short badge shown on a deliverable card.
function deliverableBadge(label: string): string | null {
  const ext = label.split(".").pop();
  if (!ext || ext === label) return null;
  return ext.toUpperCase();
}

// Keep only the latest version of each basename, most-recent first, so repeated
// regenerations (汇报.pptx v1/v2/…) collapse into one current card.
function latestDeliverables(outputs: WorkspaceItem[]): WorkspaceItem[] {
  const seen = new Set<string>();
  const result: WorkspaceItem[] = [];
  for (const item of [...outputs].reverse()) {
    const key = item.label.toLocaleLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    result.push(item);
  }
  return result;
}

function WorkspaceSectionHeading({ children, dotColor = "var(--kq-color-primary-dark)" }: { children: ReactNode; dotColor?: string }) {
  return (
    <h3 className="workspace-section-heading kq-section-heading inline-flex items-center gap-1.5 px-0 py-0 text-[12.5px] font-bold leading-snug tracking-normal">
      <span
        className="inline-block h-1.5 w-1.5 shrink-0 rounded-full"
        style={{ background: dotColor }}
      />
      {children}
    </h3>
  );
}

function WorkspaceSection({ sectionId, title, dotColor, children }: {
  sectionId: string;
  title: string;
  dotColor?: string;
  children?: ReactNode;
}) {
  return (
    <section data-workspace-section={sectionId} className="kq-workspace-card">
      <WorkspaceSectionHeading dotColor={dotColor}>{title}</WorkspaceSectionHeading>
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
      className="kq-quick-action justify-start rounded-[10px] px-2.5 py-2 text-left text-[13px] leading-snug transition"
    >
      {icon}
      {label}
    </button>
  );
}

function DeliverableCard({
  item,
  labels,
  disabled,
  onOpen,
  onReveal,
  onRegenerate,
}: {
  item: WorkspaceItem;
  labels: { open: string; reveal: string; regenerate: string; pending: string };
  disabled: boolean;
  onOpen: (path: string) => void;
  onReveal: (path: string) => void;
  onRegenerate: (item: WorkspaceItem) => void;
}) {
  const path = item.detail ?? item.label;
  const badge = deliverableBadge(item.label);
  return (
    <div className="kq-deliverable-card min-w-0">
      <div className="flex min-w-0 items-center gap-2">
        <FileText className="kq-color-icon-book h-4 w-4 shrink-0" aria-hidden />
        <span className="min-w-0 flex-1 truncate text-[13px] font-medium text-[var(--kq-color-strong)]" title={path}>
          {item.label}
        </span>
        {badge ? <span className="kq-deliverable-badge shrink-0">{badge}</span> : null}
      </div>
      <div className="mt-2 flex items-center gap-1">
        <button
          type="button"
          className="kq-deliverable-action"
          onClick={() => onOpen(path)}
          disabled={disabled}
          title={disabled ? labels.pending : labels.open}
        >
          <SquareArrowOutUpRight className="h-3.5 w-3.5" aria-hidden />
          {labels.open}
        </button>
        <button
          type="button"
          className="kq-deliverable-action ml-auto"
          onClick={() => onReveal(path)}
          disabled={disabled}
          title={disabled ? labels.pending : labels.reveal}
          aria-label={labels.reveal}
        >
          <FolderOpen className="h-3.5 w-3.5" aria-hidden />
        </button>
        <button
          type="button"
          className="kq-deliverable-action"
          onClick={() => onRegenerate(item)}
          disabled={disabled}
          title={disabled ? labels.pending : labels.regenerate}
          aria-label={labels.regenerate}
        >
          <RotateCcw className="h-3.5 w-3.5" aria-hidden />
        </button>
      </div>
    </div>
  );
}

function PptVisualMasterPreview({ master }: { master: PptVisualMaster }) {
  const [showPopover, setShowPopover] = useState(false);
  const [popoverPos, setPopoverPos] = useState<{ top: number; right: number } | null>(null);
  const cardRef = useRef<HTMLDivElement>(null);

  const updatePos = useCallback(() => {
    if (!cardRef.current) return;
    const rect = cardRef.current.getBoundingClientRect();
    // Position popover above the card, aligned to its right edge
    setPopoverPos({
      top: rect.top - 8,
      right: window.innerWidth - rect.right,
    });
  }, []);

  const handleEnter = useCallback(() => {
    updatePos();
    setShowPopover(true);
  }, [updatePos]);

  return (
    <div
      ref={cardRef}
      className="relative"
      onMouseEnter={handleEnter}
      onMouseLeave={() => setShowPopover(false)}
    >
      <div
        className={cn("kq-ppt-master-preview cursor-pointer", `kq-ppt-master-preview--${master.id}`)}
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
      {/* Hover popover — fixed to viewport, floats above all panels */}
      {showPopover && popoverPos && (
        <div
          className="fixed z-[200] w-[280px] overflow-hidden rounded-xl border border-[var(--kq-glass-border)] bg-white/96 p-2.5 shadow-xl backdrop-blur-sm dark:bg-zinc-900/96"
          style={{
            top: popoverPos.top,
            right: popoverPos.right,
            transform: "translateY(-100%)",
            boxShadow: "0 12px 40px rgba(90,74,106,0.18)",
          }}
          onMouseEnter={() => setShowPopover(true)}
          onMouseLeave={() => setShowPopover(false)}
        >
          <div className="mb-2 flex items-center gap-2">
            <span className="text-sm font-semibold text-[var(--kq-color-strong)]">{master.name}</span>
            <span className="text-xs text-[var(--kq-color-muted)]">{master.note}</span>
          </div>
          {/* Enlarged slide preview */}
          <div className="mb-2" style={pptMasterPreviewStyle(master)}>
            <div
              className={cn("kq-ppt-master-slide", `kq-ppt-master-preview--${master.id}`)}
              style={{ aspectRatio: "16/10", width: "100%", height: "auto" }}
            >
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
          </div>
          {/* Color swatches */}
          <div className="flex items-center gap-1.5">
            {master.palette.swatches.map((color) => (
              <div
                key={color}
                className="h-4 w-4 rounded-full border border-black/10"
                style={{ background: color }}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export function WorkspacePanel({
  className,
  onCollapse,
  onStartPrompt,
  goal,
  materials,
  outputs,
  activeTool,
  busy = false,
}: WorkspacePanelProps) {
  const { t } = useI18n();
  // The right rail is one surface with two modes: ACADEMY (the launchpad of
  // capabilities) and WORK (this session's goal / materials / deliverables).
  // Start on ACADEMY; morph to WORK the first time a deliverable appears.
  const [mode, setMode] = useState<"academy" | "work">(outputs.length > 0 ? "work" : "academy");
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

  const deliverables = latestDeliverables(outputs);
  const trimmedGoal = goal?.trim() || null;
  const showContext = Boolean(trimmedGoal) || materials.length > 0 || Boolean(activeTool);

  // Reveal WORK automatically the moment the first deliverable lands, without
  // overriding a later manual switch back to ACADEMY.
  const hadDeliverables = useRef(deliverables.length > 0);
  useEffect(() => {
    const has = deliverables.length > 0;
    if (has && !hadDeliverables.current) setMode("work");
    hadDeliverables.current = has;
  }, [deliverables.length]);

  const deliverableLabels = {
    open: t("chat.workspaceOpenFile"),
    reveal: t("chat.workspaceRevealFile"),
    regenerate: t("chat.workspaceRegenerate"),
    pending: t("chat.workspaceDeliverablePending"),
  };

  const openDeliverable = (path: string) => {
    void invoke("cmd_open_path", { path }).catch(() => undefined);
  };
  const revealDeliverable = (path: string) => {
    void invoke("cmd_reveal_path", { path }).catch(() => undefined);
  };
  const regenerateDeliverable = (item: WorkspaceItem) => {
    onStartPrompt?.(
      `请基于之前的材料和要求重新生成《${item.label}》。如果它是 PPT，请沿用我当前选择的视觉母版 ${selectedPptVisualMaster.name}（visual_master="${selectedPptVisualMaster.id}"），并按系统提示中的“学生交付物四层流程”重新走一遍 review_outline → 写文件，最后返回新的文件路径。`,
    );
  };

  return (
    <aside
      className={cn(
        "kq-workspace-panel flex w-[264px] shrink-0 flex-col border-l",
        className,
      )}
    >
      <div className="flex h-11 items-center justify-between gap-2 border-b border-[var(--kq-glass-border)] px-2.5">
        <div className="kq-workspace-tabs inline-flex p-0.5" role="tablist">
          <button
            type="button"
            role="tab"
            aria-selected={mode === "work"}
            className={cn("kq-workspace-tab", mode === "work" && "is-active")}
            onClick={() => setMode("work")}
          >
            {t("chat.workspaceModeWork")}
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={mode === "academy"}
            className={cn("kq-workspace-tab", mode === "academy" && "is-active")}
            onClick={() => setMode("academy")}
          >
            {t("chat.workspaceTitle")}
          </button>
        </div>
        <button
          type="button"
          onClick={onCollapse}
          className="kq-soft-icon-btn inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-md transition"
          aria-label={t("chat.workspaceCollapse")}
          title={t("chat.workspaceCollapse")}
        >
          <PanelRight className="h-4 w-4" aria-hidden />
        </button>
      </div>

      <div className="min-h-0 flex-1 space-y-3.5 overflow-y-auto overflow-x-hidden px-3 py-3.5">
        {mode === "work" ? (
        <>
        {showContext ? (
          <WorkspaceSection sectionId="workspace.context" title={t("chat.workspaceContext")}>
            <div className="mt-3 grid grid-cols-1 gap-2.5">
              {activeTool ? (
                <div className="kq-workspace-active inline-flex items-center gap-1.5 self-start rounded-full px-2.5 py-1 text-[12px] font-medium">
                  <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden />
                  {t("chat.workspaceGenerating")}
                </div>
              ) : null}
              {trimmedGoal ? (
                <p className="kq-workspace-body line-clamp-2 break-words text-[13px] leading-snug" title={trimmedGoal}>
                  {trimmedGoal}
                </p>
              ) : null}
              {materials.length > 0 ? (
                <div className="grid grid-cols-1 gap-1.5">
                  <span className="text-[11px] font-semibold uppercase tracking-wide text-[var(--kq-color-muted)]">
                    {t("chat.workspaceMaterials")}
                  </span>
                  <div className="flex flex-wrap gap-1.5">
                    {materials.map((item) => (
                      <span key={item.id} className="kq-material-chip max-w-full min-w-0 truncate" title={item.detail ?? item.label}>
                        {item.label}
                      </span>
                    ))}
                  </div>
                </div>
              ) : null}
            </div>
          </WorkspaceSection>
        ) : null}

        {deliverables.length > 0 ? (
          <WorkspaceSection sectionId="workspace.deliverables" title={t("chat.workspaceDeliverables")}>
            <div className="mt-3 grid grid-cols-1 gap-2">
              {busy && deliverables.some((item) => item.pending) ? (
                <p className="text-[12px] leading-snug text-[var(--kq-color-muted)]">
                  {t("chat.workspaceDeliverablePending")}
                </p>
              ) : null}
              {deliverables.map((item) => (
                <DeliverableCard
                  key={item.id}
                  item={item}
                  labels={deliverableLabels}
                  disabled={busy && Boolean(item.pending)}
                  onOpen={openDeliverable}
                  onReveal={revealDeliverable}
                  onRegenerate={regenerateDeliverable}
                />
              ))}
            </div>
          </WorkspaceSection>
        ) : (
          <WorkspaceSection sectionId="workspace.deliverables" title={t("chat.workspaceDeliverables")}>
            <div className="mt-3">
              <p className="text-[12.5px] leading-[1.55] text-[var(--kq-color-muted)]">
                {t("chat.workspaceWorkEmpty")}
              </p>
              <button
                type="button"
                onClick={() => setMode("academy")}
                className="kq-quick-action mt-3 flex w-full items-center gap-2 rounded-[10px] px-2.5 py-2 text-left text-[12.5px] leading-snug transition"
              >
                <Rocket className="h-3.5 w-3.5 shrink-0" style={{ color: "var(--kq-color-primary-dark)" }} aria-hidden />
                {t("chat.workspaceWorkEmptyCta")}
              </button>
            </div>
          </WorkspaceSection>
        )}
        </>
        ) : (
        <>
        <WorkspaceSection sectionId="workspace.reportPpt" title={t("chat.workspaceReportPpt")} dotColor="var(--kq-color-primary-dark)">
          <div className="mt-3 grid grid-cols-1 gap-2">
            <WorkspaceActionButton
              onClick={() => onStartPrompt?.(paperToPptPrompt)}
              icon={<BookOpenText className="kq-color-icon-book mr-2 inline h-4 w-4" aria-hidden />}
              label={t("chat.workspacePaperToPpt")}
            />
            <WorkspaceActionButton
              onClick={() => onStartPrompt?.(courseToPptPrompt)}
              icon={<GraduationCap className="kq-color-icon-course mr-2 inline h-4 w-4" aria-hidden />}
              label={t("chat.workspaceCourseToPpt")}
            />
            <WorkspaceActionButton
              onClick={() => onStartPrompt?.(codeToPptPrompt)}
              icon={<Code2 className="kq-color-icon-pen mr-2 inline h-4 w-4" aria-hidden />}
              label={t("chat.workspaceCodeToPpt")}
            />
            <label className="kq-workspace-body grid grid-cols-1 gap-1.5 text-[13px] leading-snug">
              <span className="inline-flex items-center gap-1.5 font-medium">
                <Palette className="h-3.5 w-3.5 text-[var(--kq-color-primary-dark)]" aria-hidden />
                {t("chat.workspacePptVisualMaster")}
              </span>
              <select
                value={pptVisualMaster}
                onChange={(event) => setPptVisualMaster(event.currentTarget.value as typeof pptVisualMaster)}
                className="kq-workspace-select rounded-md px-2 py-1.5 text-sm transition"
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

        <WorkspaceSection sectionId="workspace.mathAbility" title={t("chat.workspaceMathAbility")} dotColor="#4466cc">
          <div className="mt-3 grid grid-cols-1 gap-2">
            <label className="kq-workspace-body grid grid-cols-1 gap-1.5 text-[13px] leading-snug">
              <span className="inline-flex items-center gap-1.5 font-medium">
                <Languages className="h-3.5 w-3.5 text-[var(--kq-color-primary-dark)]" aria-hidden />
                {t("chat.workspaceMathLanguage")}
              </span>
              <select
                value={mathLanguage}
                onChange={(event) => setMathLanguage(event.currentTarget.value as MathLanguageId)}
                className="kq-workspace-select rounded-md px-2 py-1.5 text-sm transition"
              >
                {MATH_TARGET_LANGUAGES.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.label}
                  </option>
                ))}
              </select>
            </label>
            <WorkspaceActionButton
              onClick={() => onStartPrompt?.(formulaToCodePrompt)}
              icon={<Braces className="kq-color-icon-course mr-2 inline h-4 w-4" aria-hidden />}
              label={t("chat.workspaceFormulaToCode")}
            />
            <WorkspaceActionButton
              onClick={() => onStartPrompt?.(codeToFormulaPrompt)}
              icon={<Sigma className="kq-color-icon-pen mr-2 inline h-4 w-4" aria-hidden />}
              label={t("chat.workspaceCodeToFormula")}
            />
            <WorkspaceActionButton
              onClick={() => onStartPrompt?.(mathFormulaExtractPrompt)}
              icon={<FileSearch className="kq-color-icon-download mr-2 inline h-4 w-4" aria-hidden />}
              label={t("chat.workspaceMathFormulaExtract")}
            />
          </div>
        </WorkspaceSection>
        </>
        )}
      </div>
    </aside>
  );
}
