# D-5 Implementation Plan — 集成观测、旧面退役与 WebView2 收口

> 日期：2026-07-16
> 状态：**已完成（2026-07-17）**；旧 Study localStorage 的 installed-NSIS 升级专测由 owner 明确接受降级，未伪记通过
> 起始基线：`codex/study-d4@fcc21cab`
> 集成基线：`main@3b85a85a`（A-R3 最终 review 已收口）
> 工作分支：`codex/study-d5`
> 合并记录：D4→D5 十二提交链已 fast-forward 合入 `main@fc1f9e5a`
> 安全指针：`codex/study-d5-pre-ar3@2fbe9e3a`；`codex/study-d5-pre-final-ar3@a71de2e7`
> 正式依赖：D-2、D-3、D-4、A-R3 已完成；D-5 代码、自动门、runtime verifier 与当前数据 installed-WebView 轮已收口

## 0. 实施与集成记录（2026-07-16）

- Transport Gate 选择 §5.4 方案 1：typed/injected sink + 本机 coarse aggregate；
  Settings 明示 opt-in，默认关闭，不新增 Tauri/network endpoint。关闭时清除本机计数，
  sink throw/reject 均 fail-open。IA 与 H5 `UsageEvent` 无 import/transport 依赖。
- 开工基线在独立 worktree 记录为 Web components `19 files / 80 tests`；lint 与
  production build 沿用 D4 review 的通过状态。D5 未接触 dirty main/A-R3 index。
- pre-A-R3 Web 自动门：components `21 files / 95 tests`（page-view 用例在 StrictMode 下运行，
  并覆盖 learning-event revalidate 去重）、chat UX、capture-index、knowledge-points、
  ESLint、`tsc --noEmit` 与 Vite production build 通过。
- manifest chunk 审计通过：initial `1,698,439 raw / 491,140 gzip` bytes；StudyRoute own
  `77,558 raw / 18,366 gzip` bytes。StudyRoute 仍是 dynamic entry，CodeMirror/KaTeX 未
  进入其基础 graph；未提高 warning limit。
- legacy flashcard/quiz migration 的成功、幂等、capture 去重、failure export/status
  证据共 `5 passed`。完整 Web stores/learning helpers 已物理删除；Python migration
  diagnostics、failure export 与 rollback API 保留。
- context、flashcard、quiz 均尚未满足完整升级发布周期门，因此保留隔离 one-shot
  adapter。collection adapter 只转换迁移所需的 bounded 内容，不恢复旧 UI/store，
  也不转发旧 scheduling state 或 learner response。失败时旧 key 字节不变，只有后端
  成功或确认幂等 marker 后才清除 key。最终 pre-D5 升级样本仍须在 release bundle
  复核（截至 2026-07-16；该要求后由下方 2026-07-17 owner accepted degradation
  决定取代）。
- A-R3 feature commit `5abea97c` 后，完整 D4→D5 链先完成一次 rebase；最终 review
  以 `main@3b85a85a` 收口后，D4→D5 的十二个提交再次无冲突 rebase。rebase 期间
  main 未被修改；随后该提交链已 fast-forward 合入 `main@fc1f9e5a`。两次 rebase
  前指针均保留，便于审计。
- post-A-R3 Web 自动门通过：components `22 files / 97 tests`、chat UX、capture-index、
  knowledge-points、ESLint、`tsc --noEmit` 与 Vite production build。manifest 审计为
  initial `1,700,943 raw / 491,705 gzip` bytes、StudyRoute own
  `77,558 raw / 18,367 gzip` bytes；StudyRoute 保持 dynamic entry，未提高 warning limit。
- post-A-R3 Python Study/runtime focused 回归为 `54 passed, 2 subtests passed`；core
  learning/gateway/cron/usage contract 回归为 `255 passed`。Rust `cargo check` 在被忽略的
  空 runtime 资源目录下通过，证明源码可编译；`cargo test` 在 604 秒后无失败日志超时，
  不记作通过。
- 当时尚未完成且不得提前宣告：真实 `build_bundle.ps1 -Verify` / runtime import verifier、
  Rust test、Windows WebView2/老版本升级矩阵和稳定窗口。bundle 与正在进行的 NSIS
  构建错峰执行，当前轮不启动。
