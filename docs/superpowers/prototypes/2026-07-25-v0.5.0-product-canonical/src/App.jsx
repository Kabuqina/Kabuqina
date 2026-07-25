import { useEffect, useMemo, useRef, useState } from "react";
import {
  Activity,
  AlertCircle,
  ArrowLeft,
  ArrowRight,
  Book,
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
  Layers3,
  Library,
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
  { id: "J4", label: "转交到 Studio", detail: "Study → 来源快照 → Studio Project" },
  { id: "J5", label: "恢复现场", detail: "Study + Studio → 重启 → 安全恢复" },
];

const COURSE = {
  id: "calculus",
  title: "高等数学",
  subtitle: "极限与连续",
  savedAt: "今天 13:42",
};

const STUDY_PAGES = [
  { id: "flyleaf", label: "扉页" },
  { id: "plan", label: "计划" },
  { id: "learn", label: "学习" },
  { id: "practice", label: "练习" },
  { id: "evaluate", label: "评估" },
];

const INITIAL_PLAN_ITEMS = [
  { id: "p1", title: "理解极限与未定式的区别", meta: "本周 · 当前阶段", status: "active" },
  { id: "p2", title: "完成极限基础练习 1–6", meta: "4 / 6 已完成", status: "active" },
  { id: "p3", title: "整理一次错题回练", meta: "等待练习证据", status: "pending" },
];

const INITIAL_ANSWER = "代入后分子和分母同时为 0，所以需要先变形。";

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
        <button type="button" aria-label="设置" onClick={onOpenSettings}>
          <AppIcon icon={Settings} size={21} />
        </button>
      </div>
    </header>
  );
}

function CourseBooks({ hasCourse, onCreateCourse, onSelectCourse }) {
  return (
    <aside className="desk-rail desk-rail--books" aria-label="课程与材料">
      <section className="desk-card course-card">
        <h2>
          <AppIcon icon={Library} />
          我的课程本
        </h2>
        <p>换课就是换一本本子。</p>
        <div className="course-list">
          {hasCourse && (
            <>
              <button type="button" aria-current="true" onClick={onSelectCourse}>
                <AppIcon icon={Book} />
                高等数学
              </button>
              <button type="button">
                <AppIcon icon={Book} />
                大学物理
              </button>
            </>
          )}
        </div>
        <button className="secondary-action" type="button" onClick={onCreateCourse}>
          <AppIcon icon={Plus} />
          开新本
        </button>
      </section>
      <section className="desk-card material-card">
        <h2>
          <AppIcon icon={Layers3} />
          本课材料
        </h2>
        {hasCourse ? (
          <>
            <p>平放在这本高数笔记本旁。</p>
            <button type="button">教材 §2.3</button>
            <button type="button">习题集 p.41</button>
          </>
        ) : (
          <p>建课后，材料会跟着课程归位。</p>
        )}
      </section>
    </aside>
  );
}

function FlyleafPage({ draftVisible, onInk, onErase }) {
  return (
    <div className="lifecycle-page lifecycle-page--flyleaf">
      <header className="page-intro">
        <span className="eyebrow">本课扉页 · 我的学习设定</span>
        <h2>这本课程本属于我</h2>
        <p>这里只保存课程目标、偏好与约束；薄弱点和系统设置不会写进扉页。</p>
      </header>
      {draftVisible && (
        <section className="study-sheet study-sheet--pencil">
          <header>
            <span>
              <PencilLine aria-hidden="true" />
              铅笔草稿
            </span>
            <StatusPill tone="warning">待确认</StatusPill>
          </header>
          <h3>更新后的学习设定</h3>
          <dl className="flyleaf-rows">
            <div><dt>目标</dt><dd>能解释极限的核心概念，并独立完成基础题。</dd></div>
            <div><dt>偏好</dt><dd>先看一个直观例子，再自己动手推导。</dd></div>
            <div><dt>约束</dt><dd>工作日每天 45 分钟，不用一次学完。</dd></div>
          </dl>
          <div className="inline-actions">
            <button className="primary-action" type="button" onClick={onInk}>
              <AppIcon icon={Check} />
              落墨生效
            </button>
            <button type="button" onClick={onErase}>擦除草稿</button>
          </div>
        </section>
      )}
      <section className="study-sheet study-sheet--ink">
        <header>
          <span>
            <BookOpen aria-hidden="true" />
            已落墨
          </span>
          <StatusPill tone="success">Active</StatusPill>
        </header>
        <h3>高等数学 · 极限与连续</h3>
        <dl className="flyleaf-rows">
          <div><dt>本课目标</dt><dd>理解极限、导数与积分，并完成本学期练习。</dd></div>
          <div><dt>当前阶段</dt><dd>第 2 周 · 极限与未定式</dd></div>
          <div><dt>下一调整</dt><dd>增加“为什么不能直接代入”的解释练习。</dd></div>
        </dl>
      </section>
    </div>
  );
}

