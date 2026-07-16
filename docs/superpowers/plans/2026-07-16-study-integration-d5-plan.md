# D-5 Implementation Plan — 集成观测、旧面退役与 WebView2 收口

> 日期：2026-07-16
> 状态：plan ready，implementation not started
> 起始基线：`codex/study-d4@fcc21cab`
> 工作分支：`codex/study-d5`
> 正式依赖：D-2、D-3、D-4 已完成；最终集成轮还需等待 A-R3 收口

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

当前 `main@bca84706` 正被 A-R3 的大规模 staged/unstaged 改动占用，不适合直接
切分支或写 D-5。A-R3 不是 D-5 的正式产品依赖，但它会改变 core/persistence
命名、最终 bundle 和老版本升级路径；D-5 的最终 WebView2/升级验收必须在 A-R3
之后重跑。因此采用以下顺序：

```text
现在：D4(fcc21cab) -> D5 独立 worktree（计划、合同、Web 收口）
稍后：main 收口 A-R3 -> 合入 D4 -> D5 rebase 到新 main
最后：冲突复核 -> 全量自动门 -> release bundle -> WebView2/升级组合轮 -> 合入 D5
```

已知 A-R3 与 D-5 的直接热点是 `DECISIONS.md`、`tauri/src/lib.rs` 和
`web/src/locales/strings.ts`。D-5 在 A-R3 完成前可以改自己的独立模块，但不得
提前合入 main，也不得用整文件覆盖方式解决这些共享文件。

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
- [ ] 记录 D-5 开工时 D4 full Web/Python/Rust/size 基线，不复用口头结果；
- [ ] 记录 A-R3 overlap 清单，禁止从 dirty main 复制整文件；
- [ ] 在 A-R3 合入前不把 D-5 合回 main；D-5 不修改 A-R3 工作树/index；
- [ ] A-R3 + D4 进入 main 后 rebase D-5，并重做 diff/contract audit。

### Task 1: 先写 IA schema 与 T2 失败测试

建议新增：

- `web/src/study/iaEvents.ts`
- `web/src/study/iaEvents.test.ts`
- 必要时 `web/src/study/StudyIaContext.tsx`（只做 injected sink，不做业务状态）

测试先证明：

- [ ] 未知 event name、未知字段、自由文本、对象/数组 payload 被拒绝；
- [ ] event builder 只能产出 page/action/success/count_bucket；
- [ ] sentinel title/answer/source_ref/id 即使传入上层对象也不会进入 serialized event；
- [ ] disabled/no sink 时为同步 no-op，不产生 invoke/fetch；
- [ ] sink reject/throw 不改变 route/mutation 结果；
- [ ] H5 `UsageEvent` 测试不因 D-5 schema 改动，两个事件族没有 import 依赖。

### Task 2: 落地 transport boundary

- [ ] 先关闭 §5.4 Transport Gate，再写 production adapter；
- [ ] opt-in/default-off 必须由单一可信设置读取，不能由页面各自猜测；
- [ ] 本机 aggregate/queue（若采用）只存 event enum、允许字段和 bounded count；
- [ ] 关闭采集后停止新事件，并按 owner 已确认的 retention/erase 语义处理旧队列；
- [ ] adapter 不读取 learning repository，不接收完整 domain object；
- [ ] 失败仅 debug 记录固定错误类别，不记录 payload 或学习内容。

### Task 3: 在权威调用点接 IA 事件

- [ ] `StudyRoute`：canonical `study.page.view`，redirect/reload 去重；
- [ ] `StudyShell`：space switch success/failure；
- [ ] `PlanPage`：显式 resume click；
- [ ] `EvaluatePage`：wrongbook settle/open 与 retry click；
- [ ] `PracticePage`：due review start 与最后一次成功 complete；
- [ ] `DraftContext`：semantic review settle，只在共享 controller 发一次；
- [ ] component tests 使用 fake sink 精确断言次数和 payload；
- [ ] StrictMode/remount、请求重试、learning event revalidate 不重复计数。

### Task 4: 退役聊天侧栏重复面

- [ ] 先把 `cmdStudyMigrateBuiltinCourse` 的 idempotent seed 移到一等 Study
  bootstrap，并覆盖首次成功、失败降级、重复 mount 不重复副作用；
- [ ] `WorkspacePanel` 保留一个 `<OpenStudyLink />`，移除 `<StudySection />`；
- [ ] 删除 `StudySection.tsx`、重复 `OpenPracticeCard` 和只为过渡 quick action
  服务的 prompt/i18n/test 代码（仅在 `rg` 证明无调用后）；
- [ ] 保留 `KnowledgePointChips` capture + force refresh，它不是重复页面 mutation；
- [ ] `/study` 各页保留 `/chat` Ask Nana/逃生门，且不会把内容塞进 URL；
- [ ] 更新 `chatUx.test.mjs`：断言只有一个 STUDY 入口、无 legacy profile/practice
  surface、无 Study repository mutation 从聊天侧栏发起。

### Task 5: legacy localStorage 迁移与物理删除门

- [ ] 清点并分类 `studyStore.ts`、`flashcardStore.ts`、`quizStore.ts`、两个
  `*LearningStore.ts` 的所有生产/测试调用者；
- [ ] 用一次性旧版本 profile 构造 context/deck/quiz 三类样本，先导出/备份；
- [ ] 证明成功迁移幂等、跨本归属明确、失败时旧 key 原样保留、failure export 可用；
- [ ] 证明升级/重启后不会重复创建 artifact/card/quiz；
- [ ] 已无生产调用的 flashcard/quiz store 与 migration helper 物理删除，类型移到真实
  API contract 或一并删除，不为测试保留死生产代码；