- review follow-up 修复 1 P1 / 2 P2：恢复 flashcard/quiz one-shot 升级入口；IA
  opt-out 在 storage 清理失败时仍 session hard-off，并分别尝试两个 key；shared seed
  不再绑定首个 mount signal。focused `4 files / 37 tests`、full components
  `23 files / 106 tests`；旧 quiz 重复选项的位置与答案索引原样保留。ESLint、
  `tsc --noEmit` 与 production build 通过。复核后的
  manifest 为 initial `1,701,739 raw / 491,929 gzip` bytes、StudyRoute own
  `80,639 raw / 19,426 gzip` bytes；动态边界与既有 warning limit 保持不变。最终
  A-R3 rebase 后 focused `4 files / 37 tests`、`tsc --noEmit` 与增量 `cargo check` 通过。

**D 轨最终收口（2026-07-17）。** Owner-led installed NSIS/current-data WebView2
组合轮已完成；唯一放弃的是 pre-D5 profile/flashcard/quiz localStorage 在 installed
NSIS 中的旧样本升级专测。该项明确记录为 accepted degradation，不记作测试通过：
隔离 one-shot adapters、失败保留旧 key、migration diagnostics/failure export 均继续
保留，后续不得在没有真实旧样本证据时物理删除。当天重新核对真实 bundled runtime
（CPython 3.11.15，`BUNDLE_INFO.json` 记录 1396.9 MB）：runtime pruning、canonical
imports、legacy identity verifier 全绿；`cargo test --locked` 在完整 runtime resource
扫描后取得 `97 passed / 0 failed`，耗时 10m27s。Web components `23 files / 106 tests`、
chat/capture/knowledge focused scripts、ESLint、production build 与 manifest chunk audit
全绿；当前 chunk 为 initial `1,701,739 raw / 491,929 gzip`，StudyRoute own
`80,751 raw / 19,461 gzip`，动态边界未回归。D-1..D-5 至此关闭；通用 v0.4
发布安装、updater trust-root 与发布物检查留在 release runbook，不重新打开 D 轨。

## 1. 目标

D-5 是 v0.4.0 笔记本前端的收口切片，不再增加新的学习语义。它只完成三件事：

1. 为生命周期 IA 增加封闭、只计数不引用的事件合同与可信埋点；
2. 删除已被 `/study/:spaceId/:page` 覆盖的聊天侧栏重复面和满足退役条件的
   legacy Web 读取路径，只保留一个清晰的 STUDY 入口与随时可达的聊天逃生门；
3. 在 A-R3、D-4 都进入同一集成基线后完成 Windows WebView2 组合手工轮、
   升级迁移轮、体积门和发布文档收口。

完成后，`/study` 是学习生命周期唯一的主前端；聊天中的 `KnowledgePointChips`
仍保留为 kq-kp 显式捕获入口，但聊天侧栏不再承载第二套学习页、练习页、草稿或
治理状态机。

## 2. 为什么现在可以开 D-5

正式依赖已经满足：D-2、D-3、D-4 均已实现并通过各自 review。D-5 必须消费
D-4 的统一 `StudyDraftProvider`、M5 detail/audit/governance 与最终错误语义，因此
从 `codex/study-d4@fcc21cab` 建链式分支是正确基线。

开工时 `main@bca84706` 正被 A-R3 的大规模 staged/unstaged 改动占用，因此 D-5
从 D-4 建立独立 worktree。A-R3 会改变 core/persistence 命名、最终 bundle 和老版本
升级路径，所以最终 WebView2/升级验收必须在 A-R3 之后重跑。实际执行结果为：

```text
已完成：D4(fcc21cab) -> D5 独立 worktree（计划、合同、Web 收口）
已完成：main 最终收口 A-R3(3b85a85a) -> 完整 D4→D5 链 rebase 到新 main
已完成：完整 D4→D5 链 fast-forward 合入 main(fc1f9e5a)
已关闭：Rust test + real runtime verifier + installed current-data WebView2；旧 Study
        installed-NSIS 升级样本按 2026-07-17 owner 决策接受降级并保留 compat adapters
```

