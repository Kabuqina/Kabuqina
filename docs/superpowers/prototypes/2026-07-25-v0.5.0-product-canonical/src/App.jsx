import { useEffect, useMemo, useRef, useState } from "react";
import {
  Activity,
  AlertCircle,
  ArrowLeft,
  ArrowRight,
  BookOpen,
  Bookmark,
  Check,
  CheckCircle2,
  Circle,
  Clock3,
  Coffee,
  FileText,
  FolderOpen,
  FolderPlus,
  GraduationCap,
  Inbox,
  LampDesk,
  Layers3,
  MessageCircle,
  PencilLine,
  Plus,
  RotateCcw,
  Send,
  Settings,
  ShieldCheck,
  Sparkles,
  X,
} from "lucide-react";

const JOURNEYS = [
  { id: "J1", label: "首次建课", detail: "第一次进入 → 开新本 → 开始学习" },
  { id: "J2", label: "学习问小娜", detail: "Study → 课程 Chat → 精确返回" },
  { id: "J3", label: "保存到课程", detail: "Chat → 待审核草稿 → Study" },
  { id: "J4", label: "Studio 取材", detail: "Studio → 从 Study 选素材 → 来源快照" },
  { id: "J5", label: "恢复现场", detail: "Study + Studio → 重启 → 安全恢复" },
];

const COURSE = {
  id: "calculus",
  title: "高等数学",
  subtitle: "极限与连续",
  savedAt: "今天 13:42",
};

const COURSE_BOOKS = [
  { id: "calculus", title: "高等数学" },
  { id: "physics", title: "大学物理" },
  { id: "scratch", title: "杂记本", kind: "scratch" },
];

// 杂记本＝留白：不催、不计数、不安排；归本是安静的可选动作
// 后端契约（2026-07-04-study-m2-course-space-flashcards.md）只认这四个值，
// 无效值保守回落为 again——所以界面文案绝不能直接当评分提交。
// hard 不再由界面产出：那一档正是被去掉的不可靠自评，改由翻面耗时实测替代。
const RECALL_GRADES = {
  recalled: "good",
  forgot: "again",
  tooEasy: "easy",
};

const GRADE_LABELS = {
  good: "想起来了",
  again: "没想起来",
  easy: "太简单",
};

// 材料真值。origin 决定可信度来源怎么标：
// imported = 学生自己导入的（默认路径）；builtin = 产品自带的示例课程（样板，不是内容服务）
const MATERIALS = {
  "textbook-2-3": {
    id: "textbook-2-3",
    title: "教材 §2.3",
    subtitle: "极限的运算法则",
    origin: "imported",
    from: "高等数学教材.pdf · 第 23 页",
    body: [
      "若 lim f(x) 与 lim g(x) 都存在，则和、差、积的极限等于极限的和、差、积；当分母极限不为 0 时，商的极限等于极限的商。",
      "注意最后一条的前提。若分子与分母的极限同时为 0，运算法则不适用——此时把式子记作 0/0，称为未定式。",
      "未定式不是一个数值结果，而是一个信号：它说明还需要继续分析。常见的办法是先约去公因子，再求极限。",
    ],
  },
  "workbook-41": {
    id: "workbook-41",
    title: "习题集 p.41",
    subtitle: "未定式练习 6 题",
    origin: "imported",
    from: "习题集.pdf · 第 41 页",
    body: [
      "1. 求 lim (x² − 1) / (x − 1)，x → 1。",
      "2. 求 lim (√x − 2) / (x − 4)，x → 4。",
      "3. 判断：得到 0/0 就说明极限不存在。这句话对吗？为什么？",
    ],
  },
  "practice-feedback": {
    id: "practice-feedback",
    title: "当前练习与反馈",
    subtitle: "练习 3 · 第 2 步",
    origin: "imported",
    from: "高等数学 · 我写的答案与页边批注",
    body: [
      "我的答案：代入后分子和分母同时为 0，所以需要先变形。",
      "页边批注：已说清分子分母都趋近 0；还差这句——0/0 是未定式，不是极限值。",
    ],
  },
};

// Planner 层：一张卡＝我要说的一件事，素材作为依据挂在它下面。
// 小娜拟的以铅笔出现，落墨后才进入顺序——内容她做，项目你参与。
const INITIAL_POINTS = [
  { id: "p1", say: "直接代入会得到 0/0", backing: "教材 §2.3", state: "ink" },
  { id: "p2", say: "0/0 不是一个数，是“还要继续分析”的信号", backing: "教材 §2.3", state: "ink" },
  { id: "p3", say: "所以要先化简，再求极限", backing: null, state: "pencil" },
  { id: "p4", say: "用可约因子的例子走一遍", backing: "教材 §2.3 例题", state: "pencil" },
];

const INITIAL_SCRATCH_NOTES = [
  {
    id: "s1",
    text: "读到一句：数学里的等号，是在说两个不同的写法，指的是同一个东西。",
    // 来源行统一为「来源 · 时间」
    meta: "来自对话 · 昨天",
  },
];

const STUDY_PAGES = [
  { id: "flyleaf", label: "扉页" },
  { id: "plan", label: "计划" },
  { id: "learn", label: "学习" },
  { id: "practice", label: "练习" },
  { id: "evaluate", label: "评估" },
];

// 目录来自教材自己的章节结构（小娜整理，非凭空生成），因此有出处。
// 状态只反映"留下过什么重构痕迹"，绝不显示覆盖率——覆盖率会把"学过多少"伪装成"学会多少"。
const COURSE_OUTLINE = [
  { no: "2.1", title: "数列的极限", state: "practiced" },
  { no: "2.2", title: "函数的极限", state: "practiced" },
  { no: "2.3", title: "极限的运算法则", state: "current", material: "textbook-2-3" },
  { no: "2.4", title: "无穷小与无穷大", state: "none" },
  { no: "2.5", title: "函数的连续性", state: "none" },
];

const OUTLINE_STATE_LABEL = {
  practiced: "练过",
  wrong: "有错题",
  current: "在学",
  none: "",
};

const INITIAL_PLAN_ITEMS = [
  { id: "p1", title: "理解极限与未定式的区别", meta: "本周 · 当前阶段", status: "active" },
  { id: "p2", title: "完成极限基础练习 1–6", meta: "4 / 6 已完成", status: "active" },
  { id: "p3", title: "整理一次错题回练", meta: "等待练习证据", status: "pending" },
];

const INITIAL_ANSWER = "代入后分子和分母同时为 0，所以需要先变形。";

// 学习页的一步 = 一个知识核 + 一次学习者自己的重构 + 一次对照
const LEARN_SEED = {
  index: "01",
  source: "教材 §2.3",
  core: "0/0 是未定式，不是一个确定的数。",
  prompt: "为什么代入得到 0/0，还不能算求出了极限？",
  reference:
    "直接代入只说明原式还需要继续分析。不同函数都可能得到 0/0，但它们的极限可以不同，所以还要继续化简，或者换一种分析方法。",
  contrastHint: "对照看看：你的说法里，点出“不同函数都可能得到 0/0，结果却不同”了吗？",
};

const GENERAL_MESSAGES = [
  {
    role: "user",
    text: "帮我把今天学到的“未定式”整理成一段便于复习的话。",
  },
  {
    role: "assistant",
    text: "可以。先抓住一个边界：0/0 不是一个数，也不是极限答案；它只是在提醒我们，直接代入还不足以判断结果，需要继续化简或换一种分析方法。",
    canSave: true,
  },
];

const COURSE_MESSAGES = [
  {
    role: "user",
    text: "我知道代入后是 0/0，但不知道为什么这还不是答案。",
  },
  {
    role: "assistant",
    text: "你已经找到卡点了。先只补一句：数学里“0/0”不是一个确定的数，而是在提醒我们还要继续分析。试着把“未定式”这个词放进你的原句里。",
    meta: "一级提示 · 只给下一步",
  },
];

const STUDIO_MESSAGES = [
  {
    role: "user",
    text: "我想把这组关于 0/0 未定式的材料讲给没有学过极限的同学，应该先确定什么？",
  },
  {
    role: "assistant",
    text: "先不要决定做成 PPT 还是文章。先写清楚受众、希望对方听完后理解什么，以及这次必须引用哪些来源；表达形式可以在项目结构稳定后再选。",
    meta: "Studio 协作 · 先澄清表达目标",
  },
];

const PLAN_MESSAGES = [
  {
    role: "user",
    text: "周末我有两个小时，想把这周学过的内容简单过一遍。",
  },
  {
    role: "assistant",
    text: "可以先按“回想—核对—补缺”分成三段：先不看材料写下记得的内容，再用笔记核对，最后只处理最不确定的两处。",
  },
];

const CHAT_SESSIONS = [
  {
    id: "general-study",
    kind: "general",
    title: "整理今天的学习",
    meta: "今天 14:06",
  },
  {
    id: "course-limit",
    kind: "course",
    title: "高等数学 · 练习 3",
    meta: "今天 13:58",
    origin: "Study",
  },
  {
    id: "studio-limit",
    kind: "studio",
    title: "极限概念分享",
    meta: "昨天",
    origin: "Studio",
  },
  {
    id: "general-plan",
    kind: "general",
    title: "周末复习安排",
    meta: "昨天",
  },
];

function AppIcon({ icon: Icon, size = 18, strokeWidth = 2 }) {
  return <Icon aria-hidden="true" size={size} strokeWidth={strokeWidth} />;
}

function StatusPill({ tone = "neutral", children }) {
  return <span className={`status-pill status-pill--${tone}`}>{children}</span>;
}

function PrototypeRail({ activeJourney, onSelect, productStatus }) {
  return (
    <section className="prototype-rail" aria-label="原型旅程控制">
      <div className="prototype-rail__title">
        <div>
          <strong>Kabuqina v0.5.0 · 全产品 Canonical 原型</strong>
          <span>PRODUCT FLOW · J1–J5 · 2026-07-25</span>
        </div>
        <StatusPill tone="prototype">交互模拟，不代表后端已发布</StatusPill>
      </div>
      <div className="prototype-journeys">
        {JOURNEYS.map((journey) => (
          <button
            key={journey.id}
            className={activeJourney === journey.id ? "is-active" : ""}
            onClick={() => onSelect(journey.id)}
            type="button"
          >
            <span>{journey.id}</span>
            <strong>{journey.label}</strong>
            <small>{journey.detail}</small>
          </button>
        ))}
      </div>
      <p className="prototype-status" aria-live="polite">
        <CheckCircle2 size={15} aria-hidden="true" />
        {productStatus}
      </p>
    </section>
  );
}

