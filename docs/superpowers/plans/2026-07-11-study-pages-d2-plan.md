# D-2 Implementation Plan — 扉页 / 计划 / 评估纵切

> **执行说明：** 本仓库当前会话未提供 `superpowers:executing-plans` 技能；
> 按既有 D-1 plan 的 task-by-task、测试先行、逐项提交纪律执行。本文是
> v0.4.0 master plan 要求的 just-in-time 实施计划。

**Goal:** 将 `/study/:spaceId/flyleaf|plan|evaluate` 从占位页升级为消费真实
B-1/M4 数据的产品页面，并在每个新写路径落地时同步撤掉旧侧栏对应写入口。
D-2 不实现学习页、练习页、统一草稿箱、场景皮肤或 D-5 遥测。

**Inputs:**

- [v0.4.0 master plan](2026-07-06-v0.4.0-development-plan.md) D-2；
- [v0.4 notebook implementation design](../specs/2026-07-10-v0.4-notebook-frontend-implementation-design.md)；
- [frontend vision](../specs/2026-07-06-desk-notebook-frontend-vision.md) 的扉页、书签、错题本和学习日志裁决；
- D-1.1 commit `c6deb980`。

**Tech Stack:** React 19 / React Router 7 / existing kq-glass tokens；Tauri 2
structured desk bridge；FastAPI trusted desktop routes；owned `hermes_core`
learning projections；Vitest/RTL + pytest。零新增 runtime dependency。

---

## Guardrails

- URL `spaceId` 是所有页面读取与 mutation 的事实来源。任何 D-2 API 都不得
  回退到后端 current space；`/study` 无参数规范化除外。
- owner 仍由 runtime 注入，Web 只能传 `spaceId`，不能传 `ownerId`。
- 不使用 mock/demo 数据填页面。缺能力显示 empty/degraded/unsupported。
- 新旧 UI 不双写：D-2 页面上线时，旧 localStorage profile editor 与
  learning-profile/path/evaluation 写入口同步退役；legacy localStorage 只保留
  读取与一次性迁移，失败不删除。
- 扉页不展示 weak points；weak points 只出现在错题本/评估证据语境。
- “继续上次”仅来自 active `learning_plan` 的首个 open item；v0.4 不伪造
  tutor checkpoint。
- 错题重试 URL 只放 `source=wrongbook` 与 opaque `activityId`，不放题目、
  答案、标题、标签或自由文本。
- 活动时间线消费 bounded safe projection，不把 activity detail、答案、note
  或学习正文批量下发给页面。
- 所有 Rust 命令使用 `{status, code, detail}` 结构化错误；Web 不解析或显示
  后端 detail。
- 页面先完成 loading / empty / error / degraded / stale、键盘、焦点与窄窗，
  再加页边视觉；无新增动效或拟物场景。
- `/chat` 初始依赖图不得新增 D-2 页面代码；记录 `/study` route chunk
  raw/gzip，不能以调高 Vite warning limit 通过。

---

### Task 1: D-2 开工门与基线

- [x] D-1.1 已提交：`c6deb980`；工作区 clean。
- [x] 用户已完成 bundle + desktop manual smoke，无阻断问题。
- [x] D-1.1：Web component 29/29、chat UX、lint、TypeScript/build、
  core/desk 11/11 通过。
- [x] B-1 core service 与 desk/Tauri commands 已存在：student state、
  evaluation、learning plan、plan item complete/skip；B-5 wrongbook bounded
  projection 已存在。
- [x] 记录接口缺口：B-1 routes/commands 默认 current space、旧 String error；
  learning activity 尚无 bounded page projection。Task 2 先补齐，再写 UI。

### Task 2: URL-scoped B-1 wire 与安全投影

**Core / Python:**

- [x] 在 `LearningStore` + `LearningExecutionContext` 增加 bounded activity
  summary page：newest-first，字段仅 `activity_id / activity_type /
  artifact_id / item_id / created_at`，返回 `count / returned / limit /
  truncated`；不得读取或返回 `detail_json`。