已知 A-R3 与 D-5 的直接热点是 `DECISIONS.md`、`tauri/src/lib.rs` 和
`web/src/locales/strings.ts`。rebase 未产生冲突，三个热点已按 hunk 复核，并由
post-A-R3 Web/Python/core/Rust check 覆盖；D-4 与 D-5 现已进入 main。

## 3. 开工审计结论

### 3.1 IA telemetry 还没有桌面消费链

- `hermes_core/agent/usage_events.py` 是模型 transport/cost/H5 conduct 的可选
  per-attempt sink，不是 Web IA collector；D-5 不得把页面导航事件塞进该模型。
- 仓库目前没有可供 Web 调用的 telemetry endpoint、生产 sink 或已经落地的
  Settings opt-in toggle。文档承诺 telemetry default-off，但运行时链尚未实现。
- 因此 D-5 可以立即锁定事件 schema、T2 隐私测试和注入点；生产 transport
  必须先过本计划的 Transport Gate，不能暗中新增上传地址或默认开启采集。

### 3.2 旧侧栏已经降级，但仍有重复壳

- `WorkspacePanel` 已有独立 `<OpenStudyLink />`，同时仍渲染 `StudySection`。
- `StudySection` 仍包含 legacy profile 摘要、四个过渡 prompt action、一个重复的
  practice handoff，以及 built-in course seed 副作用。
- 旧 `FlashcardPanel` / `QuizPanel` 已不存在，练习 mutation 已集中到
  `PracticePage`；D-5 不应重新发明兼容 panel。
- 删除 `StudySection` 前必须把 idempotent built-in course seed 移到一等 Study
  bootstrap（优先 `StudyRoute`/repository bootstrap），否则只从 `/study` 进入的
  新用户可能失去默认课程初始化。

### 3.3 legacy localStorage 分成三类

1. `studyStore.ts` 仍被 `StudySection` 作为只读 prompt context 使用，也被
   `FlyleafPage` 用于一次性 M4 context migration。
2. `flashcardStore.ts`、`quizStore.ts` 及两个 `*LearningStore.ts` 已无生产调用者，
   只剩类型/迁移 helper 与测试；它们是优先退役候选。
3. 后端 migration status/failure export 与 owner 导出能力仍有回滚价值，不因删除
   Web 旧读取而一起删除。

“删除 legacy read path”必须服从数据安全门：先用旧版本样本证明成功迁移、失败
保留、可恢复备份和幂等 marker，再删除对应读取。若一个发布周期条件尚未满足，
则只把兼容逻辑收窄为隔离的 one-shot migrator；不得谎称已经完成物理删除。

## 4. 范围与非目标

### In scope

- D-5 封闭 IA event schema、T2 privacy guard、injected sink/transport boundary；
- 八个 IA 事件的权威调用点埋点与去重；
- 删除 `StudySection` 重复面，只保留 `<OpenStudyLink />`；
- 把 built-in seed 从聊天侧栏迁到一等 Study bootstrap；
- 审计并退役 legacy `study/flashcard/quiz` localStorage 生产读取及死代码；
- route、焦点、键盘、reduced motion、错误恢复、跨本隔离与 chunk 回归；
- post-A-R3 Windows WebView2、真实 Tauri invoke、老版本升级与治理安全轮；
- master plan、QA/release checklist、DECISIONS（仅非琐碎合同决策）收口。

### Out of scope

- v0.5.0 desk/paper/scene skin、3D 翻页、新品牌美术；
- 新的 M4/M5/M6 artifact/activity 语义或第二套 Study repository；
- tutor loop、checkpoint、H5 conduct 算法或 `UsageEvent` billing contract；
- 未经 owner 决策的 telemetry 上传 endpoint、第三方 SDK 或默认开启采集；
- 用 D-5 顺手删除仍承担 rollback/migration evidence 的 Python/core API；
- 在真实用户唯一学习数据上执行彻底删除、覆盖导入或破坏性升级测试。

## 5. IA 事件合同

### 5.1 允许事件名

只允许 master plan 已批准的封闭集合：

