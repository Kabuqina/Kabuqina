# D-1 Implementation Plan — 一等 `/study` 路由与笔记本壳

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** implement the D-1 slice of
[v0.4 笔记本前端实施设计](../specs/2026-07-10-v0.4-notebook-frontend-implementation-design.md)
(the frozen D-0 spec, hereafter **D0 §n**): a lazily-loaded first-class
`/study/:spaceId?/:page?` route with the notebook shell — top bar, space
switcher, lifecycle nav, draft count, route status states — backed by an
injectable `StudyRepository`. **No page content**: the five lifecycle pages
render placeholder surfaces only; D-2/D-3/D-4 own them.

**Slice id:** D-1 of the
[v0.4.0 development plan](2026-07-06-v0.4.0-development-plan.md).

**Tech Stack:** React 19 + react-router 7, existing kq-glass tokens, Vitest/RTL
(D-0 foundation), zero new runtime deps (NOT even `motion` — first need is D-2+).

---

## Guardrails

- **Do not start before Task 1's gate is green.** A-R2 (desktop/web rename) and
  B-1/M4 wire work are present on current main; Task 1 verifies their landed
  commits and allowed compatibility residue instead of assuming an unlanded
  dependency.
- **Shell only.** No flyleaf/plan/learn/practice/evaluate content, no
  mutations except `selectSpace`, no CodeMirror/motion/KaTeX imports, no new
  brand artwork (AskNana is text + existing icon, D0 §10).
- **Old sidebar stays fully functional.** D-1 adds an "打开学习空间" entry to
  the existing STUDY panel; it does NOT strip `StudySection` — per-capability
  demotion happens per-page in D-2+ (master plan §4). Dual-write is impossible
  in D-1 because the shell writes nothing but `selectSpace`.
- **No mock data anywhere** (D0 §5.3): missing capability renders
  `degraded/unsupported`, never demo content.
- **Chunk budget** (D0 §11): retain the historical D-0 baseline
  (1,563.48 kB / 469.81 kB gzip), but measure D-1's ≤ **5 kB** `/chat` initial
  gzip net delta against a fresh, recorded pre-D-1 build from current main;
  `StudyRoute` must be its own route chunk.
- New interactive components merge only with happy-path + failure-keeps-data +
  keyboard-only assertions (D0 §12); no source-regex-only tests for new UI.
- i18n zh + en for every string; no emoji; charter rules apply (no learning
  content in any telemetry — D-1 adds NO telemetry at all, IA events are D-5).
- Commit locally per task; do NOT push; stop for review at plan end.

---

### Task 1: D-1 开工门核对（不绿不动工）

- [x] **Step 1:** verify all five D0 §14 preconditions and record evidence in
  the progress notes:

```powershell
git log --oneline -12                    # record A-R2/B-1/M4 landed commits
git rev-parse HEAD                       # bind the pre-D-1 baseline to a commit
cd web; npm run test:components           # component runner green
npm run build -- --manifest               # fresh /chat baseline; record raw + gzip
```

  Plus: B-1 desk/Tauri wire shapes present (`cmd_study_student_state_get`
  etc. in `tauri/src/study.rs`), Style Tile canonical HTML unchanged since
  D-0 (`git log -1 -- "docs/superpowers/prototypes/Style Tile.html"`). Run the
  closing audit from `2026-07-11-a-r2-rename-plan.md` and classify every legacy
  hit against that plan's explicit allowances (core references, A-R3-reserved
  persistence names, compatibility aliases). A raw `rg "hermes"` hit count is
  evidence for review, **not** a green/red gate. If a required A-R2/B-1/M4
  commit or wire is absent, STOP here and report.

**Task 1 evidence (2026-07-11):** gate passed on `a0312b01`; A-R2 landed as
`b4c4176b` + `5e232eca`, M4/B-1 wires are present, and Style Tile remains at
`b729a107`. `npm run test:components` passed (1 file / 2 tests). Fresh pre-D-1
build: entry JS **1,564.67 kB raw / 470.20 kB gzip**, entry CSS **132.70 kB
raw / 21.52 kB gzip**; manifest generated at `dist/.vite/manifest.json`.

### Task 2: Repository 层（先于任何组件）