- [x] 新增 desk `GET /api/desk/study/activities?space_id=&limit=`。
- [x] 以下 route 全部接受并注入显式 `space_id`：student-state GET/PUT、
  context migration、evaluations list/detail、learning-plans list/items、plan item
  complete/skip、wrongbook；generic artifact detail/status 也接受 `space_id`，
  供扉页就地审核 draft。
- [x] 未知/他人 space 对外保持同一 404，不泄露归属；所有已知异常统一
  `_http_error`。

**Rust / Web API:**

- [x] 对应 Tauri commands 增加 `space_id`，切换到 `DeskBridgeError` +
  `desk_json_request_structured`；本地 id 校验失败返回 `invalid_study_id`。
- [x] `study-api.ts` 增加精确 response types 与 functions，不暴露 arbitrary
  `invoke`；所有 D-2 参数 camelCase→Tauri snake_case 由 invoke 正常映射。
- [x] `StudyRepository` 扩展 typed methods：flyleaf snapshot / legacy migrate /
  draft activate/reject / plan snapshot / plan item mutation / evaluation snapshot。
  adapter 只映射 DTO，不缓存；所有方法带 `spaceId + AbortSignal`。
- [x] Python route tests 锁定 A/B deep-link scope、bounded activity projection、
  400/404/409；Rust tests 锁定结构化 HTTP payload；repository tests 锁定
  spaceId 透传和错误归一。

### Task 3: 页面状态地基与 outlet

- [x] `PlaceholderPage` 改为 `StudyPageOutlet`：flyleaf/plan/evaluate 渲染真实
  页面；learn/practice 继续诚实占位。
- [x] 每页使用独立 request coordinator；mount、space change 与
  `study-learning-event` revalidate；旧响应不得覆盖新 space。
- [x] 首次 loading 显示页面骨架；refresh 保留 previous data；refresh error
  显示 stale banner + retry，不卸载整页。
- [x] 页面 route 完成后焦点落 `h1[tabIndex=-1]`；错误/空态均保留返回聊天
  与 AskNana 逃生门。
- [x] 建立 D-2 实际使用的 `--kq-study-*` 语义 token/CSS；组件不写裸 hex，
  200% zoom 与 `<640px` 单列布局不横向溢出。

### Task 4: FlyleafPage — 扉页

- [x] 加载 explicit-space active student state + newest student-state draft。
  active 用 ink 语义，draft 用 pencil 语义；任何 weak-point 字段都不渲染。
- [x] active 字段只呈现可编辑自我设定语义：course、goals、preferences、
  constraints、progress notes、current stage、next adjustment；空字段不伪造。
- [x] draft 夹页提供“落墨/擦掉”：使用 generic artifact status，成功后 patch
  view-model 再后台 revalidate；冲突以后端状态为准并解释。
- [x] 首次进入检测 legacy `kabuqina.study.context.v1`：有内容时调用显式
  space context migration；成功 revalidate，失败保留 localStorage 并显示
  非阻断提示。不得在页面加载时清除 legacy 数据。
- [x] empty state 引导返回聊天请小娜一起填写；不新建第二套自由表单。
- [x] 组件测试覆盖 active/draft、确认/拒绝、migration success/failure keeps
  legacy、无 weak points、keyboard-only 与 stale refresh。

### Task 5: PlanPage — 计划与书签

- [x] 加载 explicit-space active plans，按 `updated_at + artifact_id` 选择最新
  current plan，再加载其 materialized items。
- [x] 页面显示 current phase、最近阶段和 items；首个 `status=open` item 是
  唯一“继续上次”书签来源，点击滚动/聚焦该 item，不伪造 checkpoint。
- [x] open item 提供完成/跳过；mutation pending 只锁当前 item，成功 patch
  当前 VM 并 revalidate，失败保留原数据并显示可重试错误。
- [x] completed/skipped 只读展示，activity 由 core service 现有写路径产生；
  UI 不直接写 activity。
- [x] empty state 提供 AskNana 创建计划入口；无 active plan 时不读取 draft
  计划正文（D-4 统一草稿箱负责）。
- [x] 测试覆盖 current-plan 选择、resume focus、complete/skip、重复/冲突失败、
  快速切 space、empty/stale 与纯键盘。