```text
study.page.view
study.space.switch
study.resume
study.wrongbook.open
study.wrongbook.retry
study.review.start
study.review.complete
study.draft.reviewed
```

### 5.2 允许字段

事件 payload 只能从以下字段选取：

```text
page          = flyleaf | plan | learn | evaluate | practice
action        = 封闭 enum（与事件名匹配）
success       = boolean
count_bucket  = zero | one | two_to_five | six_plus
```

实现可以有传输层版本号和非用户可关联的批次元数据，但产品事件 payload 禁止：

- owner/space/artifact/item/activity/session/message id；
- URL、pathname、search/query、标题、课程名、题目、回答、笔记、弱点标签；
- artifact envelope、source_refs、activity summary、错误 message/stack；
- 任意自由文本、动态 object key 或由内容 hash 得到的伪匿名标识；
- provider/model/H5 conduct 字段，避免 IA 与 H5 混算。

### 5.3 权威触发语义

| Event | 唯一触发点 | 去重/成功语义 |
|---|---|---|
| `study.page.view` | canonical Study route 完成并提交当前 page | redirect/loading/revalidate 不计；一次 location transition 一次 |
| `study.space.switch` | `StudyShell.selectSpace` 的 repository mutation 完成/失败 | 不记录前后 space id；每次用户动作最多一条，带 `success` |
| `study.resume` | `PlanPage` “继续上次”书签被用户激活 | 不记录 plan/item id；程序 focus 不计 |
| `study.wrongbook.open` | `EvaluatePage` wrongbook section 首次 settle | 每次 page mount 最多一次；只记 `success` 和 coarse count |
| `study.wrongbook.retry` | 用户点击错题证据的“再试一次” | 不记录 activity id/query；一次 click 一次 |
| `study.review.start` | 用户从 Practice home 开始 due-card review | 后端 refresh/自动恢复不计；记录 coarse queue size |
| `study.review.complete` | 最后一张卡 review mutation 成功 | 中途退出不计 complete；不记录 grade/card id |
| `study.draft.reviewed` | 统一 draft controller 的 semantic review settle | LearnPage/inbox 共用 controller，只发一条并带 `success` |

通用 `STUDY_LEARNING_EVENT` 只负责 UI revalidate，绝不能被当作 IA 事件源；否则一次
mutation 会被多个订阅页面重复计数。

### 5.4 Transport Gate

D-5 实现事件生产前必须在 plan/progress 中明确选择并记录以下其一：

1. **推荐的当前边界：** typed/injected sink + 本机 coarse aggregate，default-off，
   不新增网络上传；未来若确定 endpoint，再单独评审 consent、batch、retention；
2. **扩大 D-5：** 同时实现 Settings opt-in、单一 endpoint、batch/erase/opt-out，
   需要独立安全与隐私 review，不得仅靠文档承诺。

无论选择哪一种，sink 失败必须 fail-open（不影响导航或 mutation），disabled 时不得
发 Tauri/network 请求，测试 sink 不得进入 production bundle。

## 6. 实施任务

### Task 0: 固定分支、基线与集成门

- [x] 从 `codex/study-d4@fcc21cab` 创建 `codex/study-d5` 独立 worktree；
- [x] D-5 开工与 pre/post-A-R3 Web/Python/Rust/size 基线已在 §0 固定记录；
- [x] 记录 A-R3 overlap 清单，禁止从 dirty main 复制整文件；
- [x] 在 A-R3 合入前不把 D-5 合回 main；D-5 不修改 A-R3 工作树/index；
- [x] A-R3 最终 review 进入 main 后，把完整 D4→D5 提交链 rebase 到 `main@3b85a85a`，并重做
  diff/contract audit；D4 未被单独写入 main。

### Task 1: 先写 IA schema 与 T2 失败测试

建议新增：

- `web/src/study/iaEvents.ts`
- `web/src/study/iaEvents.test.ts`
- 必要时 `web/src/study/StudyIaContext.tsx`（只做 injected sink，不做业务状态）

测试先证明：