function AppHeader({
  surface,
  onSurface,
  onOpenActivity,
  onOpenSettings,
  activityCount,
  theme,
  onToggleTheme,
}) {
  return (
    <header className="app-header">
      <button className="brand-lockup" type="button" onClick={() => onSurface("study")}>
        <span className="brand-mark">K</span>
        <span>Kabuqina</span>
      </button>
      <nav className="primary-nav" aria-label="一级目的地">
        <button
          type="button"
          aria-current={surface === "study" ? "page" : undefined}
          onClick={() => onSurface("study")}
        >
          <AppIcon icon={BookOpen} />
          Study
        </button>
        <button
          type="button"
          aria-current={surface === "studio" ? "page" : undefined}
          onClick={() => onSurface("studio")}
        >
          <AppIcon icon={FolderOpen} />
          Studio
        </button>
      </nav>
      <div className="utility-nav">
        <button
          type="button"
          aria-current={surface === "chat" ? "page" : undefined}
          onClick={() => onSurface("chat")}
        >
          <AppIcon icon={MessageCircle} />
          <span>Chat</span>
        </button>
        <button type="button" onClick={onOpenActivity}>
          <AppIcon icon={Activity} />
          <span>Activity</span>
          {activityCount > 0 && <b>{activityCount}</b>}
        </button>
        <button
          type="button"
          className={`lamp-toggle ${theme === "dark" ? "is-on" : ""}`}
          aria-label={theme === "dark" ? "台灯已开，切换回白天" : "开台灯，进入夜晚"}
          aria-pressed={theme === "dark"}
          onClick={onToggleTheme}
        >
          <AppIcon icon={LampDesk} size={21} />
        </button>
        <button type="button" aria-label="设置" onClick={onOpenSettings}>
          <AppIcon icon={Settings} size={21} />
        </button>
      </div>
    </header>
  );
}

function BookPill({ book, active, onSelect }) {
  return (
    <button
      className={`nb-pill ${book.kind === "scratch" ? "nb-pill--scratch" : ""}`}
      type="button"
      aria-current={active ? "page" : undefined}
      onClick={() => onSelect(book)}
    >
      <span className="spine" aria-hidden="true" />
      {book.title}
    </button>
  );
}

// 书立：课程名长在本子的标签上，换课＝换一本本子。
// 杂记本不是课程，所以离开课程那一组，单独待在最右边。
function Bookend({ hasCourse, activeCourse, onSelectCourse, onCreateCourse }) {
  const scratch = COURSE_BOOKS.find((book) => book.kind === "scratch");
  return (
    <nav className="bookend" aria-label="课程本">
      {hasCourse &&
        COURSE_BOOKS.filter((book) => book.kind !== "scratch").map((book) => (
          <BookPill
            key={book.id}
            book={book}
            active={book.id === activeCourse}
            onSelect={onSelectCourse}
          />
        ))}
      <button className="nb-pill nb-pill--new" type="button" onClick={onCreateCourse}>
        <AppIcon icon={Plus} size={14} />
        开新本
      </button>
      {hasCourse && (
        <BookPill
          book={scratch}
          active={scratch.id === activeCourse}
          onSelect={onSelectCourse}
        />
      )}
    </nav>
  );
}

function FlyleafPage({ draftVisible, onInk, onErase }) {
  return (
    <div className="lifecycle-page lifecycle-page--flyleaf">
      {draftVisible && (
        <section className="study-sheet study-sheet--pencil">
          <header>
            <span>
              <PencilLine aria-hidden="true" />
              小娜拟的
            </span>
          </header>
          <dl className="flyleaf-rows">
            <div><dt>目标</dt><dd>能解释极限的核心概念，并独立完成基础题。</dd></div>
            <div><dt>偏好</dt><dd>先看一个直观例子，再自己动手推导。</dd></div>
            <div><dt>时间</dt><dd>工作日每天 45 分钟，不用一次学完。</dd></div>
          </dl>
          <div className="inline-actions">
            <button className="primary-action" type="button" onClick={onInk}>
              <AppIcon icon={Check} />
              就按这个来
            </button>
            <button type="button" onClick={onErase}>不用这个</button>
          </div>
        </section>
      )}
      {/* 上下两块用同一组字段，否则会让人以为确认之后字段会变。
          当前阶段属于计划页，下一调整属于评估页，都不放在扉页。 */}
      <section className="study-sheet study-sheet--ink">
        <header>
          <span>
            <BookOpen aria-hidden="true" />
            我确认过的
          </span>
        </header>
        <dl className="flyleaf-rows">
          <div><dt>目标</dt><dd>理解极限、导数与积分，完成本学期练习。</dd></div>
          <div><dt>偏好</dt><dd>先看例子，再自己推一遍。</dd></div>
          <div><dt>时间</dt><dd>工作日每天 30 分钟。</dd></div>
        </dl>
      </section>
    </div>
  );
}

function PlanPage({ items, onUpdate, onOpenMaterial }) {
  return (
    <div className="lifecycle-page lifecycle-page--plan">
      {/* 计划依据目录来做，所以计划长在目录里当前这一节下面，不是另起一块 */}
      <section className="course-outline">
        <header>
          <span>
            <Layers3 aria-hidden="true" />
            教材目录
          </span>
          <small>小娜从《高等数学教材.pdf》整理</small>
        </header>
        {COURSE_OUTLINE.map((section) => {
          const isCurrent = section.state === "current";
          return (
            <article className="outline-section" key={section.no} data-state={section.state}>
              {/* 有材料才做成按钮——不做"看着能点却点不动"的行。
                  生产里目录抽自教材，每节都对应页码，因此每节都可点。 */}
              {section.material ? (
                <button
                  className="outline-row"
                  type="button"
                  aria-current={isCurrent ? "true" : undefined}
                  onClick={() => onOpenMaterial(section.material)}
                >
                  <span className="outline-no">{section.no}</span>
                  <strong>{section.title}</strong>
                  <small>{OUTLINE_STATE_LABEL[section.state]}</small>
                </button>
              ) : (
                <div className="outline-row outline-row--flat">
                  <span className="outline-no">{section.no}</span>
                  <strong>{section.title}</strong>
                  <small>{OUTLINE_STATE_LABEL[section.state]}</small>
                </div>
              )}

              {isCurrent && (
                <div className="plan-list">
                  {items.map((item) => (
                    <article key={item.id} data-status={item.status}>
                      <span className="plan-state">
                        {item.status === "done" ? (
                          <Check aria-hidden="true" />
                        ) : (
                          <Circle aria-hidden="true" />
                        )}
                      </span>
                      <div>
                        <strong>{item.title}</strong>
                        <small>
                          {item.status === "skipped" ? "已调整 · 不计为完成" : item.meta}
                        </small>
                      </div>
                      {item.status === "active" || item.status === "pending" ? (
                        <div className="plan-actions">
                          <button type="button" onClick={() => onUpdate(item.id, "done")}>
                            完成
                          </button>
                          <button type="button" onClick={() => onUpdate(item.id, "skipped")}>
                            跳过
                          </button>
                        </div>
                      ) : (
                        <StatusPill tone={item.status === "done" ? "success" : "prototype"}>
                          {item.status === "done" ? "已完成" : "已跳过"}
                        </StatusPill>
                      )}
                    </article>
                  ))}
                </div>
              )}
            </article>
          );
        })}
      </section>
    </div>
  );
}

function LearnPage({
  step,
  draft,
  onDraft,
  onContrast,
  onReveal,
  onRewrite,
  onContinue,
  draftSaved,
  onOpenDraft,
}) {
  const wrote = draft.trim().length > 0;
  return (
    <div className="lifecycle-page lifecycle-page--learn">
      <section className="learn-concept">
        <span className="concept-index">{LEARN_SEED.index}</span>
        <div>
          <span className="eyebrow">这一步要弄懂的 · {LEARN_SEED.source}</span>
          <h3>{LEARN_SEED.core}</h3>
        </div>
      </section>

      {step === "contrast" ? (
        <>
          {/* 这一页的主角就是这两块，所以都给足分量；我的想法为空就留空，不补提示 */}
          <div className="contrast-pair">
            <section className="study-sheet">
              <header>
                <span>
                  <FileText aria-hidden="true" />
                  {LEARN_SEED.source} 的说法
                </span>
              </header>
              <p className="reference-words">{LEARN_SEED.reference}</p>
            </section>
            <section className="study-sheet study-sheet--ink">
              <header>
                <span>
                  <PencilLine aria-hidden="true" />
                  我的想法
                </span>
              </header>
              {wrote && <p className="own-words">{draft}</p>}
            </section>
          </div>
          <aside className="margin-note">
            <Coffee aria-hidden="true" />
            <div>
              <strong>这里只对照，不判分</strong>
              <p>{LEARN_SEED.contrastHint}</p>
            </div>
          </aside>
          <div className="inline-actions">
            <button className="primary-action" type="button" onClick={onRewrite}>
              <AppIcon icon={PencilLine} />
              {wrote ? "补一句我的想法" : "写下我的想法"}
            </button>
            <button type="button" onClick={onContinue}>
              去练习中验证
            </button>
          </div>
        </>
      ) : (
        <>
          <p className="reconstruct-prompt">{LEARN_SEED.prompt}</p>
          <label className="answer-field">
            <span>
              <strong>我的想法</strong>
              <small>随便写，不评分</small>
            </span>
            <textarea
              value={draft}
              onChange={(event) => onDraft(event.target.value)}
              placeholder="不用完整，写你现在想到的那一句就好…"
            />
          </label>
          <div className="inline-actions">
            <button
              className="primary-action"
              type="button"
              disabled={!wrote}
              onClick={onContrast}
            >
              和教材对一下
              <AppIcon icon={ArrowRight} />
            </button>
            <button type="button" onClick={onReveal}>
              先看教材的说法
            </button>
          </div>
        </>
      )}

      {draftSaved && (
        <button className="draft-row" type="button" onClick={onOpenDraft}>
          <span>
            <strong>“0/0 未定式”辅导笔记</strong>
            <small>等你过目 · 还没进课程</small>
          </span>
          <StatusPill tone="warning">草稿</StatusPill>
        </button>
      )}

      <button className="material-call" type="button">
        <AppIcon icon={Layers3} size={15} />
        需要时翻材料：教材 §2.3 · 例题三则
      </button>
    </div>
  );
}

function EvaluatePage({ onRetry }) {
  return (
    <div className="lifecycle-page lifecycle-page--evaluate">
      <div className="evaluation-summary">
        <section>
          <span>最近评估</span>
          <strong>基础概念基本达标</strong>
          <p>来自 6 次练习和 1 次复习</p>
        </section>
        <section>
          <span>建议下一步</span>
          <strong>继续练习“解释理由”</strong>
          <p>先修正未定式的表述</p>
        </section>
      </div>
      <section className="study-sheet">
        <header>
          <span><RotateCcw aria-hidden="true" />错题本</span>
          <StatusPill tone="warning">2 项待回访</StatusPill>
        </header>
        {/* 同一个列表里不给两种动作——用户看不出为什么这题能重做那题不能 */}
        <article className="wrongbook-row">
          <div>
            <strong>0/0 能不能直接作为极限值？</strong>
            <small>练习 3 · 今天</small>
          </div>
          <button className="primary-action" type="button" onClick={onRetry}>再做一次</button>
        </article>
        <article className="wrongbook-row">
          <div>
            <strong>什么时候可以先约分再求极限？</strong>
            <small>练习 2 · 昨天</small>
          </div>
          <button type="button" onClick={onRetry}>再做一次</button>
        </article>
      </section>
    </div>
  );
}