### Task 6: EvaluatePage — 错题本 / 最近评估 / 学习日志

- [x] 并行加载 explicit-space wrongbook bounded projection、active evaluation
  summaries + newest detail、activity summary page；任何一块失败只降级该块。
- [x] 错题卡只显示 score/max/percent、weak tags 与时间；不显示答案、response、
  prompt 或任意 activity detail。
- [x] “再试一次”链接固定为
  `/study/:spaceId/practice?source=wrongbook&activityId=<opaque-id>`；测试断言
  URL 不含学习内容。
- [x] 最近评估展示 observations / suggestions；weak points 与错题证据同页但
  不回流扉页。
- [x] 学习日志按 activity type + timestamp 形成见证式只读时间线，不下判断；
  未知 activity type 使用中性 fallback，不渲染 detail。
- [x] 测试覆盖三块独立 loading/error/empty、bounded/truncated、retry link、
  content exclusion、窄窗与 keyboard navigation。

### Task 7: 旧侧栏逐页退役与双写审计

- [x] `StudySection` 删除 profile edit modal、save/reset localStorage 写路径；
  profile card 改为指向 `/study` 的只读兼容摘要。
- [x] 移除旧 `learningProfile / learningPath / learningEvaluation` 快捷写入口；
  新页面的 AskNana link 是唯一入口，其他 D-3/D-4 actions 保留。
- [x] 旧 context 仍可只读注入剩余 prompt，直到 D-5；`startAction` 不再执行
  无变化的 `saveStudyContext`。
- [x] 更新 `chatUx.test.mjs`：断言旧 editor/write actions 已退役、剩余
  StudySection/FlashcardPanel/QuizPanel 未被越界删除。
- [x] 全仓 `rg` 双写审计并把残留分类写入 completion record。

### Task 8: 质量门、体积与收口

- [x] Web：D-2 component tests + full `test:components` + `test:chat-ux` + lint +
  production build。
- [x] Python：D-2 route tests、M4/M6 regression、core activity projection tests。
- [x] Rust：study bridge unit tests + `cargo test` relevant target；必要时
  `cargo check`。
- [x] 记录 build manifest：`/chat` initial raw/gzip、StudyRoute/D-2 chunks；
  确认 `/chat` 初始依赖图未新增页面代码。
- [x] 更新 D-0 spec 与 master plan D-2 状态、测试数字、已知降级；

## Completion record（2026-07-11）

D-2 automated implementation gate passed. Web: **10 files / 43 tests**, chat UX,
lint, TypeScript, manifest build；Python M4/M6/core: **13 tests**；Rust：offline
`cargo check` 与 study bridge validation test。Build：initial graph **1,711.14 kB
raw / 495.07 kB gzip**，StudyRoute **29.54 / 7.48 kB gzip**。旧侧栏仍保留
D-3/D-4 的 Flashcard/Quiz 与知识/资源/辅导/安全入口；profile editor、
learningProfile、learningPath、learningEvaluation 写入口和 `startAction` 的
legacy context 回写均已移除。desktop bundle/visual smoke 作为本轮集成烟测。
  `git diff --check`，本地提交，不 push。

---

## Acceptance Criteria

- 三页全部消费真实、owner+URL-space scoped 数据；A/B deep-link 不串数据。
- 扉页 active/draft 语义正确，legacy migration 失败不丢数据，weak points 永不
  出现在扉页。
- 计划完成/跳过只经 core service 写 activity；“继续上次”只指向首个 open
  current-plan item。
- 评估页错题、评估、时间线均 bounded；retry URL 与 DOM 不泄露答案/正文。
- 新旧 UI 对 profile/plan/evaluation 无双写；旧 editor 和三个旧写入口退役。
- loading/empty/error/degraded/stale、键盘、焦点、窄窗、200% zoom 有真实
  component assertions。
- 无 mock 数据、无新 runtime dependency、无 D-3/D-4/D-5 越界。
- Web/Python/Rust 相关门全绿，`/chat` 初始依赖图无 D-2 页面代码。