- [x] 未知 event name、未知字段、自由文本、对象/数组 payload 被拒绝；
- [x] event builder 只能产出 page/action/success/count_bucket；
- [x] sentinel title/answer/source_ref/id 即使传入上层对象也不会进入 serialized event；
- [x] disabled/no sink 时为同步 no-op，不产生 invoke/fetch；
- [x] sink reject/throw 不改变 route/mutation 结果；
- [x] H5 `UsageEvent` 测试不因 D-5 schema 改动，两个事件族没有 import 依赖。

### Task 2: 落地 transport boundary

- [x] 先关闭 §5.4 Transport Gate，再写 production adapter；
- [x] opt-in/default-off 必须由单一可信设置读取，不能由页面各自猜测；
- [x] 本机 aggregate/queue（若采用）只存 event enum、允许字段和 bounded count；
- [x] 关闭采集后停止新事件，并按 owner 已确认的 retention/erase 语义处理旧队列；
- [x] adapter 不读取 learning repository，不接收完整 domain object；
- [x] 失败不记录 payload 或学习内容（当前实现完全静默 fail-open）。

### Task 3: 在权威调用点接 IA 事件

- [x] `StudyRoute`/`StudyShell`：canonical `study.page.view`，redirect/reload 去重；
- [x] `StudyShell`：space switch success/failure；
- [x] `PlanPage`：显式 resume click；
- [x] `EvaluatePage`：wrongbook settle/open 与 retry click；
- [x] `PracticePage`：due review start 与最后一次成功 complete；
- [x] `DraftContext`：semantic review settle，只在共享 controller 发一次；
- [x] component tests 使用 fake sink 精确断言次数和 payload；
- [x] StrictMode/remount、请求重试、learning event revalidate 不重复计数。

### Task 4: 退役聊天侧栏重复面

- [x] 先把 `cmdStudyMigrateBuiltinCourse` 的 idempotent seed 移到一等 Study
  bootstrap，并覆盖首次成功、失败降级、重复 mount 不重复副作用；
- [x] `WorkspacePanel` 保留一个 `<OpenStudyLink />`，移除 `<StudySection />`；
- [x] 删除 `StudySection.tsx`、重复 `OpenPracticeCard` 和只为过渡 quick action
  服务的 prompt/i18n/test 代码（仅在 `rg` 证明无调用后）；
- [x] 保留 `KnowledgePointChips` capture + force refresh，它不是重复页面 mutation；
- [x] `/study` 各页保留 `/chat` Ask Nana/逃生门，且不会把内容塞进 URL；
- [x] 更新 `chatUx.test.mjs`：断言只有一个 STUDY 入口、无 legacy profile/practice
  surface、无 Study repository mutation 从聊天侧栏发起。

### Task 5: legacy localStorage 迁移与物理删除门

- [x] 清点并分类 `studyStore.ts`、`flashcardStore.ts`、`quizStore.ts`、两个
  `*LearningStore.ts` 的所有生产/测试调用者；
- [x] Owner 决定不再执行 installed-NSIS 的旧 profile/deck/quiz 样本专测；未记作通过，
  自动成功/失败/幂等/failure-export 证据保留，兼容 adapter 不删除；
- [x] 证明成功迁移幂等、跨本归属明确、失败时旧 key 原样保留、failure export 可用；
- [x] 证明重复调用不会重复创建 artifact/card/quiz；
- [x] flashcard/quiz 完整 store 与日常 learning helper 物理删除；只保留
  `legacyStudyCollectionMigration.ts` bounded one-shot adapter 及真实 API wrapper，
  不为测试恢复死生产状态机；
- [x] context migration 未满足“一发布周期 + rollback evidence”，因此未删除 one-shot
  Web reader；成功才清 key、失败保留旧值的边界继续保留，物理删除延期到真实证据齐备；
- [x] 若周期门未满足，把读取收窄到独立 one-shot compat migrator，删除日常 UI/prompt
  读取，并在 master plan 明记 deferred physical deletion；不得提前清 key；
- [x] 后端 migration diagnostics/export 保留，除非独立证明已无 rollback 价值。

### Task 6: 自动集成、隐私、a11y 与体积门

Web：