function StudyNotebook({
  hasCourse,
  studyState,
  studyPage,
  answer,
  onAnswer,
  onCreateCourse,
  onContinue,
  onNavigatePage,
  onAsk,
  onCheck,
  flyleafDraftVisible,
  onInkFlyleaf,
  onEraseFlyleaf,
  planItems,
  onUpdatePlan,
  draftSaved,
  onOpenDraft,
  onRetryWrongbook,
  onOpenBook,
  learnStep,
  learnDraft,
  onLearnDraft,
  onLearnContrast,
  onLearnReveal,
  onLearnRewrite,
}) {
  if (!hasCourse) {
    return (
      <section className="notebook notebook--welcome" aria-labelledby="welcome-title">
        <div className="notebook-cover-line" />
        <div className="welcome-copy">
          <span className="eyebrow">第一次来到书桌</span>
          <h1 id="welcome-title">先开一本课程本</h1>
          <p>
            课程本会把材料、计划、练习、笔记与学习证据放在同一个上下文里。普通对话不会被自动塞进课程。
          </p>
          <button className="primary-action" type="button" onClick={onCreateCourse}>
            <AppIcon icon={Plus} />
            开第一本课程本
          </button>
          <small>本地学习功能可用；需要模型的动作会明确提示配置。</small>
        </div>
      </section>
    );
  }

  const isPractice = studyPage === "practice";
  return (
    <section className="notebook" aria-label="当前课程笔记本">
      <header className="notebook-header">
        <div>
          <h1>{COURSE.subtitle}</h1>
          {/* 不给时间戳：它会引出"那之后我写的呢"，反而制造不安 */}
          <p>已自动保存</p>
        </div>
        {/* 书签的作用是回到"我在做的那件事"——事比编号重要，所以内容在主行 */}
        <button className="bookmark-card" type="button" onClick={onContinue}>
          <AppIcon icon={Bookmark} />
          <span>
            <strong>解释为什么不能直接代入</strong>
            <small>接着上次 · 练习 3</small>
          </span>
        </button>
      </header>
      <nav className="notebook-tabs" aria-label="笔记本分页">
        {STUDY_PAGES.map((tab) => (
          <button
            type="button"
            key={tab.id}
            aria-current={tab.id === studyPage ? "page" : undefined}
            onClick={() => onNavigatePage(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </nav>
      <article className="notebook-page">
        {studyPage === "flyleaf" && (
          <FlyleafPage
            draftVisible={flyleafDraftVisible}
            onInk={onInkFlyleaf}
            onErase={onEraseFlyleaf}
          />
        )}
        {studyPage === "plan" && (
          <PlanPage items={planItems} onUpdate={onUpdatePlan} onOpenMaterial={onOpenBook} />
        )}
        {studyPage === "learn" && (
          <LearnPage
            step={learnStep}
            draft={learnDraft}
            onDraft={onLearnDraft}
            onContrast={onLearnContrast}
            onReveal={onLearnReveal}
            onRewrite={onLearnRewrite}
            draftSaved={draftSaved}
            onOpenDraft={onOpenDraft}
            onContinue={onContinue}
          />
        )}
        {isPractice && (
          <div className="practice-sheet">
            <span className="eyebrow">练习 3 · 第 2 步</span>
            {/* 题目才是这一页的主角；原来那个大标题只是把题目换句话说了一遍 */}
            <h2 className="practice-question">
              计算 <span className="formula">lim (x² − 1) / (x − 1)，x → 1</span>
              。为什么不能把直接代入得到的 0/0 当作答案？
            </h2>
            <p className="completion-standard">
              <strong>完成标准：</strong>
              说清“得到 0/0”不等于“得到极限值”，并指出下一步。
            </p>
            {studyState === "returned" && (
              <aside className="margin-note">
                <Coffee aria-hidden="true" />
                <div>
                  <strong>小娜留在页边</strong>
                  <p>试试把“未定式”这个词，放进你原来那句话里。</p>
                </div>
              </aside>
            )}
            <label className="answer-field">
              <span>
                <strong>我的答案</strong>
              </span>
              <textarea value={answer} onChange={(event) => onAnswer(event.target.value)} />
            </label>
            <p className="save-status">
              <ShieldCheck size={16} aria-hidden="true" />
              {studyState === "returned" ? "回到原处，答案没被改动" : "草稿已保存"}
            </p>
            {studyState === "returned" ? (
              <section className="feedback-card" aria-label="检查结果">
                <header>
                  <strong>页边批注</strong>
                  <StatusPill tone="warning">还差一步</StatusPill>
                </header>
                <div className="feedback-grid">
                  <p>
                    <Check size={16} aria-hidden="true" />
                    <span>
                      <strong>已说清</strong>
                      代入后分子、分母都趋近 0。
                    </span>
                  </p>
                  <p>
                    <Circle size={16} aria-hidden="true" />
                    <span>
                      <strong>还差这句</strong>
                      0/0 是未定式，不是极限值。
                    </span>
                  </p>
                </div>
                <div className="inline-actions">
                  <button className="primary-action" type="button" onClick={onCheck}>
                    修改答案
                  </button>
                  <button type="button" onClick={onAsk}>
                    <AppIcon icon={Coffee} />
                    让小娜陪我补这一步
                  </button>
                </div>
              </section>
            ) : (
              <div className="inline-actions">
                <button className="primary-action" type="button" onClick={onCheck}>
                  检查这一步
                </button>
                <button type="button" onClick={onAsk}>
                  <AppIcon icon={Coffee} />
                  碰杯问小娜
                </button>
              </div>
            )}
          </div>
        )}
        {studyPage === "evaluate" && (
          <EvaluatePage onRetry={onRetryWrongbook} />
        )}
      </article>
    </section>
  );
}

function ReviewCards({
  hasCourse,
  isScratch,
  onReview,
  reviewDone,
  onAsk,
  onOpenBook,
  stackIndexOpen,
  onToggleStackIndex,
}) {
  return (
    <aside className="desk-rail desk-rail--review" aria-label="参考资料、复习与小娜">
      {/* 书堆：参考书立着（需要时抽一本），笔记本摊开着（天天写）。
          刻意不是一个可浏览的知识库空间。 */}
      {!isScratch && hasCourse && (
        <section className="book-stack">
          <h2>参考资料</h2>
          <div className="spines">
            <button className="book-spine" type="button" onClick={() => onOpenBook("textbook-2-3")}>
              教材 §2.3
            </button>
            <button className="book-spine" type="button" onClick={() => onOpenBook("workbook-41")}>
              习题集 p.41
            </button>
            <button
              className="book-spine book-spine--add"
              type="button"
              aria-label="放一本资料进来"
              title="放一本资料进来"
              onClick={() => onOpenBook(null)}
            >
              ＋
            </button>
          </div>
          {/* Learning Index 与 Studio 的 Material Index 同层，因此同样待遇：
              贴在书堆上的目录，可翻开核对，不占入口 */}
          <button className="stack-index" type="button" onClick={onToggleStackIndex}>
            <AppIcon icon={FileText} size={13} />
            小娜从这些书里读到的
          </button>
          {stackIndexOpen && (
            <ul className="stack-index-list">
              <li>极限的运算法则 <span>教材 §2.3</span></li>
              <li>可约因子的例题 <span>教材 §2.3</span></li>
              <li>未定式练习 6 题 <span>习题集 p.41</span></li>
            </ul>
          )}
        </section>
      )}
      {!isScratch && (
        <section className="desk-card review-card">
          <h2>
            <AppIcon icon={Inbox} />
            今天要复习
          </h2>
          <strong className="due-number">{reviewDone ? "5" : "6"}</strong>
          <p>张卡片 · 随时可以停</p>
          <button type="button" onClick={onReview} disabled={!hasCourse}>
            {reviewDone ? "接着复习" : "开始复习"}
          </button>
        </section>
      )}
      <button
        className="cup-anchor"
        type="button"
        aria-label="碰杯问小娜"
        onClick={onAsk}
        disabled={!hasCourse}
      >
        <span>
          <Coffee size={25} aria-hidden="true" />
        </span>
        <strong>碰杯问小娜</strong>
        <small>{hasCourse ? "安静陪着你" : "等你开第一本课程本"}</small>
      </button>
    </aside>
  );
}

// 材料摊开在旁边，不接管页面——与小娜聊天框是同一族"侧开"物件。
// 原始场景表已定：书只能作为局部呈现形态，不做主界面。
function MaterialPanel({
  material,
  mode,
  onClose,
  onNote,
  citeTargets,
  citeOpen,
  onStartCite,
  onCite,
  onOpenOriginal,
}) {
  const isCopy = mode === "studio";
  return (
    <aside className={`material-panel ${isCopy ? "material-panel--copy" : ""}`} aria-label="摊开的材料">
      <header>
        <div>
          <span className="eyebrow">
            {material.origin === "builtin" ? "产品自带的示例" : "你导入的"}
            {" · "}
            {material.from}
          </span>
          <h2>{material.title}</h2>
          <p>{material.subtitle}</p>
        </div>
        <button type="button" aria-label="放回去" onClick={onClose}>
          <AppIcon icon={X} size={18} />
        </button>
      </header>

      <div className="material-body">
        {material.body.map((paragraph, index) => (
          <p key={index}>{paragraph}</p>
        ))}
      </div>


      <footer className="material-foot">
        {isCopy ? (
          <>
            {citeOpen ? (
              <div className="cite-choice">
                <span>挂到哪一条？</span>
                {citeTargets.map((point) => (
                  <button type="button" key={point.id} onClick={() => onCite(point)}>
                    {point.say}
                  </button>
                ))}
              </div>
            ) : (
              <button className="primary-action" type="button" onClick={onStartCite}>
                作为某条的出处
              </button>
            )}
            <button className="material-original" type="button" onClick={onOpenOriginal}>
              去看原件
            </button>
          </>
        ) : (
          // 对一段材料唯一能做的事是把它转成自己的话——高亮收藏是反重构的
          <button className="primary-action" type="button" onClick={onNote}>
            <AppIcon icon={PencilLine} size={15} />
            用自己的话记下来
          </button>
        )}
      </footer>
    </aside>
  );
}

function ScratchNotebook({
  draft,
  onDraft,
  notes,
  filingId,
  onStartFiling,
  onCancelFiling,
  onFile,
}) {
  return (
    <section className="notebook notebook--scratch" aria-label="杂记本">
      <div className="scratch-page">
        <textarea
          className="scratch-pad"
          aria-label="随手写"
          value={draft}
          onChange={(event) => onDraft(event.target.value)}
          placeholder="随便写点什么…"
        />
        {notes.map((note) => (
          <article className="scratch-note" key={note.id}>
            <p>{note.text}</p>
            <div className="scratch-note__foot">
              <span>{note.meta}</span>
              {filingId === note.id ? (
                <span className="scratch-file-choice">
                  {COURSE_BOOKS.filter((book) => book.kind !== "scratch").map((book) => (
                    <button type="button" key={book.id} onClick={() => onFile(note, book)}>
                      {book.title}
                    </button>
                  ))}
                  <button type="button" onClick={onCancelFiling}>
                    算了
                  </button>
                </span>
              ) : (
                <button
                  className="scratch-file"
                  type="button"
                  onClick={() => onStartFiling(note.id)}
                >
                  放进课程本
                </button>
              )}
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

function StudyDesk(props) {
  const isScratch = props.activeBook === "scratch";
  return (
    <main className="desk-scene" data-testid="study-desk">
      <Bookend
        hasCourse={props.hasCourse}
        activeCourse={props.activeBook}
        onCreateCourse={props.onCreateCourse}
        onSelectCourse={props.onSelectBook}
      />
      {isScratch ? (
        <ScratchNotebook
          draft={props.scratchDraft}
          onDraft={props.onScratchDraft}
          notes={props.scratchNotes}
          filingId={props.filingId}
          onStartFiling={props.onStartFiling}
          onCancelFiling={props.onCancelFiling}
          onFile={props.onFileNote}
        />
      ) : (
        <StudyNotebook {...props} />
      )}
      <ReviewCards
        hasCourse={props.hasCourse}
        isScratch={isScratch}
        onReview={props.onReview}
        reviewDone={props.reviewDone}
        onAsk={props.onAsk}
        onOpenBook={props.onOpenBook}
        stackIndexOpen={props.stackIndexOpen}
        onToggleStackIndex={props.onToggleStackIndex}
      />
      <nav className="narrow-desk-tools" aria-label="窄窗书桌工具">
        {!isScratch && props.hasCourse && (
          <button type="button" onClick={() => props.onOpenBook("stack")}>
            <AppIcon icon={Layers3} />
            参考
          </button>
        )}
        {!isScratch && (
          <button type="button" onClick={props.onReview}>
            <AppIcon icon={Inbox} />
            卡片
          </button>
        )}
        <button type="button" onClick={props.onAsk}>
          <AppIcon icon={Coffee} />
          小娜
        </button>
      </nav>
    </main>
  );
}

function SessionHistory({ activeSession, open, onClose, onNew, onSelect }) {
  return (
    <aside
      className={`chat-history ${open ? "is-open" : ""}`}
      aria-label="历史会话"
      aria-hidden={!open}
    >
      <header>
        <h2>会话</h2>
        <button type="button" aria-label="关闭历史会话" onClick={onClose}>
          <AppIcon icon={X} size={17} />
        </button>
      </header>
      <button className="new-chat-action" type="button" onClick={onNew}>
        <AppIcon icon={Plus} size={16} />
        新对话
      </button>
      <div className="session-list">
        {CHAT_SESSIONS.map((session) => (
          <button
            className={activeSession === session.id ? "is-active" : ""}
            type="button"
            key={session.id}
            onClick={() => onSelect(session)}
          >
            <strong>{session.title}</strong>
            <span>
              {session.meta}
              {session.origin && <small>{session.origin}</small>}
            </span>
          </button>
        ))}
      </div>
    </aside>
  );
}

function ChatPaper({
  chatKind,
  activeSession,
  messages,
  chatDraft,
  onChatDraft,
  onSend,
  onOpenHistory,
  onReturn,
  onSaveDraft,
  onOpenCreate,
  savedMessages,
}) {
  const isCourse = chatKind === "course";
  const isStudio = chatKind === "studio";
  const isNew = activeSession === "new";
  const session = CHAT_SESSIONS.find((item) => item.id === activeSession);

  return (
    <section
      className="chat-paper chat-paper--minimal"
      aria-label={isNew ? "自由会话" : session?.title ?? "会话"}
    >
      <header className="chat-paper__header">
        <button
          className="history-toggle"
          type="button"
          aria-label="打开历史会话"
          onClick={onOpenHistory}
        >
          <AppIcon icon={Clock3} size={18} />
        </button>
        {!isNew && (
          <div className="chat-session-title">
            <h1>{session?.title}</h1>
            {session?.origin && <span>{session.origin}</span>}
          </div>
        )}
        {(isCourse || isStudio) && (
          <button className="return-action" type="button" onClick={onReturn}>
            <AppIcon icon={ArrowLeft} size={16} />
            {isCourse ? "返回这一步" : "返回项目"}
          </button>
        )}
      </header>

      <div className={`message-list ${isNew ? "message-list--empty" : ""}`} aria-live="polite">
        {isNew ? (
          <section className="chat-empty-state">
            <h1>和小娜聊聊</h1>
            <p>从一个问题，或一个还没想清楚的念头开始。</p>
          </section>
        ) : (
          messages.map((message, index) => {
            const messageId = `${activeSession}-${index}`;
            return (
              <article
                className={`message message--${message.role}`}
                key={`${message.role}-${index}`}
              >
                <div className="message-author">{message.role === "user" ? "我" : "小娜"}</div>
                <p>{message.text}</p>
                {message.meta && <small>{message.meta}</small>}
                {!isStudio && (
                  <div className="message-actions">
                    <button
                      type="button"
                      onClick={() => onSaveDraft(messageId)}
                      disabled={savedMessages.includes(messageId)}
                    >
                      <AppIcon icon={BookOpen} />
                      {savedMessages.includes(messageId) ? "已留下，待审核" : "留到本子里"}
                    </button>
                    {/* 课程会话属于 Study，学习就是纯粹的学习；取材由 Studio 那边发起 */}
                    {!isCourse && (
                      <button type="button" onClick={() => onOpenCreate(messageId)}>
                        <AppIcon icon={ArrowRight} />
                        发送到 Studio
                      </button>
                    )}
                  </div>
                )}
              </article>
            );
          })
        )}
      </div>

      <form
        className="chat-composer"
        onSubmit={(event) => {
          event.preventDefault();
          onSend();
        }}
      >
        <div className="composer-tools">
          <button type="button" aria-label="添加材料">
            <AppIcon icon={Plus} />
          </button>
          {(isCourse || isStudio) && (
            <span>{isCourse ? "高等数学" : "极限概念分享"}</span>
          )}
        </div>
        <textarea
          aria-label="发送消息"
          value={chatDraft}
          onChange={(event) => onChatDraft(event.target.value)}
          placeholder="和小娜聊聊…"
        />
        <button className="send-button" type="submit" aria-label="发送">
          <AppIcon icon={Send} />
        </button>
      </form>
    </section>
  );
}

function ChatDesk(props) {
  const messages =
    props.activeSession === "new"
      ? []
      : props.activeSession === "general-plan"
        ? PLAN_MESSAGES
        : props.chatKind === "course"
          ? COURSE_MESSAGES
          : props.chatKind === "studio"
            ? STUDIO_MESSAGES
            : GENERAL_MESSAGES;

  return (
    <main className="chat-desk" data-testid="chat-desk">
      <SessionHistory
        activeSession={props.activeSession}
        open={props.historyOpen}
        onClose={props.onCloseHistory}
        onNew={props.onNewChat}
        onSelect={props.onSelectSession}
      />
      <ChatPaper {...props} messages={messages} />
    </main>
  );
}

function ContextChatPanel({
  kind,
  chatDraft,
  onChatDraft,
  onClose,
  onOpenFull,
  onSend,
}) {
  const isCourse = kind === "course";
  const messages = isCourse ? COURSE_MESSAGES : STUDIO_MESSAGES;
  return (
    <aside className="context-chat-panel" aria-label={isCourse ? "Study 小娜聊天框" : "Studio 小娜聊天框"}>
      <header>
        <div>
          <span>{isCourse ? "Study" : "Studio"}</span>
          <h2>问小娜</h2>
        </div>
        <button type="button" aria-label="关闭聊天框" onClick={onClose}>
          <AppIcon icon={X} size={18} />
        </button>
      </header>
      <p className="context-chat-panel__scope">
        {isCourse ? "高等数学 · 练习 3 · 第 2 步" : "极限概念分享"}
      </p>
      <div className="context-chat-panel__messages" aria-live="polite">
        {messages.map((message, index) => (
          <article className={`mini-message mini-message--${message.role}`} key={`${message.role}-${index}`}>
            <strong>{message.role === "user" ? "我" : "小娜"}</strong>
            <p>{message.text}</p>
          </article>
        ))}
      </div>
      <form
        className="context-chat-composer"
        onSubmit={(event) => {
          event.preventDefault();
          onSend();
        }}
      >
        <textarea
          aria-label="发送消息"
          value={chatDraft}
          onChange={(event) => onChatDraft(event.target.value)}
          placeholder={isCourse ? "继续问这一步…" : "一起梳理这个项目…"}
        />
        <button className="send-button" type="submit" aria-label="发送">
          <AppIcon icon={Send} size={17} />
        </button>
      </form>
      <button className="open-full-chat" type="button" onClick={onOpenFull}>
        在完整 Chat 中打开
        <AppIcon icon={ArrowRight} size={15} />
      </button>
    </aside>
  );
}

function StudioDesk({
  connected,
  onNewProject,
  onOpenChat,
  onOpenTransfer,
  onReturnSource,
  onToast,
  points,
  onMovePoint,
  onInkPoint,
  onDropPoint,
  onAskDraft,
  indexOpen,
  onToggleIndex,
  onOpenMaterial,
}) {
  const pencilCount = points.filter((point) => point.state === "pencil").length;
  return (
    <main className="studio-desk" data-testid="studio-desk">
      {/* 夹子的标签是纵向的：本立着露顶边，夹插着露侧边 */}
      <nav className="folder-tabs" aria-label="我的工作夹">
        {connected && (
          <button className="folder-tab" type="button" aria-current="page">
            <span className="folder-spine" aria-hidden="true" />
            极限概念分享
          </button>
        )}
        <button className="folder-tab folder-tab--new" type="button" onClick={onNewProject}>
          <AppIcon icon={Plus} size={14} />
          新项目
        </button>
      </nav>

      <section className="studio-workspace" aria-label="当前项目">
        {connected ? (
          <>
            {/* Brief：别在夹子最前面的一张便条，所有排序判断都要回到它 */}
            {/* 标题本身已含受众与目的，不再另立字段；理清 Brief 走右下角那只杯子 */}
            <header className="brief-slip">
              <h1>把“0/0 是未定式”讲给刚接触极限的同学</h1>
            </header>

            <div className="point-stack">
              {points.map((point, index) => {
                const isPencil = point.state === "pencil";
                return (
                  <article
                    className={`point-card ${isPencil ? "point-card--pencil" : ""}`}
                    key={point.id}
                  >
                    <span className="point-order">{index + 1}</span>
                    <div>
                      <strong>{point.say}</strong>
                      <small>
                        {isPencil
                          ? "小娜拟的 · 你确认了才算数"
                          : point.backing
                            ? `出处：${point.backing}`
                            : "还没有出处"}
                      </small>
                    </div>
                    {isPencil ? (
                      <span className="pencil-actions">
                        <button type="button" onClick={() => onInkPoint(point.id)}>
                          <AppIcon icon={Check} size={14} />
                          要这条
                        </button>
                        <button type="button" onClick={() => onToast("原型：改写这张卡")}>
                          改写
                        </button>
                        <button type="button" onClick={() => onDropPoint(point.id)}>
                          抽走
                        </button>
                      </span>
                    ) : (
                      <span className="point-move">
                        <button
                          type="button"
                          aria-label={`把“${point.say}”往前挪`}
                          disabled={index === 0}
                          onClick={() => onMovePoint(index, -1)}
                        >
                          ↑
                        </button>
                        <button
                          type="button"
                          aria-label={`把“${point.say}”往后挪`}
                          disabled={index === points.length - 1}
                          onClick={() => onMovePoint(index, 1)}
                        >
                          ↓
                        </button>
                      </span>
                    )}
                  </article>
                );
              })}
              <div className="point-stack__foot">
                <button
                  className="point-add"
                  type="button"
                  onClick={() => onToast("原型：新增一张观点卡")}
                >
                  <AppIcon icon={Plus} size={15} />
                  自己写一条
                </button>
                <button className="point-ask" type="button" onClick={onAskDraft}>
                  <AppIcon icon={Coffee} size={15} />
                  让小娜再拟几条
                </button>
              </div>
            </div>

            {/* Writer 不是地方，是动作：顺序定了才成件，这时才选格式。
                还有铅笔卡就不能装订——不能把一份没确认的大纲成件。 */}
            <footer className="bind-bar">
              <button
                className="primary-action"
                type="button"
                disabled={pencilCount > 0}
                onClick={() => onToast("原型：这一步才选 PPT / 文档 / 讲义")}
              >
                按这个顺序做出来
                <AppIcon icon={ArrowRight} />
              </button>
              {/* 只在锁住时说话，并说清怎么解锁；用词与卡片上的按钮一致 */}
              {pencilCount > 0 && (
                <span>还有 {pencilCount} 条要你定：要，还是抽走</span>
              )}
            </footer>
          </>
        ) : (
          <div className="studio-empty">
            <FolderOpen aria-hidden="true" />
            <h2>先说清要讲给谁</h2>
            <p>项目从表达目标开始，不从文件格式开始。</p>
            <div className="inline-actions">
              <button className="primary-action" type="button" onClick={onNewProject}>
                <AppIcon icon={Plus} />
                新项目
              </button>
              <button type="button" onClick={onOpenTransfer}>
                <AppIcon icon={ArrowLeft} />
                从 Study 取素材
              </button>
            </div>
          </div>
        )}
      </section>

      <aside className="studio-rail studio-rail--sources" aria-label="素材">
        <section className="material-pile">
          <header>
            <h2>
              <AppIcon icon={Layers3} />
              素材
            </h2>
            <button type="button" onClick={() => onToast("原型：上传本地材料")}>
              <AppIcon icon={Plus} size={15} />
            </button>
          </header>
          {connected ? (
            <>
              {/* 点开的是复印件本身；想看原件是面板里的另一个动作 */}
              <button
                className="material-slip material-slip--copy"
                type="button"
                onClick={() => onOpenMaterial("practice-feedback")}
              >
                当前练习与反馈
                <small>复印件 · 原件在高等数学 · 练习 3</small>
              </button>
              <button
                className="material-slip material-slip--copy"
                type="button"
                onClick={() => onOpenMaterial("textbook-2-3")}
              >
                教材 §2.3
                <small>复印件 · 原件在高等数学 · 教材 §2.3</small>
              </button>
              {/* Material Index 不是一个去处，是这堆素材自己的目录 */}
              <button className="pile-index" type="button" onClick={onToggleIndex}>
                <AppIcon icon={FileText} size={14} />
                小娜从素材里读到的
              </button>
              {indexOpen && (
                <ul className="pile-index-list">
                  <li>未定式的定义 <span>教材 §2.3</span></li>
                  <li>可约因子的例题 3 则 <span>教材 §2.3</span></li>
                  <li>我写错的那一步 <span>练习与反馈</span></li>
                </ul>
              )}
            </>
          ) : (
            <p className="quiet-copy">还没有素材。可以上传，也可以从 Study 取。</p>
          )}
        </section>
        <button
          className="cup-anchor studio-cup-anchor"
          type="button"
          aria-label="碰杯问小娜，讨论当前工作夹"
          onClick={onOpenChat}
        >
          <span>
            <Coffee size={25} aria-hidden="true" />
          </span>
          <strong>碰杯问小娜</strong>
          <small>{connected ? "一起理这个项目" : "一起想讲给谁"}</small>
        </button>
      </aside>
    </main>
  );
}

function ModalShell({ title, eyebrow, onClose, children, wide = false }) {
  const closeRef = useRef(null);
  const sheetRef = useRef(null);
  useEffect(() => {
    closeRef.current?.focus();
  }, []);
  const trapFocus = (event) => {
    if (event.key !== "Tab") return;
    const focusables = sheetRef.current?.querySelectorAll(
      'button:not(:disabled), [href], input:not(:disabled), select:not(:disabled), textarea:not(:disabled), [tabindex]:not([tabindex="-1"])',
    );
    if (!focusables || focusables.length === 0) return;
    const first = focusables[0];
    const last = focusables[focusables.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  };
  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={onClose}>
      <section
        ref={sheetRef}
        className={`modal-sheet ${wide ? "modal-sheet--wide" : ""}`}
        role="dialog"
        aria-modal="true"
        aria-labelledby="modal-title"
        onMouseDown={(event) => event.stopPropagation()}
        onKeyDown={trapFocus}
      >
        <header>
          <div>
            {eyebrow && <span className="eyebrow">{eyebrow}</span>}
            <h2 id="modal-title">{title}</h2>
          </div>
          <button ref={closeRef} type="button" aria-label="关闭" onClick={onClose}>
            <AppIcon icon={X} />
          </button>
        </header>
        {children}
      </section>
    </div>
  );
}

// 用户在这一刻只想知道一件事：走了会不会丢东西。不在这里教产品的状态模型。
function LeavePracticeModal({ destination, onStay, onLeave }) {
  const label = STUDY_PAGES.find((page) => page.id === destination)?.label ?? "其他分页";
  return (
    <ModalShell title="刚改的还没检查" onClose={onStay}>
      <p className="modal-lead">离开就没了。</p>
      <div className="modal-actions">
        <button type="button" onClick={onStay}>留下</button>
        <button className="danger-action" type="button" onClick={onLeave}>
          丢掉，去{label}
        </button>
      </div>
    </ModalShell>
  );
}

function NewCourseModal({ onClose, onCreate }) {
  const [title, setTitle] = useState("高等数学");
  const [goal, setGoal] = useState("理解极限、导数与积分，并完成本学期练习");
  return (
    <ModalShell title="开一本课程本" eyebrow="J1 · 首次进入" onClose={onClose}>
      <form
        className="form-stack"
        onSubmit={(event) => {
          event.preventDefault();
          onCreate(title);
        }}
      >
        <label>
          <span>课程名称</span>
          <input value={title} onChange={(event) => setTitle(event.target.value)} required />
        </label>
        <label>
          <span>我想学会什么</span>
          <textarea value={goal} onChange={(event) => setGoal(event.target.value)} />
        </label>
        <aside className="honest-note">
          <ShieldCheck aria-hidden="true" />
          <p>
            <strong>先建本地课程，不要求模型配置。</strong>
            需要小娜解释或生成内容时，再明确提示你配置 provider。
          </p>
        </aside>
        <div className="modal-actions">
          <button type="button" onClick={onClose}>
            取消
          </button>
          <button className="primary-action" type="submit">
            开始这门课
            <AppIcon icon={ArrowRight} />
          </button>
        </div>
      </form>
    </ModalShell>
  );
}

function AskPreviewModal({ onClose, onStart }) {
  const [question, setQuestion] = useState(
    "我知道代入后是 0/0，但不知道为什么这还不是答案。",
  );
  return (
    <ModalShell title="结合当前这一步问小娜" eyebrow="提问前审核" onClose={onClose}>
      <p className="modal-lead">
        她会带上你正在看的题、刚写的答案和“还差一步”，不会替你改答案。
      </p>
      <section className="context-preview">
        <strong>高等数学 · 练习 3 · 第 2 步</strong>
        <span>返回位置：我的答案与页边批注</span>
      </section>
      <label className="form-stack">
        <span>我卡在哪里？</span>
        <textarea value={question} onChange={(event) => setQuestion(event.target.value)} />
      </label>
      <div className="modal-actions">
        <button type="button" onClick={onClose}>
          先不问
        </button>
        <button className="primary-action" type="button" onClick={() => onStart(question)}>
          开始提问
          <AppIcon icon={ArrowRight} />
        </button>
      </div>
    </ModalShell>
  );
}

function DraftReviewModal({ onClose, onAccept, boundCourse }) {
  return (
    <ModalShell
      title={boundCourse ? `审核后留进${boundCourse}` : "审核后再留到本子里"}
      eyebrow="Chat → Study"
      onClose={onClose}
      wide
    >
      <div className="draft-review-layout">
        <section>
          <h3>待审核内容</h3>
          <blockquote>
            0/0 不是一个确定的数，也不是极限答案；它表示直接代入不足以判断结果，需要继续化简或采用其他分析方法。
          </blockquote>
          <h3>来源</h3>
          <div className="source-list">
            <span>
              <MessageCircle size={16} aria-hidden="true" />
              普通对话 · “整理今天的学习”
            </span>
            <span>
              <FileText size={16} aria-hidden="true" />
              小娜回复 · 今天 14:06
            </span>
          </div>
        </section>
        <aside>
          {!boundCourse && (
            <label>
              <span>留到</span>
              <select defaultValue="calculus">
                <option value="calculus">高等数学</option>
                <option value="physics">大学物理</option>
                <option value="scratch">杂记本 · 还不属于哪门课</option>
              </select>
            </label>
          )}
          <label>
            <span>作为</span>
            <select defaultValue="note">
              <option value="note">待审核辅导笔记</option>
              <option value="knowledge">待审核知识点</option>
            </select>
          </label>
          <aside className="honest-note">
            <ShieldCheck aria-hidden="true" />
            <p>
              <strong>不会自动改变掌握度。</strong>
              激活前它只是 draft，也不会完成计划或练习。
            </p>
          </aside>
        </aside>
      </div>
      <div className="modal-actions">
        <button type="button" onClick={onClose}>
          返回修改
        </button>
        <button className="primary-action" type="button" onClick={onAccept}>
          保存为待审核草稿
          <AppIcon icon={Check} />
        </button>
      </div>
    </ModalShell>
  );
}

function StudioTransferModal({ onClose, step, setStep, onAccept, origin }) {
  const [target, setTarget] = useState("existing");
  const availableSources =
    origin === "chat"
      ? ["普通对话回复 · 0/0 未定式", "普通对话上下文"]
      : ["当前练习与反馈", "教材 §2.3", "“0/0 未定式”辅导笔记"];
  const [selected, setSelected] = useState(
    origin === "chat" ? ["普通对话回复 · 0/0 未定式"] : ["当前练习与反馈", "教材 §2.3"],
  );
  const toggleSource = (source) => {
    setSelected((items) =>
      items.includes(source) ? items.filter((item) => item !== source) : [...items, source],
    );
  };

  return (
    <ModalShell
      title={origin === "chat" ? "发送到 Studio" : "从 Study 取素材"}
      onClose={onClose}
      wide
    >
      {step === "select" ? (
        <>
          <div className="stepper">
            <strong>1 选内容</strong>
            <span>2 看一眼</span>
            <span>3 取过来</span>
          </div>
          <div className="transfer-grid">
            <section>
              <h3>取哪些</h3>
              {availableSources.map((source) => (
                <label className="source-choice" key={source}>
                  <input
                    type="checkbox"
                    checked={selected.includes(source)}
                    onChange={() => toggleSource(source)}
                  />
                  <span>
                    <FileText aria-hidden="true" />
                    <strong>{source}</strong>
                    {/* 出处只说出处；"不会动到原件"整屏说一次就够（见底部） */}
                    <small>{origin === "chat" ? "自由对话 · 昨天" : "高等数学 · 练习 3"}</small>
                  </span>
                </label>
              ))}
            </section>
            <section>
              <h3>放进哪个项目</h3>
              <label className="source-choice">
                <input
                  type="radio"
                  name="studio-target"
                  checked={target === "existing"}
                  onChange={() => setTarget("existing")}
                />
                <span>
                  <FolderOpen aria-hidden="true" />
                  <strong>极限概念分享</strong>
                  <small>已有的项目 · 还没写清要讲什么</small>
                </span>
              </label>
              <label className="source-choice">
                <input
                  type="radio"
                  name="studio-target"
                  checked={target === "new"}
                  onChange={() => setTarget("new")}
                />
                <span>
                  <FolderPlus aria-hidden="true" />
                  <strong>新项目</strong>
                  <small>先建个空的，格式以后再选</small>
                </span>
              </label>
            </section>
          </div>
          <div className="modal-actions">
            <button type="button" onClick={onClose}>
              取消
            </button>
            <button
              className="primary-action"
              type="button"
              disabled={selected.length === 0}
              onClick={() => setStep("review")}
            >
              看一眼
              <AppIcon icon={ArrowRight} />
            </button>
          </div>
        </>
      ) : (
        <>
          <div className="stepper">
            <span>1 选内容</span>
            <strong>2 看一眼</strong>
            <span>3 取过来</span>
          </div>
          <section className="snapshot-review">
            <div>
              <span>取这些</span>
              <strong>{selected.join("、")}</strong>
            </div>
            <div>
              <span>放进</span>
              <strong>{target === "existing" ? "极限概念分享" : "一个新项目"}</strong>
            </div>
          </section>
          {/* 用户只需要知道两件事：拿走的是什么，会不会动到原件 */}
          <aside className="honest-note">
            <ShieldCheck aria-hidden="true" />
            <p>
              <strong>取的是复印件，原件留在高等数学里。</strong>
              在这边怎么改，都不会动到你的课程。
            </p>
          </aside>
          <div className="modal-actions">
            <button type="button" onClick={() => setStep("select")}>
              返回修改
            </button>
            <button className="primary-action" type="button" onClick={onAccept}>
              取过来
              <AppIcon icon={ArrowRight} />
            </button>
          </div>
        </>
      )}
    </ModalShell>
  );
}

function ActivityPanel({
  onClose,
  transferStep,
  studioConnected,
  draftSaved,
  onOpenStudio,
  onOpenDraft,
  onOpenRecovery,
}) {
  return (
    <div className="panel-backdrop" role="presentation" onMouseDown={onClose}>
      <aside
        className="activity-panel"
        role="dialog"
        aria-modal="true"
        aria-labelledby="activity-title"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <header>
          <div>
            <span className="eyebrow">跨页面现场</span>
            <h2 id="activity-title">Activity / Recent</h2>
          </div>
          <button type="button" aria-label="关闭" onClick={onClose}>
            <AppIcon icon={X} />
          </button>
        </header>
        <section>
          <h3>进行中</h3>
          <button className="activity-row" type="button">
            <span className="activity-icon activity-icon--study">
              <BookOpen aria-hidden="true" />
            </span>
            <span>
              <strong>练习 3 · 第 2 步</strong>
              <small>高等数学 · 答案已保存</small>
            </span>
            <StatusPill tone="info">可继续</StatusPill>
          </button>
          {(transferStep === "review" || studioConnected) && (
            <button className="activity-row" type="button" onClick={onOpenStudio}>
              <span className="activity-icon activity-icon--create">
                <FolderOpen aria-hidden="true" />
              </span>
              <span>
                <strong>Studio · 极限概念分享</strong>
                <small>{studioConnected ? "素材已取过来 · 还没写清要讲什么" : "素材还没确认取哪些"}</small>
              </span>
              <StatusPill tone={studioConnected ? "info" : "warning"}>
                {studioConnected ? "可继续" : "待审核"}
              </StatusPill>
            </button>
          )}
        </section>
        <section>
          <h3>待处理</h3>
          {draftSaved ? (
            <button className="activity-row" type="button" onClick={onOpenDraft}>
              <span className="activity-icon activity-icon--draft">
                <PencilLine aria-hidden="true" />
              </span>
              <span>
                <strong>“0/0 未定式”辅导笔记</strong>
                <small>高等数学 · 等待你审核激活</small>
              </span>
              <StatusPill tone="warning">待审核</StatusPill>
            </button>
          ) : (
            <p className="panel-empty">没有等待处理的草稿。</p>
          )}
        </section>
        <section>
          <h3>最近项目</h3>
          {studioConnected ? (
            <button className="activity-row" type="button" onClick={onOpenStudio}>
              <span className="activity-icon activity-icon--result">
                <FolderOpen aria-hidden="true" />
              </span>
              <span>
                <strong>极限概念分享</strong>
                <small>项目 · 素材 2 份</small>
              </span>
              <StatusPill tone="prototype">布局阶段</StatusPill>
            </button>
          ) : (
            <p className="panel-empty">项目会和学习活动分开显示。</p>
          )}
        </section>
        <button className="recovery-test" type="button" onClick={onOpenRecovery}>
          <AppIcon icon={RotateCcw} />
          模拟应用重启后的恢复选择
        </button>
      </aside>
    </div>
  );
}

function RecoveryModal({ onClose, onResumeStudy, onResumeStudio }) {
  return (
    <ModalShell title="欢迎回来，要继续哪一件？" eyebrow="J5 · 重启恢复" onClose={onClose} wide>
      <p className="modal-lead">
        检测到多个可恢复现场。Kabuqina 不会替你猜，也不会让较新的活动覆盖较旧的活动。
      </p>
      <div className="recovery-grid">
        <button type="button" onClick={onResumeStudy}>
          <span className="activity-icon activity-icon--study">
            <BookOpen aria-hidden="true" />
          </span>
          <span>
            <StatusPill tone="info">学习</StatusPill>
            <strong>练习 3 · 第 2 步</strong>
            <small>答案已保存 · 返回位置有效</small>
          </span>
          <ArrowRight aria-hidden="true" />
        </button>
        <button type="button" onClick={onResumeStudio}>
          <span className="activity-icon activity-icon--create">
            <FolderOpen aria-hidden="true" />
          </span>
          <span>
            <StatusPill tone="prototype">Studio</StatusPill>
            <strong>极限概念分享</strong>
            <small>素材和顺序都在，可以接着做</small>
          </span>
          <ArrowRight aria-hidden="true" />
        </button>
      </div>
      <aside className="recovery-warning">
        <AlertCircle aria-hidden="true" />
        <div>
          <strong>一个旧返回位置已经失效</strong>
          <p>原练习被删除，因此只回到“高等数学”课程总览，不打开错误课程，也不丢弃记录。</p>
        </div>
        <button type="button" onClick={onResumeStudy}>
          安全打开课程
        </button>
      </aside>
    </ModalShell>
  );
}

function SettingsModal({ onClose, theme, onToggleTheme }) {
  return (
    <ModalShell title="设置" eyebrow="诚实的能力状态" onClose={onClose}>
      <section className="settings-list">
        <div>
          <span className="settings-icon">
            <LampDesk aria-hidden="true" />
          </span>
          <span>
            <strong>台灯 · 外观</strong>
            <small>深浅模式跟随桌上的台灯；右上角随时可切换</small>
          </span>
          <button className="theme-mirror" type="button" onClick={onToggleTheme}>
            {theme === "dark" ? "关灯" : "开灯"}
          </button>
        </div>
        <div>
          <span className="settings-icon">
            <Sparkles aria-hidden="true" />
          </span>
          <span>
            <strong>模型与费用</strong>
            <small>未在原型中连接真实 provider</small>
          </span>
          <StatusPill tone="warning">模拟</StatusPill>
        </div>
        <div>
          <span className="settings-icon">
            <ShieldCheck aria-hidden="true" />
          </span>
          <span>
            <strong>学习改进计数</strong>
            <small>默认关闭；不发送题目、答案和来源</small>
          </span>
          <StatusPill>关闭</StatusPill>
        </div>
        <div>
          <span className="settings-icon">
            <GraduationCap aria-hidden="true" />
          </span>
          <span>
            <strong>结构化 Tutor</strong>
            <small>产品行为可演示，生产 runtime 尚未在本原型验证</small>
          </span>
          <StatusPill tone="prototype">原型</StatusPill>
        </div>
      </section>
    </ModalShell>
  );
}

function CardReviewModal({ onClose, onGrade }) {
  const [revealed, setRevealed] = useState(false);
  const shownAt = useRef(Date.now());
  const thinkingMs = useRef(null);

  const reveal = () => {
    thinkingMs.current = Date.now() - shownAt.current;
    setRevealed(true);
  };

  return (
    <ModalShell title="今天要复习" onClose={onClose}>
      <section className="flashcard">
        <span>高等数学 · 极限</span>
        <h3>为什么 0/0 不能直接当作极限值？</h3>
        {revealed ? (
          <p>
            因为 0/0 是未定式：不同函数都可能在代入时得到 0/0，但极限结果可能不同，需要继续分析。
          </p>
        ) : (
          <button className="primary-action" type="button" onClick={reveal}>
            显示答案
          </button>
        )}
      </section>
      {revealed && (
        <>
          {/* 只问学习者能可靠回答的那一个问题：想起来了没有。
              两个按钮等重——把"想起来了"做成主动作会诱导不诚实的自评，
              调度器拿到的就是垃圾。难度不问，用翻面耗时去量。 */}
          <div className="recall-grid">
            <button type="button" onClick={() => onGrade(RECALL_GRADES.recalled, thinkingMs.current)}>
              想起来了
            </button>
            <button type="button" onClick={() => onGrade(RECALL_GRADES.forgot, thinkingMs.current)}>
              没想起来
            </button>
          </div>
          <button
            className="too-easy"
            type="button"
            onClick={() => onGrade(RECALL_GRADES.tooEasy, thinkingMs.current)}
          >
            这张太简单了，别再常来
          </button>
        </>
      )}
    </ModalShell>
  );
}

export function App() {
  const [journey, setJourney] = useState("J2");
  const [surface, setSurface] = useState("study");
  const [hasCourse, setHasCourse] = useState(true);
  const [studyState, setStudyState] = useState("overview");
  const [studyPage, setStudyPage] = useState("learn");
  const [answer, setAnswer] = useState(INITIAL_ANSWER);
  const [practiceDirty, setPracticeDirty] = useState(false);
  const [pendingStudyPage, setPendingStudyPage] = useState(null);
  const [flyleafDraftVisible, setFlyleafDraftVisible] = useState(true);
  const [learnStep, setLearnStep] = useState("seed");
  const [learnDraft, setLearnDraft] = useState("");
  const [activeBook, setActiveBook] = useState(COURSE.id);
  const [scratchDraft, setScratchDraft] = useState("");
  const [scratchNotes, setScratchNotes] = useState(INITIAL_SCRATCH_NOTES);
  const [filingId, setFilingId] = useState(null);
  const [points, setPoints] = useState(INITIAL_POINTS);
  const [indexOpen, setIndexOpen] = useState(false);
  const [stackIndexOpen, setStackIndexOpen] = useState(false);
  const [openMaterial, setOpenMaterial] = useState(null);
  const [citeOpen, setCiteOpen] = useState(false);
  const [planItems, setPlanItems] = useState(INITIAL_PLAN_ITEMS);
  const [chatKind, setChatKind] = useState("general");
  const [activeChatSession, setActiveChatSession] = useState("new");
  const [chatHistoryOpen, setChatHistoryOpen] = useState(false);
  const [contextChat, setContextChat] = useState(null);
  const [chatDraft, setChatDraft] = useState("");
  const [overlay, setOverlay] = useState(null);
  const [draftSaved, setDraftSaved] = useState(false);
  const [savedMessages, setSavedMessages] = useState([]);
  const [pendingSaveId, setPendingSaveId] = useState(null);
  const [draftActivated, setDraftActivated] = useState(false);
  const [reviewDone, setReviewDone] = useState(false);
  const [transferStep, setTransferStep] = useState("select");
  const [studioConnected, setStudioConnected] = useState(false);
  const [transferOrigin, setTransferOrigin] = useState("study");
  const [toast, setToast] = useState("");
  const [theme, setTheme] = useState(() =>
    document.documentElement.dataset.theme === "dark" ? "dark" : "light",
  );
  const [productStatus, setProductStatus] = useState(
    "J2 ready · 书桌 → 课程 Chat → 精确返回",
  );

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try {
      window.localStorage.setItem("kabuqina-theme", theme);
    } catch {
      /* 无持久化环境时静默 */
    }
  }, [theme]);

  const activityCount = useMemo(() => {
    let count = 1;
    if (draftSaved && !draftActivated) count += 1;
    if (transferStep === "review" || studioConnected) count += 1;
    return count;
  }, [draftActivated, draftSaved, studioConnected, transferStep]);

  useEffect(() => {
    if (!toast) return undefined;
    const timer = window.setTimeout(() => setToast(""), 2600);
    return () => window.clearTimeout(timer);
  }, [toast]);

  useEffect(() => {
    const handleKey = (event) => {
      if (event.key === "Escape") {
        if (overlay) {
          setOverlay(null);
          setPendingStudyPage(null);
        } else if (contextChat) {
          setContextChat(null);
        } else if (chatHistoryOpen) {
          setChatHistoryOpen(false);
        }
      }
    };
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [chatHistoryOpen, contextChat, overlay]);

  const openStudyPage = (page, options = {}) => {
    const { bypassGuard = false } = options;
    if (!bypassGuard && studyPage === "practice" && practiceDirty && page !== "practice") {
      setPendingStudyPage(page);
      setOverlay("leave-practice");
      return;
    }
    setStudyPage(page);
    setPendingStudyPage(null);
    setOverlay(null);
    if (page === "practice") {
      setStudyState((current) => (["returned", "complete"].includes(current) ? current : "practice"));
    } else {
      setStudyState("overview");
    }
    setProductStatus(`Study · 已打开${STUDY_PAGES.find((item) => item.id === page)?.label ?? "课程"}页`);
  };

  const updatePlanItem = (id, status) => {
    setPlanItems((items) => items.map((item) => (item.id === id ? { ...item, status } : item)));
    setToast(status === "done" ? "计划项已完成，并记录为学习活动" : "计划项已跳过，未计为完成");
  };

  const resetJourney = (id) => {
    setJourney(id);
    setOverlay(null);
    setContextChat(null);
    setChatHistoryOpen(false);
    setPendingStudyPage(null);
    setToast("");
    setReviewDone(false);
    setPracticeDirty(false);
    setAnswer(INITIAL_ANSWER);
    setFlyleafDraftVisible(true);
    setPlanItems(INITIAL_PLAN_ITEMS);
    setLearnStep("seed");
    setLearnDraft("");
    setActiveBook(COURSE.id);
    setScratchNotes(INITIAL_SCRATCH_NOTES);
    setFilingId(null);
    if (id === "J1") {
      setSurface("study");
      setHasCourse(false);
      setStudyState("overview");
      setStudyPage("flyleaf");
      setDraftSaved(false);
      setDraftActivated(false);
      setTransferStep("select");
      setStudioConnected(false);
      setProductStatus("J1 ready · 第一次进入，没有隐式课程，也不要求先配模型");
      return;
    }
    setHasCourse(true);
    if (id === "J2") {
      setSurface("study");
      setStudyState("overview");
      setStudyPage("learn");
      setChatKind("course");
      setActiveChatSession("course-limit");
      setStudioConnected(false);
      setTransferStep("select");
      setProductStatus("J2 ready · 书桌 → 课程 Chat → 精确返回");
      return;
    }
    if (id === "J3") {
      setSurface("chat");
      setChatKind("general");
      setActiveChatSession("general-study");
      setDraftSaved(false);
      setDraftActivated(false);
      setStudioConnected(false);
      setTransferStep("select");
      setProductStatus("J3 ready · 普通对话不绑课，保存前先审核");
      return;
    }
    if (id === "J4") {
      setSurface("studio");
      setStudyState("overview");
      setStudyPage("learn");
      setTransferStep("select");
      setStudioConnected(false);
      setTransferOrigin("study");
      setProductStatus("J4 ready · 由 Studio 发起取材；Study 侧没有向外的出口");
      return;
    }
    setSurface("study");
    setStudyState("practice");
    setStudyPage("practice");
    setTransferStep("done");
    setStudioConnected(true);
    setOverlay("recovery");
    setProductStatus("J5 ready · Study 与 Studio 现场并存，由用户选择恢复");
  };

  // 课程会话已有明确课程：照存，只跳过选课程那一步，内容与类型仍需审核
  const openDraftReview = (messageId) => {
    setPendingSaveId(messageId);
    setOverlay("draft-review");
  };

  const openFullContextChat = (kind) => {
    setContextChat(null);
    setSurface("chat");
    setChatKind(kind);
    setActiveChatSession(kind === "course" ? "course-limit" : "studio-limit");
    setProductStatus(
      kind === "course"
        ? "J2 in progress · 已从轻量聊天打开课程历史会话"
        : "Studio Chat · 已从轻量聊天打开项目历史会话",
    );
  };

  const returnToStudy = () => {
    setOverlay(null);
    setSurface("study");
    setStudyPage("practice");
    setStudyState("returned");
    setPracticeDirty(false);
    setProductStatus("J2 complete · 原答案未改写，反馈与焦点回到原位置");
    setToast("已准确返回练习 3 · 第 2 步");
  };

  const acceptDraft = () => {
    setDraftSaved(true);
    if (pendingSaveId) setSavedMessages((ids) => [...ids, pendingSaveId]);
    setPendingSaveId(null);
    setOverlay(null);
    setProductStatus("J3 complete · 草稿已进入高等数学待审核区，未改变掌握度");
    setToast("已保存为待审核草稿");
  };

  const openDraftFromActivity = () => {
    setOverlay(null);
    setSurface("study");
    setStudyState("overview");
    setStudyPage("learn");
    setDraftActivated(true);
    setProductStatus("J3 reviewed · 草稿已在课程内预览，等待显式激活");
    setToast("已打开高等数学的待审核草稿");
  };

  const createCourse = () => {
    setHasCourse(true);
    setOverlay(null);
    setStudyState("overview");
    setStudyPage("flyleaf");
    setProductStatus("J1 complete · 已建课并进入明确第一步；本地能力不依赖模型");
    setToast("高等数学课程本已放上书桌");
  };

  const openStudioTransfer = (origin = "study") => {
    setTransferOrigin(origin);
    setTransferStep("select");
    setOverlay("studio-transfer");
    setProductStatus(
      origin === "chat"
        ? "Studio handoff · 审核普通 Chat 回复后再进入 Project"
        : "J4 in progress · 选择要转交的 Study 来源",
    );
  };

  return (
    <div className="prototype-page">
      <PrototypeRail
        activeJourney={journey}
        onSelect={resetJourney}
        productStatus={productStatus}
      />
      <section className="app-frame" aria-label="Kabuqina v0.5.0 全产品原型">
        <AppHeader
          surface={surface}
          onSurface={(next) => {
            setSurface(next);
            setOverlay(null);
            setContextChat(null);
            setChatHistoryOpen(false);
            if (next === "chat") {
              setChatKind("general");
              setActiveChatSession("new");
              setProductStatus("Chat · 新的自由会话");
            }
          }}
          onOpenActivity={() => setOverlay("activity")}
          onOpenSettings={() => setOverlay("settings")}
          activityCount={activityCount}
          theme={theme}
          onToggleTheme={() => setTheme((current) => (current === "dark" ? "light" : "dark"))}
        />
        {surface === "study" ? (
          <StudyDesk
            hasCourse={hasCourse}
            studyState={studyState}
            studyPage={studyPage}
            answer={answer}
            onAnswer={(value) => {
              setAnswer(value);
              setPracticeDirty(true);
            }}
            onCreateCourse={() => setOverlay("new-course")}
            onContinue={() => {
              setStudyPage("practice");
              setStudyState("practice");
              setProductStatus("J2 in progress · 当前题、答案与返回位置已建立");
            }}
            onNavigatePage={openStudyPage}
            onAsk={() => {
              setContextChat("course");
              setProductStatus("J2 in progress · 小娜在当前学习页边展开");
            }}
            onCheck={() => {
              setPracticeDirty(false);
              setStudyState("returned");
              setToast("检查完成：还差一步");
            }}
            onReview={() => setOverlay("review-card")}
            reviewDone={reviewDone}
            flyleafDraftVisible={flyleafDraftVisible}
            onInkFlyleaf={() => {
              setFlyleafDraftVisible(false);
              setToast("学习设定已确认");
            }}
            onEraseFlyleaf={() => {
              setFlyleafDraftVisible(false);
              setToast("铅笔草稿已擦除，原设定保持不变");
            }}
            planItems={planItems}
            onUpdatePlan={updatePlanItem}
            activeBook={activeBook}
            onSelectBook={(book) => {
              setActiveBook(book.id);
              setFilingId(null);
              setProductStatus(
                book.kind === "scratch"
                  ? "Study · 杂记本：不属于任何课程的一页"
                  : `Study · 已翻到${book.title}`,
              );
            }}
            scratchDraft={scratchDraft}
            onScratchDraft={setScratchDraft}
            scratchNotes={scratchNotes}
            filingId={filingId}
            onStartFiling={setFilingId}
            onCancelFiling={() => setFilingId(null)}
            onFileNote={(note, book) => {
              setScratchNotes((items) => items.filter((item) => item.id !== note.id));
              setFilingId(null);
              setToast(`已归到${book.title}，等你审核后才进课程`);
            }}
            learnStep={learnStep}
            learnDraft={learnDraft}
            onLearnDraft={setLearnDraft}
            onLearnContrast={() => {
              setLearnStep("contrast");
              setProductStatus("Study · 学习页对照：你的说法与教材并排，不判分");
            }}
            onLearnReveal={() => {
              setLearnStep("contrast");
              setToast("已展开教材说法；看完仍建议自己说一遍");
            }}
            onLearnRewrite={() => setLearnStep("seed")}
            draftSaved={draftSaved && !draftActivated}
            onOpenDraft={openDraftFromActivity}
            onOpenBook={(id) => {
              // 窄屏下书堆整条被隐藏，"参考"是唯一入口，得先给一个书架让人挑
              if (id === "stack") {
                setOpenMaterial("stack");
                return;
              }
              if (!id || !MATERIALS[id]) {
                setToast("原型：放一本参考资料进来");
                return;
              }
              setOpenMaterial(id);
            }}
            stackIndexOpen={stackIndexOpen}
            onToggleStackIndex={() => setStackIndexOpen((open) => !open)}
            onRetryWrongbook={() => {
              setStudyPage("practice");
              setStudyState("practice");
              setProductStatus("Study · 从评估页回到错题来源");
              setToast("已带着错题来源回到练习 3 · 第 2 步");
            }}
            onToast={setToast}
          />
        ) : surface === "studio" ? (
          <StudioDesk
            connected={studioConnected}
            onNewProject={() => {
              setStudioConnected(true);
              setTransferStep("done");
              setProductStatus("Studio ready · 已建立空 Project，尚未选择输出形式");
              setToast("已新建项目");
            }}
            onOpenChat={() => {
              setContextChat("studio");
              setProductStatus("Studio · 小娜在当前 Project 旁展开");
            }}
            onOpenTransfer={() => openStudioTransfer("study")}
            onReturnSource={() => {
              setSurface("study");
              setStudyPage("practice");
              setStudyState("practice");
              setToast("已回到高等数学 · 原来源位置");
            }}
            onToast={setToast}
            points={points}
            onMovePoint={(index, delta) => {
              setPoints((items) => {
                const next = [...items];
                const [moved] = next.splice(index, 1);
                next.splice(index + delta, 0, moved);
                return next;
              });
            }}
            onInkPoint={(id) => {
              setPoints((items) =>
                items.map((item) => (item.id === id ? { ...item, state: "ink" } : item)),
              );
              setToast("已加进顺序");
            }}
            onDropPoint={(id) => {
              setPoints((items) => items.filter((item) => item.id !== id));
              setToast("已抽走，没有写进项目");
            }}
            onAskDraft={() => {
              setPoints((items) => [
                ...items,
                {
                  id: `p${Date.now()}`,
                  say: "结尾留一个让他们自己试的问题",
                  backing: null,
                  state: "pencil",
                },
              ]);
              setProductStatus("Studio · 小娜又拟了一条，仍是铅笔，等你过目");
            }}
            indexOpen={indexOpen}
            onToggleIndex={() => setIndexOpen((open) => !open)}
            onOpenMaterial={(id) => {
              setOpenMaterial(id);
              setCiteOpen(false);
            }}
          />
        ) : (
          <ChatDesk
            chatKind={chatKind}
            activeSession={activeChatSession}
            historyOpen={chatHistoryOpen}
            onOpenHistory={() => setChatHistoryOpen(true)}
            onCloseHistory={() => setChatHistoryOpen(false)}
            onNewChat={() => {
              setChatKind("general");
              setActiveChatSession("new");
              setChatHistoryOpen(false);
              setProductStatus("Chat · 新的自由会话");
            }}
            onSelectSession={(session) => {
              setChatKind(session.kind);
              setActiveChatSession(session.id);
              setChatHistoryOpen(false);
              setProductStatus(
                session.kind === "course"
                  ? "Chat · 已打开来自 Study 的历史会话"
                  : session.kind === "studio"
                    ? "Chat · 已打开来自 Studio 的历史会话"
                    : "Chat · 已打开自由会话历史",
              );
            }}
            chatDraft={chatDraft}
            onChatDraft={setChatDraft}
            onSend={() => {
              if (!chatDraft.trim()) return;
              setChatDraft("");
              setToast("原型已模拟发送");
            }}
            onReturn={() => {
              if (chatKind === "course") {
                returnToStudy();
              } else {
                setSurface("studio");
                setProductStatus("Studio · 已返回极限概念分享");
              }
            }}
            onSaveDraft={openDraftReview}
            onOpenCreate={() => openStudioTransfer("chat")}
            savedMessages={savedMessages}
          />
        )}

        {draftActivated && surface === "study" && (
          <aside className="draft-activation-banner" aria-live="polite">
            <PencilLine aria-hidden="true" />
            <span>
              <strong>待审核辅导笔记</strong>
              “0/0 未定式”已预览；只有点击“激活”后才进入课程知识。
            </span>
            <button
              type="button"
              onClick={() => {
                setDraftActivated(false);
                setDraftSaved(false);
                setToast("草稿已激活为辅导笔记");
              }}
            >
              激活
            </button>
          </aside>
        )}

        {overlay === "leave-practice" && (
          <LeavePracticeModal
            destination={pendingStudyPage}
            onStay={() => {
              setOverlay(null);
              setPendingStudyPage(null);
              setToast("已留在练习，草稿保持不变");
            }}
            onLeave={() => {
              const destination = pendingStudyPage ?? "learn";
              setAnswer(INITIAL_ANSWER);
              setPracticeDirty(false);
              openStudyPage(destination, { bypassGuard: true });
              setToast("刚才的修改已丢掉");
            }}
          />
        )}
        {overlay === "new-course" && (
          <NewCourseModal onClose={() => setOverlay(null)} onCreate={createCourse} />
        )}
        {openMaterial === "stack" && (
          <aside className="material-panel" aria-label="本课参考">
            <header>
              <div>
                <span className="eyebrow">抽一本出来看</span>
                <h2>参考资料</h2>
              </div>
              <button type="button" aria-label="放回去" onClick={() => setOpenMaterial(null)}>
                <AppIcon icon={X} size={18} />
              </button>
            </header>
            <div className="material-body">
              {["textbook-2-3", "workbook-41"].map((id) => (
                <button
                  className="shelf-row"
                  type="button"
                  key={id}
                  onClick={() => setOpenMaterial(id)}
                >
                  <strong>{MATERIALS[id].title}</strong>
                  <small>{MATERIALS[id].subtitle}</small>
                </button>
              ))}
            </div>
          </aside>
        )}
        {openMaterial && MATERIALS[openMaterial] && (
          <MaterialPanel
            material={MATERIALS[openMaterial]}
            mode={surface === "studio" ? "studio" : "study"}
            onClose={() => {
              setOpenMaterial(null);
              setCiteOpen(false);
            }}
            onNote={() => {
              setOpenMaterial(null);
              setSurface("study");
              setStudyPage("learn");
              setLearnStep("seed");
              setToast("材料放回去了，现在用自己的话说一遍");
            }}
            citeTargets={points.filter((point) => point.state === "ink")}
            citeOpen={citeOpen}
            onStartCite={() => setCiteOpen(true)}
            onCite={(point) => {
              setPoints((items) =>
                items.map((item) =>
                  item.id === point.id
                    ? { ...item, backing: MATERIALS[openMaterial].title }
                    : item,
                ),
              );
              setCiteOpen(false);
              setOpenMaterial(null);
              setToast(`已挂到「${point.say}」下面`);
            }}
            onOpenOriginal={() => {
              setOpenMaterial(null);
              setSurface("study");
              setStudyPage("practice");
              setStudyState("practice");
              setToast("已回到高等数学 · 原件位置");
            }}
          />
        )}
        {contextChat && (
          <ContextChatPanel
            kind={contextChat}
            chatDraft={chatDraft}
            onChatDraft={setChatDraft}
            onClose={() => setContextChat(null)}
            onOpenFull={() => openFullContextChat(contextChat)}
            onSend={() => {
              if (!chatDraft.trim()) return;
              setChatDraft("");
              setToast("原型已模拟发送");
            }}
          />
        )}
        {overlay === "draft-review" && (
          <DraftReviewModal
            onClose={() => setOverlay(null)}
            onAccept={acceptDraft}
            boundCourse={chatKind === "course" ? COURSE.title : null}
          />
        )}
        {overlay === "studio-transfer" && (
          <StudioTransferModal
            onClose={() => setOverlay(null)}
            step={transferStep}
            setStep={setTransferStep}
            origin={transferOrigin}
            onAccept={() => {
              setStudioConnected(true);
              setTransferStep("done");
              setOverlay(null);
              setSurface("studio");
              setProductStatus("J4 complete · SourceSnapshot 已建立，Study 真值未被改写");
              setToast("已打开 Studio · 极限概念分享");
            }}
          />
        )}
        {overlay === "activity" && (
          <ActivityPanel
            onClose={() => setOverlay(null)}
            transferStep={transferStep}
            studioConnected={studioConnected}
            draftSaved={draftSaved && !draftActivated}
            onOpenStudio={() => {
              setOverlay(null);
              setSurface("studio");
            }}
            onOpenDraft={openDraftFromActivity}
            onOpenRecovery={() => setOverlay("recovery")}
          />
        )}
        {overlay === "recovery" && (
          <RecoveryModal
            onClose={() => setOverlay(null)}
            onResumeStudy={() => {
              setOverlay(null);
              setSurface("study");
              setStudyPage("practice");
              setStudyState("practice");
              setPracticeDirty(false);
              setProductStatus("J5 complete · 已由用户选择恢复学习现场");
              setToast("已恢复练习 3 · 第 2 步");
            }}
            onResumeStudio={() => {
              setOverlay(null);
              setSurface("studio");
              setStudioConnected(true);
              setProductStatus("J5 complete · 已由用户选择恢复 Studio Project");
              setToast("已恢复 Studio · 极限概念分享");
            }}
          />
        )}
        {overlay === "settings" && (
          <SettingsModal
            onClose={() => setOverlay(null)}
            theme={theme}
            onToggleTheme={() => setTheme((current) => (current === "dark" ? "light" : "dark"))}
          />
        )}
        {overlay === "review-card" && (
          <CardReviewModal
            onClose={() => setOverlay(null)}
            onGrade={(grade, thinkingMs) => {
              setReviewDone(true);
              setOverlay(null);
              setToast(`已记录：${GRADE_LABELS[grade]}`);
              // 难度是量出来的，不是问出来的；这里只在原型评审栏显示，不进产品界面
              setProductStatus(
                `Study · 提交 grade="${grade}"，翻面耗时 ${(thinkingMs / 1000).toFixed(1)}s（难度信号来自实测，不来自自评）`,
              );
            }}
          />
        )}
        {toast && (
          <div className="toast" role="status">
            <CheckCircle2 aria-hidden="true" />
            {toast}
          </div>
        )}
      </section>
    </div>
  );
}