**Files:**
- Add: `web/src/study/repository.ts`（interface + errors + production adapter）
- Add: `web/src/study/repositoryContext.tsx`（provider + `useStudyRepository`）
- Add: `web/src/study/loadable.ts`（D0 §5.2 的 `Loadable<T>` 判别联合 + helpers）
- Add: `web/src/study/repository.test.ts`、`loadable.test.ts`（Vitest）

- [x] **Step 1:** interface 按 D0 §5.1 实现三方法起步
  （`listSpaces / selectSpace / listDrafts`），全部带 `AbortSignal`；
  production adapter 包装现有 `web/src/chat/study/study-api.ts` 的
  `cmdStudySpaces / cmdStudySpaceSelect / cmdStudyDrafts`——adapter 不新增
  Tauri 命令，只做映射与错误归一。先把 `cmdStudyDrafts` 改成
  `kind?: string` 且缺省时不注入 kind；FlashcardPanel/QuizPanel 保持显式
  传入 `flashcard_deck`/`quiz`。repository 的壳级查询必须无 kind，测试
  锁定跨类型计数，避免默认只返回 flashcard。
- [x] **Step 2:** `StudyRepositoryError` 归一 `unavailable / not-found /
  conflict / invalid / unknown`。当前 `desk_json_request` 丢弃 HTTP status，
  所以 D-1 **不得**按人类可读 detail 猜 400/404/409：仅映射后端稳定的
  error-code 前缀与 desk-not-ready/transport 拒绝；未识别值一律
  `unknown`。原始文案只保留在 `cause`，UI 永不直接渲染。若实现发现
  后端没有稳定 code，记录 typed `{status, code, detail}` bridge 为后续
  基建任务，不在 D-1 顺手扩大 Rust 合同。
- [x] **Step 3:** repository 层不缓存。明确 `AbortSignal` 语义：Tauri
  `invoke` 发出后不能真正取消，adapter 只在调用前/返回后检查 signal；
  调用方使用显式 request coordinator（generation/request id + active
  controller）决定是否提交 `Loadable`。`loadable.ts` 提供纯状态 helper，
  测试覆盖旧请求后返回、abort 后返回、快速连续切换，均不得覆盖当前
  状态（D0 §5.1）。

### Task 3: 路由注册与 canonical 解析

**Files:**
- Modify: `web/src/main.tsx`（`React.lazy` route chunk）
- Add: `web/src/study/StudyRoute.tsx`（默认导出;内部 `Routes`）
- Add: `web/src/study/routeModel.ts`（slug 解析/规范化的纯函数）
- Add: `web/src/study/routeModel.test.ts` + `StudyRoute.test.tsx`

- [x] **Step 1:** `main.tsx` 注册
  `<Route path="/study/*" element={<Suspense fallback={<BootPill/>}><StudyRoute/></Suspense>}>`，
  `const StudyRoute = lazy(() => import("./study/StudyRoute"))` —— 这是
  唯一允许触碰 `/chat` 初始 chunk 的改动。
- [x] **Step 2:** `routeModel.ts` 纯函数锁定 D0 §2.1 语义:
  - `PAGE_SLUGS = ["flyleaf","plan","learn","practice","evaluate"] as const`;
  - `/study` → 读 spaces:有 current → `replace` 到 `/study/:id/flyleaf`;
    无 space → 留在开本空态;
  - `/study/:id` → replace 到该 space 的 `flyleaf`;
  - 非法 slug → not-found 视图（"回到扉页" + "返回聊天"）,不静默跳转;
  - 未知/他人 space id → unavailable 恢复视图,**文案不区分"不存在"与
    "不属于你"**（不泄露归属,D0 §2.1）;
  - D-1 的五个 slug 均为 route-ready placeholder，space 切换保持同名
    page；仅非法 slug 进入 not-found。能力级回落留给该页迁移时定义，
    D-1 不以“尚未实现内容”为由跳回 `flyleaf`。
- [x] **Step 3:** route 测试用 MemoryRouter + fake repository 覆盖以上每条
  分支 + 后退行为（history 正常入栈,replace 只用于规范化）。

### Task 4: 壳组件（D0 §4 组件树,自上而下）

**Files:**
- Add: `web/src/study/StudyShell.tsx`、`StudyTopBar.tsx`、`SpaceSwitcher.tsx`、
  `DraftInboxButton.tsx`、`StudyLifecycleNav.tsx`、`StudyRouteStatus.tsx`、
  `pages/PlaceholderPage.tsx`