function PlanPage({ items, onUpdate, onContinue }) {
  const completed = items.filter((item) => item.status === "done").length;
  return (
    <div className="lifecycle-page lifecycle-page--plan">
      <header className="page-intro">
        <span className="eyebrow">Active Plan · 第 2 周</span>
        <h2>极限与未定式</h2>
        <p>计划只描述下一步学习动作；完成和跳过会成为活动证据，不伪装成草稿。</p>
      </header>
      <button className="plan-bookmark" type="button" onClick={onContinue}>
        <Bookmark aria-hidden="true" />
        <span>
          <strong>继续上次：练习 3 · 第 2 步</strong>
          <small>解释为什么 0/0 不是极限答案</small>
        </span>
        <ArrowRight aria-hidden="true" />
      </button>
      <section className="study-sheet">
        <header>
          <span><Clock3 aria-hidden="true" />本周计划</span>
          <StatusPill tone="info">{completed} / {items.length} 完成</StatusPill>
        </header>
        <div className="plan-list">
          {items.map((item) => (
            <article key={item.id} data-status={item.status}>
              <span className="plan-state">
                {item.status === "done" ? <Check aria-hidden="true" /> : <Circle aria-hidden="true" />}
              </span>
              <div>
                <strong>{item.title}</strong>
                <small>{item.status === "skipped" ? "已调整 · 不计为完成" : item.meta}</small>
              </div>
              {item.status === "active" || item.status === "pending" ? (
                <div className="plan-actions">
                  <button type="button" onClick={() => onUpdate(item.id, "done")}>完成</button>
                  <button type="button" onClick={() => onUpdate(item.id, "skipped")}>跳过</button>
                </div>
              ) : (
                <StatusPill tone={item.status === "done" ? "success" : "prototype"}>
                  {item.status === "done" ? "已完成" : "已跳过"}
                </StatusPill>
              )}
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}

function LearnPage({ draftSaved, onOpenDraft, onContinue }) {
  return (
    <div className="lifecycle-page lifecycle-page--learn">
      <header className="page-intro">
        <span className="eyebrow">知识正文 · 来源可追溯</span>
        <h2>从“0/0 是什么”继续</h2>
        <p>学习页承接知识库、资源包和辅导笔记；它帮助理解，但不判分、不接管练习答案。</p>
      </header>
      <section className="learn-concept">
        <span className="concept-index">01</span>
        <div>
          <span className="eyebrow">知识点 · 教材 §2.3</span>
          <h3>0/0 是未定式，不是一个确定的数</h3>
          <p>直接代入只说明原式还需要继续分析。不同函数都可能得到 0/0，但它们的极限可以不同。</p>
        </div>
      </section>
      <div className="learn-grid">
        <section className="study-sheet">
          <header><span><Layers3 aria-hidden="true" />课程资源</span></header>
          <button className="resource-row" type="button">
            <FileText aria-hidden="true" />
            <span><strong>教材 §2.3 · 极限的运算法则</strong><small>可信来源 · 本地材料</small></span>
          </button>
          <button className="resource-row" type="button">
            <FileText aria-hidden="true" />
            <span><strong>例题：可约因子的极限</strong><small>资源包 · 3 个逐步例子</small></span>
          </button>
        </section>
        <section className="study-sheet">
          <header><span><PencilLine aria-hidden="true" />辅导笔记</span></header>
          {draftSaved ? (
            <button className="draft-row" type="button" onClick={onOpenDraft}>
              <span><strong>“0/0 未定式”辅导笔记</strong><small>待审核 · 不改变课程真值</small></span>
              <StatusPill tone="warning">草稿</StatusPill>
            </button>
          ) : (
            <p className="quiet-copy">还没有待审核笔记。普通 Chat 内容不会自动写进课程。</p>
          )}
        </section>
      </div>
      <button className="primary-action" type="button" onClick={onContinue}>
        去练习中验证理解
        <AppIcon icon={ArrowRight} />
      </button>
    </div>
  );
}

function EvaluatePage({ onRetry }) {
  return (
    <div className="lifecycle-page lifecycle-page--evaluate">
      <header className="page-intro">
        <span className="eyebrow">有界学习证据</span>
        <h2>评估与回访</h2>
        <p>这里只展示能回到来源的学习证据，不给学习者贴人格或能力标签。</p>
      </header>
      <div className="evaluation-summary">
        <section>
          <span>最近评估</span>
          <strong>基础概念基本达标</strong>
          <p>证据来自 6 次练习、1 次卡片复习和最近一次解释题。</p>
        </section>
        <section>
          <span>下一调整</span>
          <strong>继续练习“解释理由”</strong>
          <p>先修正未定式的表述，再进入更复杂的化简方法。</p>
        </section>
      </div>
      <section className="study-sheet">
        <header>
          <span><RotateCcw aria-hidden="true" />错题本</span>
          <StatusPill tone="warning">2 项待回访</StatusPill>
        </header>
        <article className="wrongbook-row">
          <div>
            <strong>0/0 能不能直接作为极限值？</strong>
            <small>来源：练习 3 · 第 2 步 · 今天 13:42</small>
          </div>
          <button className="primary-action" type="button" onClick={onRetry}>再试一次</button>
        </article>
        <article className="wrongbook-row">
          <div>
            <strong>什么时候可以先约分再求极限？</strong>
            <small>来源：练习 2 · 昨天</small>
          </div>
          <button type="button" onClick={onRetry}>打开来源</button>
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
  onOpenWork,
  flyleafDraftVisible,
  onInkFlyleaf,
  onEraseFlyleaf,
  planItems,
  onUpdatePlan,
  draftSaved,
  onOpenDraft,
  onRetryWrongbook,
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
          <h1>{COURSE.title} · 极限</h1>
          <p>我的课程笔记本 · 最近保存 13:42</p>
        </div>
        <button className="bookmark-card" type="button" onClick={onContinue}>
          <AppIcon icon={Bookmark} />
          <span>
            <strong>继续：练习 3 · 第 2 步</strong>
            <small>解释为什么不能直接代入</small>
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
          <PlanPage items={planItems} onUpdate={onUpdatePlan} onContinue={onContinue} />
        )}
        {studyPage === "learn" && (
          <LearnPage
            draftSaved={draftSaved}
            onOpenDraft={onOpenDraft}
            onContinue={onContinue}
          />
        )}
        {isPractice && (
          <div className="practice-sheet">
            <span className="eyebrow">练习 3 · 第 2 步</span>
            <h2>解释为什么不能直接代入</h2>
            <p className="completion-standard">
              <strong>完成标准：</strong>
              区分“得到 0/0”与“得到极限值”，并指出下一步需要继续分析。
            </p>
            <p>
              计算 <strong>lim (x² − 1) / (x − 1)，x → 1</strong>。为什么不能把直接代入得到的
              0/0 当作答案？
            </p>
            {studyState === "returned" && (
              <aside className="margin-note">
                <Coffee aria-hidden="true" />
                <div>
                  <strong>小娜留在页边的提示</strong>
                  <p>先补清“0/0 是未定式，不是极限值”。这只是建议，不会写进你的答案。</p>
                </div>
              </aside>
            )}
            <label className="answer-field">
              <span>
                <strong>我的答案</strong>
                <small>{studyState === "returned" ? "原答案未改写" : "我的草稿"}</small>
              </span>
              <textarea value={answer} onChange={(event) => onAnswer(event.target.value)} />
            </label>
            <p className="save-status">
              <ShieldCheck size={16} aria-hidden="true" />
              {studyState === "returned"
                ? "已准确返回：原答案、反馈与返回位置都在原位"
                : "草稿已保存在这本笔记本中"}
            </p>
            {studyState === "returned" ? (
              <section className="feedback-card" aria-label="检查结果">
                <header>
                  <strong>页边批注 · 需要修改</strong>
                  <StatusPill tone="warning">还差一步</StatusPill>
                </header>
                <div className="feedback-grid">
                  <p>
                    <Check size={16} aria-hidden="true" />
                    <span>
                      <strong>已经说明清楚</strong>
                      代入后分子、分母都趋近 0。
                    </span>
                  </p>
                  <p>
                    <Circle size={16} aria-hidden="true" />
                    <span>
                      <strong>还差一步</strong>
                      说明 0/0 是未定式，不是极限值。
                    </span>
                  </p>
                  <p>
                    <ArrowRight size={16} aria-hidden="true" />
                    <span>
                      <strong>接下来试试</strong>
                      把这句话补进解释，再检查一次。
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
      <button className="send-studio-tab" type="button" onClick={onOpenWork}>
        <AppIcon icon={ArrowRight} />
        <span>选择内容，发送到 Studio</span>
      </button>
    </section>
  );
}

function ReviewCards({ hasCourse, onReview, reviewDone, onAsk }) {
  return (
    <aside className="desk-rail desk-rail--review" aria-label="复习卡片与小娜">
      <section className="desk-card review-card">
        <h2>
          <AppIcon icon={Inbox} />
          本课卡片盒
        </h2>
        <strong className="due-number">{reviewDone ? "5" : "6"}</strong>
        <p>张今日到期 · 不打断当前练习</p>
        <button type="button" onClick={onReview} disabled={!hasCourse}>
          {reviewDone ? "已复习 1 张" : "到安全节点后复习"}
        </button>
      </section>
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

function StudyDesk(props) {
  return (
    <main className="desk-scene" data-testid="study-desk">
      <CourseBooks
        hasCourse={props.hasCourse}
        onCreateCourse={props.onCreateCourse}
        onSelectCourse={() => props.onToast("已打开高等数学课程本")}
      />
      <StudyNotebook {...props} />
      <ReviewCards
        hasCourse={props.hasCourse}
        onReview={props.onReview}
        reviewDone={props.reviewDone}
        onAsk={props.onAsk}
      />
      <nav className="narrow-desk-tools" aria-label="窄窗书桌工具">
        <button type="button" onClick={props.onCreateCourse}>
          <AppIcon icon={Library} />
          课程
        </button>
        <button type="button" onClick={props.onReview}>
          <AppIcon icon={Inbox} />
          卡片
        </button>
        <button type="button" onClick={props.onOpenWork}>
          <AppIcon icon={ArrowRight} />
          Studio
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
  draftSaved,
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
          messages.map((message, index) => (
            <article
              className={`message message--${message.role}`}
              key={`${message.role}-${index}`}
            >
              <div className="message-author">{message.role === "user" ? "我" : "小娜"}</div>
              <p>{message.text}</p>
              {message.meta && <small>{message.meta}</small>}
              {message.canSave && (
                <div className="message-actions">
                  <button type="button" onClick={onSaveDraft} disabled={draftSaved}>
                    <AppIcon icon={BookOpen} />
                    {draftSaved ? "已生成待审核草稿" : "保存到课程"}
                  </button>
                  <button type="button" onClick={onOpenCreate}>
                    <AppIcon icon={ArrowRight} />
                    发送到 Studio
                  </button>
                </div>
              )}
            </article>
          ))
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
}) {
  return (
    <main className="studio-desk" data-testid="studio-desk">
      <aside className="studio-rail studio-rail--projects" aria-label="Studio 项目册">
        <header>
          <div>
            <span className="eyebrow">输出与表达</span>
            <h2>我的项目册</h2>
          </div>
          <button type="button" aria-label="新建 Studio Project" onClick={onNewProject}>
            <AppIcon icon={Plus} />
          </button>
        </header>
        {connected ? (
          <button className="studio-project-row is-active" type="button">
            <span className="session-icon session-icon--studio">
              <FolderOpen aria-hidden="true" />
            </span>
            <span>
              <strong>极限概念分享</strong>
              <small>来源 2 项 · Brief 待澄清</small>
            </span>
          </button>
        ) : (
          <p className="studio-rail-empty">还没有项目。可以新建空项目，或从 Study 显式转交材料。</p>
        )}
        <section className="studio-boundary-note">
          <ShieldCheck aria-hidden="true" />
          <p>
            <strong>Studio 不等于 PPT。</strong>
            具体工作面和输出形式将在整体布局冻结后单独设计。
          </p>
        </section>
      </aside>

      <section className="studio-workspace" aria-label="当前 Studio Project">
        <header className="studio-workspace__header">
          <div>
            <span className="eyebrow">Studio · 输出域</span>
            <h1>{connected ? "极限概念分享" : "建立一个表达项目"}</h1>
            <p>
              {connected
                ? "先确定受众、目的和来源，再决定最终表达形式。"
                : "Studio 以 Project 为容器，不以某一种文件格式为入口。"}
            </p>
          </div>
          <StatusPill tone="prototype">整体布局阶段</StatusPill>
        </header>

        {connected ? (
          <div className="studio-overview">
            <section className="studio-brief-card">
              <span className="eyebrow">Project Brief</span>
              <h2>把“0/0 是未定式”讲给刚接触极限的同学</h2>
              <div className="studio-brief-grid">
                <p>
                  <span>受众</span>
                  <strong>刚开始学习极限的同学</strong>
                </p>
                <p>
                  <span>目标</span>
                  <strong>理解为什么 0/0 只是继续分析的信号</strong>
                </p>
                <p>
                  <span>形式</span>
                  <strong>尚未决定</strong>
                </p>
              </div>
            </section>
            <section className="studio-stage-card">
              <header>
                <div>
                  <span className="eyebrow">当前阶段</span>
                  <h2>澄清表达目标</h2>
                </div>
                <StatusPill tone="info">下一步</StatusPill>
              </header>
              <p>
                当前只有来源快照和初始目标。先与小娜梳理受众、结构与完成标准，不提前选择 PPT、
                文档或其他工具。
              </p>
              <div className="inline-actions">
                <button className="primary-action" type="button" onClick={onOpenChat}>
                  <AppIcon icon={MessageCircle} />
                  与小娜梳理
                </button>
                <button type="button" onClick={() => onToast("Studio 详细工具将在整体布局冻结后设计")}>
                  查看项目边界
                </button>
              </div>
            </section>
          </div>
        ) : (
          <div className="studio-empty">
            <FolderOpen aria-hidden="true" />
            <span className="eyebrow">独立输出空间</span>
            <h2>项目从表达目标开始，不从文件格式开始</h2>
            <p>
              你可以建立空项目，也可以把 Study 中明确选择的材料、笔记或学习记录作为只读来源快照发送过来。
            </p>
            <div className="inline-actions">
              <button className="primary-action" type="button" onClick={onNewProject}>
                <AppIcon icon={Plus} />
                新建项目
              </button>
              <button type="button" onClick={onOpenTransfer}>
                <AppIcon icon={ArrowLeft} />
                从 Study 选择来源
              </button>
            </div>
          </div>
        )}
      </section>

      <aside className="studio-rail studio-rail--sources" aria-label="Studio 来源与连接">
        <section className="desk-card">
          <h2>
            <AppIcon icon={Layers3} />
            来源快照
          </h2>
          {connected ? (
            <>
              <button type="button" onClick={onReturnSource}>
                当前练习与反馈
              </button>
              <button type="button" onClick={onReturnSource}>
                教材 §2.3
              </button>
              <p>来自高等数学 · 可返回原位置</p>
            </>
          ) : (
            <p>来源由用户显式选择；Studio 不读取隐式 current course。</p>
          )}
        </section>
        <section className="desk-card studio-write-boundary">
          <h2>
            <AppIcon icon={ShieldCheck} />
            写入边界
          </h2>
          <p>Studio 的项目、版本和交付物不会修改 Study 的掌握度、计划或练习。</p>
        </section>
        <button
          className="cup-anchor studio-cup-anchor"
          type="button"
          aria-label="碰杯问小娜，讨论当前 Studio Project"
          onClick={onOpenChat}
        >
          <span>
            <Coffee size={25} aria-hidden="true" />
          </span>
          <strong>碰杯问小娜</strong>
          <small>{connected ? "一起梳理这个 Project" : "先聊清表达目标"}</small>
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

function LeavePracticeModal({ destination, onStay, onLeave }) {
  const label = STUDY_PAGES.find((page) => page.id === destination)?.label ?? "其他分页";
  return (
    <ModalShell title="这一步还有未提交修改" eyebrow="练习 · 离页保护" onClose={onStay}>
      <p className="modal-lead">
        你刚修改的答案仍是本页草稿。直接前往“{label}”会放弃这次未提交修改，但不会删除已经保存的练习记录。
      </p>
      <aside className="honest-note">
        <ShieldCheck aria-hidden="true" />
        <p>
          <strong>Chat 和 Studio 会保留当前页与草稿。</strong>
          只有切换课程或生命周期分页时，才需要你决定是否放弃修改。
        </p>
      </aside>
      <div className="modal-actions">
        <button type="button" onClick={onStay}>留在练习</button>
        <button className="danger-action" type="button" onClick={onLeave}>
          放弃修改并前往“{label}”
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

function DraftReviewModal({ onClose, onAccept }) {
  return (
    <ModalShell title="审核后再保存到课程" eyebrow="J3 · Chat → Study" onClose={onClose} wide>
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
          <label>
            <span>保存到</span>
            <select defaultValue="calculus">
              <option value="calculus">高等数学</option>
              <option value="physics">大学物理</option>
            </select>
          </label>
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
    <ModalShell title="发送到 Studio" eyebrow="J4 · 显式跨域连接" onClose={onClose} wide>
      {step === "select" ? (
        <>
          <div className="stepper">
            <strong>1 选择来源</strong>
            <span>2 审核快照</span>
            <span>3 打开 Project</span>
          </div>
          <div className="transfer-grid">
            <section>
              <h3>从 Study 选择什么</h3>
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
                    <small>
                      {origin === "chat"
                        ? "普通 Chat · 未绑定课程或项目"
                        : "高等数学 · Study 真值保持不变"}
                    </small>
                  </span>
                </label>
              ))}
            </section>
            <section>
              <h3>发送到哪个 Project</h3>
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
                  <small>已有 Project · Brief 待澄清</small>
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
                  <strong>新建 Project</strong>
                  <small>只建立项目容器，不预选输出格式</small>
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
              审核来源快照
              <AppIcon icon={ArrowRight} />
            </button>
          </div>
        </>
      ) : (
        <>
          <div className="stepper">
            <span>1 已选来源</span>
            <strong>2 审核快照</strong>
            <span>3 打开 Project</span>
          </div>
          <section className="snapshot-review">
            <div>
              <span>来源</span>
              <strong>{selected.join("、")}</strong>
            </div>
            <div>
              <span>目标</span>
              <strong>{target === "existing" ? "Studio · 极限概念分享" : "Studio · 新 Project"}</strong>
            </div>
            <div>
              <span>传递方式</span>
              <strong>只读 SourceSnapshot · 带 revision 与返回位置</strong>
            </div>
            <div>
              <span>写入边界</span>
              <strong>不修改 Study 原对象，不改变掌握度或计划完成度</strong>
            </div>
          </section>
          <aside className="honest-note">
            <ShieldCheck aria-hidden="true" />
            <p>
              <strong>这不是“生成 PPT”。</strong>
              本轮只建立 Study 与 Studio 的领域连接；Studio 内部工作面将在整体布局冻结后设计。
            </p>
          </aside>
          <div className="modal-actions">
            <button type="button" onClick={() => setStep("select")}>
              返回修改
            </button>
            <button className="primary-action" type="button" onClick={onAccept}>
              创建快照并打开 Studio
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
                <small>{studioConnected ? "来源快照已保存 · Brief 待澄清" : "来源转交等待确认"}</small>
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
                <small>Studio Project · 来源 2 项</small>
              </span>
              <StatusPill tone="prototype">布局阶段</StatusPill>
            </button>
          ) : (
            <p className="panel-empty">Studio Project 会与学习活动分开显示。</p>
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
            <small>来源快照已保存 · Project 工作面可恢复</small>
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

function SettingsModal({ onClose }) {
  return (
    <ModalShell title="设置" eyebrow="诚实的能力状态" onClose={onClose}>
      <section className="settings-list">
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
  return (
    <ModalShell title="到安全节点后复习" eyebrow="本课卡片盒" onClose={onClose}>
      <section className="flashcard">
        <span>高等数学 · 极限</span>
        <h3>为什么 0/0 不能直接当作极限值？</h3>
        {revealed ? (
          <p>
            因为 0/0 是未定式：不同函数都可能在代入时得到 0/0，但极限结果可能不同，需要继续分析。
          </p>
        ) : (
          <button className="primary-action" type="button" onClick={() => setRevealed(true)}>
            显示答案
          </button>
        )}
      </section>
      {revealed && (
        <div className="grade-grid">
          {["1 忘了", "2 困难", "3 记得", "4 熟练"].map((grade) => (
            <button type="button" key={grade} onClick={() => onGrade(grade)}>
              {grade}
            </button>
          ))}
        </div>
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
  const [planItems, setPlanItems] = useState(INITIAL_PLAN_ITEMS);
  const [chatKind, setChatKind] = useState("general");
  const [activeChatSession, setActiveChatSession] = useState("new");
  const [chatHistoryOpen, setChatHistoryOpen] = useState(false);
  const [contextChat, setContextChat] = useState(null);
  const [chatDraft, setChatDraft] = useState("");
  const [overlay, setOverlay] = useState(null);
  const [draftSaved, setDraftSaved] = useState(false);
  const [draftActivated, setDraftActivated] = useState(false);
  const [reviewDone, setReviewDone] = useState(false);
  const [transferStep, setTransferStep] = useState("select");
  const [studioConnected, setStudioConnected] = useState(false);
  const [transferOrigin, setTransferOrigin] = useState("study");
  const [toast, setToast] = useState("");
  const [productStatus, setProductStatus] = useState(
    "J2 ready · 书桌 → 课程 Chat → 精确返回",
  );

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
      setSurface("study");
      setStudyState("overview");
      setStudyPage("learn");
      setTransferStep("select");
      setStudioConnected(false);
      setTransferOrigin("study");
      setOverlay("studio-transfer");
      setProductStatus("J4 ready · Study 选择来源 → 审核快照 → Studio Project");
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

  const openDraftReview = () => {
    if (chatKind === "course") {
      setToast("课程对话已经有明确上下文，无需重新绑定");
      return;
    }
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
            onOpenWork={() => openStudioTransfer("study")}
            onReview={() => setOverlay("review-card")}
            reviewDone={reviewDone}
            flyleafDraftVisible={flyleafDraftVisible}
            onInkFlyleaf={() => {
              setFlyleafDraftVisible(false);
              setToast("学习设定已落墨生效");
            }}
            onEraseFlyleaf={() => {
              setFlyleafDraftVisible(false);
              setToast("铅笔草稿已擦除，原设定保持不变");
            }}
            planItems={planItems}
            onUpdatePlan={updatePlanItem}
            draftSaved={draftSaved && !draftActivated}
            onOpenDraft={openDraftFromActivity}
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
              setToast("已建立 Studio Project");
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
            draftSaved={draftSaved}
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
              setToast(`已放弃未提交修改并前往${STUDY_PAGES.find((page) => page.id === destination)?.label ?? "课程"}页`);
            }}
          />
        )}
        {overlay === "new-course" && (
          <NewCourseModal onClose={() => setOverlay(null)} onCreate={createCourse} />
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
          <DraftReviewModal onClose={() => setOverlay(null)} onAccept={acceptDraft} />
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
        {overlay === "settings" && <SettingsModal onClose={() => setOverlay(null)} />}
        {overlay === "review-card" && (
          <CardReviewModal
            onClose={() => setOverlay(null)}
            onGrade={(grade) => {
              setReviewDone(true);
              setOverlay(null);
              setToast(`已记录：${grade}`);
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