- [ ] context migration 若满足“一发布周期 + rollback evidence”，删除
  `FlyleafPage` Web read 和 `studyStore.ts`；成功升级样本的旧 key 只在确认迁移后清除；
- [ ] 若周期门未满足，把读取收窄到独立 one-shot compat migrator，删除日常 UI/prompt
  读取，并在 master plan 明记 deferred physical deletion；不得提前清 key；
- [ ] 后端 migration diagnostics/export 保留，除非独立证明已无 rollback 价值。

### Task 6: 自动集成、隐私、a11y 与体积门

Web：

- [ ] IA pure/component tests、Study route/shell/pages、DraftContext、legacy retirement；
- [ ] `test:components`、`test:chat-ux`、capture-index、study stores（剩余者）、lint；
- [ ] `tsc --noEmit` + production build + `inspect-study-chunks.mjs`；
- [ ] `/chat` initial graph 不引入 StudyRoute/CodeMirror/KaTeX/IA test sink；
- [ ] 删除旧面后 route chunk 与 initial gzip 变化有记录，不能只提高 warning limit；
- [ ] heading focus、dialog trap/return、Escape、aria-current、纯键盘、200% zoom、
  reduced motion、离开未提交练习确认仍有组件级回归。

Python/core/Rust：

- [ ] 只运行 D-5 实际触及边界的 focused tests；若新增 Tauri telemetry command，
  覆盖 allowlist/size/unknown-field/default-off/fail-open；
- [ ] B-0/T2 测试扫描实际 serialized events，而不是只扫描 TypeScript type；
- [ ] M4/M5/M6、migration、owner isolation、secure delete/source_refs 回归；
- [ ] relevant `cargo test` / `cargo check`；A-R3 rebase 后重跑 bundle import verifier。

### Task 7: A-R3 后集成审计

- [ ] 确认 main 顺序为 A-R3 完成、D4 合入，再 rebase/merge D5；
- [ ] 对 `DECISIONS.md`、`tauri/src/lib.rs`、`strings.ts` 做 hunk 级冲突复核；
- [ ] 全仓搜索旧 `hermes*` persistence key、旧 Study localStorage key 和旧 Tauri command；
- [ ] 从真实 pre-A-R3/pre-D5 app-data 副本跑升级，不只测 clean install；
- [ ] clean install、upgrade install、desk child restart、gateway child 存在时均启动正常；
- [ ] 最终 release bundle 生成后再进入手工组合轮，不用 Vite dev 冒充发布验收。

### Task 8: Windows WebView2 组合手工轮

先创建 disposable owner/fixture；测试前导出可恢复备份。彻底删除只作用于一次性数据。

#### 8.1 布局、主题与输入矩阵

- [ ] 窄 `<640px`、中 `640..959px`、宽 `>=960px`；
- [ ] 100% 与 200% 缩放，无页面双轴滚动；
- [ ] light/dark/system，中文/英文；
- [ ] mouse + 纯键盘，focus 顺序、返回焦点、Space/1..4 focus exclusion；
- [ ] Windows reduced motion 开启时无位移/翻转依赖。

采用 pairwise matrix 覆盖主题×语言×宽度，200% 和纯键盘各有独立完整路径；不要把
所有组合乘成不可执行的笛卡尔积，但每个维度至少与两个其他维度交叉一次。

#### 8.2 生命周期与跨本

- [ ] 两个课程 A/B：deep link、space switch、draft count、detail/audit 不串本；
- [ ] Flyleaf active/draft、Plan resume/complete/skip、Evaluate wrongbook/retry；
- [ ] Practice cards/quiz/code/derivation、未提交离开确认、draft activate/reject；
- [ ] Learn 三种 M5 active kind、独立 unavailable/retry、source/raw 按需展开；
- [ ] unified inbox 的三种 lifecycle、semantic reviewer unavailable、显式 retry；
- [ ] telemetry fake/local evidence 只有允许 enum/count，不含本轮 fixture 文本/id。

#### 8.3 治理、降级与升级

- [ ] export 与取消；非空 owner import 拒绝；空 owner roundtrip；
- [ ] migration diagnostics/failure export；删除强确认与成功后 cache 清空；
- [ ] offline、desk child unavailable/restart、请求超时、previous/stale 保留；
- [ ] v0.3/pre-D5 localStorage 样本升级，成功/失败/重启/幂等均验证；
- [ ] A-R3 persistence rename 的旧目录/配置/凭据迁移与 D-5 Study migration 同时存在时
  不互相覆盖；
- [ ] 真实用户数据未用于 destructive smoke，fixture 与临时文件最终清理。

### Task 9: 文档、发布门与收口

- [ ] 更新 master plan D-5 completion record、`DECISIONS.md` 的 IA transport/retention
  决策、学习数据宪章 T2 完成记录；
- [ ] 更新 QA/release checklist：Study route、WebView2 matrix、旧版本升级、telemetry
  default-off/opt-out、fixture safety；
- [ ] 记录最终测试数字、bundle/chunk raw+gzip、已知降级与 deferred cleanup；
- [ ] `git diff --check`、工作树 clean、review 通过后才允许 D-5 合入 main；
- [ ] D-5 frontend feature-complete 与最终 bundle smoke 至少隔一个稳定窗口，不能同日
  边改边宣告 release ready。

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