- Modify: `web/src/locales/strings.ts`（zh/en 全量新词条）
- Modify: `web/src/index.css`（`--kq-study-*` 语义别名,D0 §10:引用 Style
  Tile 已验证值,组件不写裸 hex）
- Add: 对应 `.test.tsx`

- [x] **Step 1: StudyShell + view-model。** `StudyShellVM` 只含 space 摘要、
  当前 page、draft count、可用性（D0 §5.2）;desk 不可用 → 全壳 `degraded`
  视图（说明 + "返回聊天"逃生门,不困住用户,D0 §1.3）。spaces/drafts 在
  mount、space change 以及既有 `study-learning-event` 后 revalidate；组件
  unmount 时清理 listener，事件突发仍由 generation guard 防旧值回写。
- [x] **Step 2: StudyTopBar。** BackToChat（链接 `/chat`）、SpaceSwitcher、
  DraftInboxButton、AskNanaLink（文字+现有 lucide 图标,导航 `/chat`,
  不用咖啡杯,D0 §10）。
- [x] **Step 3: SpaceSwitcher。** 使用单一 controller/选择状态与共享 option
  list；以容器尺寸（`container-type: inline-size` + ResizeObserver/等价
  hook）只挂载当前 presentation：宽容器呈现 listbox/popover，窄容器呈现
  dialog（focus trap、Escape、关闭归还焦点,D0 §9）。不同时保留两棵可
  聚焦 DOM，也不以 `window.innerWidth` 维护两套业务状态。切换采用悲观提交：
  pending 时禁用重复提交，`selectSpace` 成功后才导航到目标 space 同名
  page 并 revalidate；失败保留原 route/data，就地报错。"开新本"在 D-1
  明确为普通 `/chat` 链接并说明在旧 STUDY 面板创建，不声称深链到尚未
  存在的创建态，也不实现创建表单。
- [x] **Step 4: StudyLifecycleNav。** 链接语义（`<nav>` + `<a>`）,
  `aria-current="page"`;五页固定顺序;`640..959px` 横向可滚动,`<640px`
  保留文字可横滚,**永不折叠进 hamburger**（D0 §8）。
- [x] **Step 5: DraftInboxButton。** 无 kind 的 `listDrafts` 跨类型计数，
  VM/popover 只保留 kind→count，不保留或渲染 title/content；显示值 99+
  封顶。点击展开**只读** popover:按 kind 分组计数 + 一行说明
  "草稿审核在各分页进行（D-2 起迁入）"。不做 activate/reject（防双写,
  统一草稿箱是 D-4）。当前 endpoint 仍可能返回无界元数据：把 B-5
  增加 summary/count query 记入收口记录，不能把 99+ 显示上限误写成
  网络载荷上限。popover 支持 Escape，关闭后焦点归还触发按钮。
- [x] **Step 6: PlaceholderPage。** 每个 lifecycle page 渲染:页 `h1`
  （route 完成后 `tabIndex=-1` 聚焦,D0 §9）、一句"本页将在 D-x 迁入"
  说明、指向旧侧栏对应能力的链接（能力仍在旧处,诚实导流）。"尚未迁入"
  是 availability 状态，不套用学习数据为空时的庆祝文案；零 space 才按
  D0 §6 使用积极开本空态。无 space 时 nav 不生成带空 id 的 lifecycle
  链接。
- [x] **Step 7: 键盘与焦点验收**（组件测试断言）:纯键盘走通
  切页→切 space→开草稿 popover→回聊天;dialog trap/Escape/焦点归还;
  popover Escape/焦点归还；`aria-current` 正确迁移。D-1 不引入动画，
  因此不为 reduced-motion 写无行为可测的源码断言；实际动画首次进入
  D-2+ 时再加入 `prefers-reduced-motion` 行为测试。
- [x] **Step 8: tokens。** 只建立本切片实际使用的明/暗主题语义别名：
  `--kq-study-muted`、`--kq-study-pencil`、`--kq-study-warn`（及必要的
  foreground/hover 配对），值引用 Style Tile 已验证 token；继续排除
  paper/noise/desk 等场景 token，组件 CSS 不写裸 hex。

### Task 5: 旧面板入口 + 收尾核查