- [x] IA pure/component tests、Study route/shell/pages、DraftContext、legacy retirement；
- [x] `test:components`、`test:chat-ux`、capture-index、knowledge-points、lint；
- [x] `tsc --noEmit` + production build + `inspect-study-chunks.mjs`；
- [x] `/chat` initial graph 不引入 StudyRoute/CodeMirror/KaTeX/IA test sink；
- [x] 删除旧面后 route chunk 与 initial gzip 变化有记录，不能只提高 warning limit；
- [x] heading focus、dialog trap/return、Escape、aria-current、纯键盘、200% zoom、
  reduced motion、离开未提交练习确认由组件回归与 installed current-data WebView 轮覆盖；

Python/core/Rust：

- [x] 只运行 D-5 实际触及边界的 focused tests；未新增 Tauri telemetry command；
- [x] B-0/T2 测试扫描实际 serialized events，而不是只扫描 TypeScript type；
- [x] M4/M5/M6、migration、owner isolation、secure delete/source_refs focused 回归；
- [x] `cargo check`（空的 ignored runtime resource 仅用于源码编译检查）；
- [x] `cargo test --locked`：97 passed / 0 failed（10m27s）；真实 bundled runtime 的
  pruning、canonical imports、legacy identity verifier 全部通过。

### Task 7: A-R3 后集成审计

- [x] 确认 A-R3 已在 main 收口；完整 D4→D5 链已 rebase 并 fast-forward 合入 main；
- [x] 对 `DECISIONS.md`、`tauri/src/lib.rs`、`strings.ts` 做 hunk 级复核；rebase 无冲突；
- [x] 搜索旧 persistence/Study key 与 Tauri command：Web 生产代码仅保留隔离的
  context/flashcard/quiz one-shot readers；A-R3 的 `hermes-home`/`HERMES_HOME`
  命中均为有意兼容桥或 core 的一发布周期 alias，不做 D-5 机械删除；
- [x] pre-A-R3/pre-D5 Study app-data 升级专测由 owner 明确放弃；未声称通过，兼容
  readers/adapters 与 rollback diagnostics 保留，未来删除前仍须补真实样本证据；
- [x] installed current-data NSIS 的启动、Study 主路径与 child restart 组合轮完成；旧
  Study 数据 upgrade 不在本条中偷换为已验证；
- [x] 手工组合轮使用实际 installed NSIS/WebView2，不以 Vite dev 冒充发布验收。

### Task 8: Windows WebView2 组合手工轮

先创建 disposable owner/fixture；测试前导出可恢复备份。彻底删除只作用于一次性数据。

#### 8.1 布局、主题与输入矩阵

- [x] 窄 `<640px`、中 `640..959px`、宽 `>=960px`；
- [x] 100% 与 200% 缩放，无页面双轴滚动；
- [x] light/dark/system，中文/英文；
- [x] mouse + 纯键盘，focus 顺序、返回焦点、Space/1..4 focus exclusion；
- [x] Windows reduced motion 开启时无位移/翻转依赖。

采用 pairwise matrix 覆盖主题×语言×宽度，200% 和纯键盘各有独立完整路径；不要把
所有组合乘成不可执行的笛卡尔积，但每个维度至少与两个其他维度交叉一次。

#### 8.2 生命周期与跨本

- [x] 两个课程 A/B：deep link、space switch、draft count、detail/audit 不串本；
- [x] Flyleaf active/draft、Plan resume/complete/skip、Evaluate wrongbook/retry；
- [x] Practice cards/quiz/code/derivation、未提交离开确认、draft activate/reject；
- [x] Learn 三种 M5 active kind、独立 unavailable/retry、source/raw 按需展开；
- [x] unified inbox 的三种 lifecycle、semantic reviewer unavailable、显式 retry；
- [x] telemetry fake/local evidence 只有允许 enum/count，不含本轮 fixture 文本/id。

#### 8.3 治理、降级与升级

- [x] export 与取消；非空 owner import 拒绝；空 owner roundtrip；
- [x] migration diagnostics/failure export；删除强确认与成功后 cache 清空；
- [x] offline、desk child unavailable/restart、请求超时、previous/stale 保留；
- [x] v0.3/pre-D5 localStorage installed-NSIS 样本升级由 owner 接受不执行；自动
  成功/失败/重启/幂等合同已覆盖，但本项不记作手工测试通过，adapter 继续保留；