**Files:**
- Modify: `web/src/chat/WorkspacePanel.tsx`（STUDY 分支顶部加
  `OpenStudyLink`:进入 `/study`;不移除任何现有能力）
- Add: `web/src/chat/OpenStudyLink.tsx`
- Modify: `web/src/chat/chatUx.test.mjs`（断言 OpenStudyLink 存在 +
  StudySection 仍完整挂载——防 Codex 过度删除）
- Add: `web/src/chat/OpenStudyLink.test.tsx`（真实渲染的可访问性/导航测试）
- Add: `web/scripts/inspect-study-chunks.mjs`（读取 Vite manifest 的依赖图）

- [x] **Step 1:** OpenStudyLink + i18n。Vitest/RTL 真实渲染测试验证
  accessible name、`href=/study` 与键盘激活；`chatUx.test.mjs` 的源码断言
  只负责证明旧 `StudySection` 仍完整挂载，不作为新交互的唯一测试。
- [x] **Step 2: 体积门。**

```powershell
cd web
npm run build -- --manifest
node scripts/inspect-study-chunks.mjs
```

  脚本从 `.vite/manifest.json` 递归遍历 `imports/dynamicImports`，分别输出
  `/chat` 初始图和 `/study` 动态图的 raw/gzip；记录 `/chat` 相对 Task 1
  同 commit pre-D-1 基线净增 ≤ 5 kB，并保留 D-0 历史数作参照。断言存在
  独立 StudyRoute 动态入口，且 `/chat` 初始图未新增 Study shell，Study
  图不含 CodeMirror/motion/KaTeX 新副本。文件名 `rg` 只可辅助诊断，
  不作唯一证据。超预算 → 拆分或解释，不改 warning limit（D0 §11）。
- [x] **Step 3: 全量门。**

```powershell
cd web
npm run test:components; npm run test:chat-ux; npm run lint; npm run build
```

- [x] **Step 4:** 更新 D0 spec 状态行（D-1 收口记录:组件清单、chunk 数字、
  与 §2/§4 的任何偏差）;master plan 切片表 D-1 标记完成。
  Commit locally, do not push, stop for review.

---

## 状态矩阵（壳级,验收对照）

| 场景 | 期望 |
|------|------|
| desk child 不可用 | 全壳 degraded:说明 + 返回聊天;无假数据 |
| spaces 加载中 | 骨架,壳与 nav 保留,无布局跳动 |
| 零 space | 开本空态（积极文案 + 指向创建入口） |
| space 列表加载失败 | 就地错误 + 重试 + 返回聊天 |
| 快速连续切 space | 旧响应不覆盖新选择（generation 测试） |
| `selectSpace` 失败 | 保留原 route/data，就地报错，可重试 |
| 非法 page slug | not-found 视图,不静默跳转 |
| 未知/他人 space | unavailable 视图,不泄露归属 |
| 窄窗 <640px | dialog 切换器;五页文字标签横滚可达 |

## Acceptance Criteria

- `/study` 一等路由按 D0 §2.1 全语义可用,独立 lazy chunk,`/chat` 初始
  gzip 净增 ≤ 5 kB;
- 壳组件全部通过 fake-repository 组件/路由测试（happy、失败保数据、
  纯键盘、竞态旧响应四类断言）;
- 草稿计数覆盖全部 kind，壳 VM/DOM 不保留标题或学习内容；新建入口不
  冒充不存在的创建深链；
- 旧 STUDY 侧栏功能零损失,仅新增入口;写路径零重复;
- 无 mock 数据、无新 runtime 依赖、无新品牌美术、无遥测;
- i18n zh/en 完整;`--kq-study-*` 别名建立,组件无裸 hex;
- D0 spec 与 master plan 状态同步;本地提交待 review。

## Completion record（2026-07-11）

D-1 首轮壳已完成。质量门：Vitest/RTL **7 files / 20 tests**、chat UX、
lint、TypeScript 与 production build 全绿。收口 entry JS 1,567.69 kB /
471.28 kB gzip，CSS 139.03 / 22.88；相对 Task 1 fresh baseline 的初始图
gzip 合计净增约 **2.44 kB**。独立 `StudyRoute` chunk 11.00 / 3.80 kB
gzip；manifest 递归检查确认没有 CodeMirror、motion、KaTeX 新副本。
完整 drafts metadata 的无界载荷仍记录为 B-5 summary/count query 债务。