- [x] 同一旧 app-data 上的 A-R3 + Study 联合升级随上述旧 Study 专测一并接受不执行；
  A-R3 独立迁移证据有效，两套兼容路径均不得因本次收口删除；
- [x] 真实用户数据未用于 destructive smoke，fixture 与临时文件最终清理。

### Task 9: 文档、发布门与收口

- [x] 更新 master plan D-5 pre-A-R3 record、`DECISIONS.md` 的 IA transport/retention
  决策、学习数据宪章 T2 完成记录；
- [x] 更新 QA/release checklist：Study route、WebView2 matrix、旧版本升级、telemetry
  default-off/opt-out、fixture safety；
- [x] 记录 post-A-R3 自动测试数字、chunk raw+gzip、已知降级与 deferred cleanup；
- [x] 记录真实 runtime verifier、installed current-data WebView2 证据与旧 Study 升级
  专测的 owner accepted degradation；
- [x] `git diff --check`、工作树 clean 后，D4→D5 链已 fast-forward 合入 main；
- [x] D-5 frontend feature-complete（2026-07-16）与最终收口（2026-07-17）已隔稳定窗口，
  未在同日边改边宣告完成。

## 7. Suggested commit slices

1. `docs(study): plan D5 frontend closeout`
2. `test(study): lock D5 IA privacy contract`
3. `feat(study): add default-off IA event boundary`
4. `feat(study): instrument lifecycle IA actions`
5. `refactor(study): retire duplicate chat study surfaces`
6. `refactor(study): retire eligible legacy web stores`
7. `test(study): close D5 integration and migration gates`
8. `docs(study): close D5 notebook frontend`

每个 slice 只提交自己的代码与测试。A-R3 rebase 冲突单独成 integration commit，不能
混入功能实现，也不能使用“ours/theirs 整文件”跳过语义复核。

## 8. Acceptance Criteria

1. `/study/:spaceId/:page` 是 profile/plan/evaluation/practice/learn/draft/governance
   唯一主前端，聊天侧栏只有一个 STUDY 入口；kq-kp capture 保留且不复制页面状态机。
2. built-in seed 不再依赖聊天侧栏 mount；首次 `/study`、重复 mount、失败重试均安全。
3. IA 事件只来自批准的八个名称，只含 page/action/success/coarse count；T2 对实际序列化
   数据证明没有标题、题目、答案、id、source_refs、URL 或自由文本。
4. IA 与 H5/transport cost telemetry 完全分离；default-off，无 sink/失败 sink 不影响产品。
5. page/switch/resume/wrongbook/review/draft review 每个用户动作只计一次，revalidate、
   StrictMode、自动 effect 和失败重试不会双计。
6. 满足退役门的 legacy Web stores/readers 已物理删除；未满足周期门的只剩明确隔离的
   one-shot migration adapter，失败不删旧数据且有 deferred 记录。
7. 两课程跨本隔离、D2-D4 全流程、治理与降级在 post-A-R3 release bundle 上通过。
8. 窄/中/宽、亮/暗、中英、纯键盘、200% zoom、reduced motion、offline/desk child
   unavailable 和老版本升级均有 Windows WebView2 证据。
9. Web/Python/core/Rust 自动门、production build、chunk 审计、`git diff --check` 全绿；
   `/chat` initial graph 没有 Study 重内容或 telemetry test sink 回归。
10. D-5 与 A-R3/D4 合入顺序、冲突处置、测试数字、隐私决定和剩余 cleanup 均在文档中
    可追溯，工作树 clean 后再合并。

**Acceptance closeout（2026-07-17）：** 1–6、9–10 完整满足；7–8 的 installed
current-data WebView2 部分满足。唯一缺口是旧 Study localStorage 的 installed-NSIS
升级样本，owner 明确接受为降级而非通过；因此保留 one-shot adapters 和 rollback
diagnostics，并把它们的物理删除继续绑定到未来真实旧样本证据。该降级不影响 D 轨
feature close，但必须作为 v0.4 已知验证缺口保留记录。
