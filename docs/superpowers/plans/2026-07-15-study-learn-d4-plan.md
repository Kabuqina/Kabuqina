# D-4 Implementation Plan — 学习页、统一草稿箱与高级治理

> 日期：2026-07-15
>
> 状态：D-4 implemented and automated gates complete；WebView2 组合验收归 D-5
>
> 工作分支：`codex/study-d4`

**Goal:** 将 `/study/:spaceId/learn` 从占位页升级为当前课程的真实学习内容页，
让知识库、资源包、辅导笔记与已捕获知识点可阅读；把壳级草稿计数入口升级为
跨分页统一审核面，并在非拟物的高级菜单中收口数据导入/导出、来源审计、原始
JSON、迁移诊断与彻底删除。

**Inputs:**

- [v0.4.0 主开发计划](2026-07-06-v0.4.0-development-plan.md) D-4；
- [v0.4 笔记本前端实施设计](../specs/2026-07-10-v0.4-notebook-frontend-implementation-design.md)；
- [笔记本前端愿景](../specs/2026-07-06-desk-notebook-frontend-vision.md)；
- [四层学习管线设计](../specs/2026-07-01-study-four-layer-learning-pipeline-design.md) M5/M6；
- [知识点单卡捕获设计](../specs/2026-07-05-study-knowledge-point-capture-design.md)；
- 已完成的 D-1/D-2/D-3 壳、页面与 structured bridge；
- 已落地的 B-4（M5 reviewer/Gateway）与 B-5（有界摘要、治理）契约。

**Tech Stack:** React 19 / React Router 7 / Tauri 2 structured desk bridge /
FastAPI / `learning.db` / Vitest + Testing Library + user-event / existing kq-glass
tokens。D-4 不增加 runtime npm 依赖。

## Progress / 收口记录（2026-07-16）

- [x] D-4 学习页、统一草稿 controller/inbox、artifact audit 与 owner 治理实现落地；
- [x] 三轮 review 收口：跨 space/artifact 状态隔离、refresh/latest-wins、M5 kind
  有界查询、导入预检/a11y/source ref 合同，以及激活后 LearnPage 即时重载、
  refresh/load-more 隔离、原子导入 structured 409、kind 级独立降级和 audit 404
  stale 回收；
- [x] Web 自动门：ESLint、production build、19 个组件测试文件 / 80 项测试通过；
  `StudyRoute` 75.29 kB / gzip 17.61 kB；
- [x] Python/core 自动门：M6 route 7 项、governance 7 项通过；
- [x] Rust import reader：absolute path、`.json`、10 MiB、UTF-8、JSON object、
  `version=1` 共 3 项专项测试通过；
- [ ] **D-5 handoff（不属于 D-4 未完成实现）：** Windows WebView2 全组合手工轮；
  D-4 仅提供测试清单与安全夹具约束。

## Scope

### 本轮必须完成

- `LearnPage` 消费当前 URL space 的真实 active M5 artifacts；
- 知识点、知识库、资源包、辅导笔记的诚实 empty/loading/error/degraded/stale 状态；
- 所属页就地草稿与壳级统一草稿箱共用同一 controller/query/view-model/mutation；
- M5 语义复核重试、通过后落墨、拒绝抽走，以及 pending/failed 的可理解状态；
- artifact 级来源审计和原始 JSON；owner 级导出、空 owner 导入、迁移诊断、彻底删除；
- URL-space 隔离、结构化错误、窄窗/200% 缩放、键盘与焦点闭环；
- 旧 STUDY 侧栏对应知识/草稿写入口退役，禁止双写；
- 自动门、Windows WebView2 手工烟测与 D-4 文档收口。

### 明确不做

- 不做 v0.5 的桌面、书堆、白板课、3D 翻页或完整页边 companion；
- 不新增知识点实体或第二套知识库；kq-kp 仍以已激活单卡为持久化事实；
- 不在 Web join 原始数据库语义，不在列表预取所有 artifact envelope；
- 不让模型、reviewer 或导入流程自动激活内容；用户仍是最终落墨者；
- 不把导入/导出/删除伪装成抽屉、书本或其他桌面物件；
- 不在 D-4 删除仍承担一次性迁移读路径的代码；最终清理归 D-5；
- 不做 D-5 的 IA telemetry 总收口和全产品旧面删除。

## Opening audit and dependency decision

D-4 动工前审计确认：

- B-4 已由 `4a46b1e6`、`16b126d3` 落地三个 M5 kind、review lifecycle、
  production semantic reviewer、来源审计与 Gateway `/study`；主计划尚缺 B-4
  完成记录，D-4 收口时一并补文档，不重做实现；
- B-5 已提供 `space/kind/status` 有界 summary、单条 detail、统一状态转换、owner
  export/import/delete 与 migration status/failure export；
- `LearnPage` 目前仍由 `PlaceholderPage` 承担；`DraftInboxButton` 只显示 kind count，
  没有详情、审核或共享 mutation；
- artifact summary 不含正文，这是刻意的隐私/性能边界。D-4 应先读有界摘要，只有
  用户选择内容或展开草稿时才读取单条 detail；
- `source-audit` 与 `semantic-review` 当前依赖 current space，且尚无对应 Tauri
  command。D-4 必须把它们改为显式 URL `space_id` 并接入 `DeskBridgeError`；
- 已捕获 kq-kp 是 active `flashcard_deck` 单卡，公开 card projection 已含
  `front/back/tags`。学习页可只读展示标记为知识点的已捕获卡，不可杜撰“尚未
  捕获”的持久化 chips；聊天中的 `KnowledgePointChips` 继续是捕获入口。

## Guardrails

1. **URL space 是唯一页面作用域。** 页面、detail、source audit、review 与 status
   mutation 全部显式携带 `spaceId`；禁止先切 current space 再执行操作。
2. **摘要与正文分离。** 列表只读 B-5 summary；detail 按需加载，并用 generation /
   `AbortSignal` 丢弃过时响应。
3. **共享一套草稿状态机。** 统一草稿箱和所属页只消费同一个 shell-level draft
   controller；不得各自维护 activate/reject/review 的 pending/error 状态。
4. **语义 review fail closed。** reviewer 超时、异常或无效输出继续显示 pending；
   不把“审核服务不可用”解释为通过，也不把 failed 自动变成 rejected。
5. **内容类型显式映射。** knowledge/resource/note payload 先通过 typed mapper；未知
   字段不直出，契约不完整显示 degraded，不用 mock 补齐。
6. **数据治理是明确的高级功能。** 原始 JSON、迁移失败 detail 与 owner bundle 只在
   用户显式操作后加载/展示；默认学习页不渲染它们。
7. **彻底删除不可逆。** 二次确认必须要求固定确认语句；成功后清空缓存、重新加载
   spaces 并导航到安全路由，不保留已经删除的正文或草稿在内存中。
8. **导入不覆盖。** 沿用 B-5 的 empty-owner 原子导入语义；UI 在调用前解释前置条件，
   冲突以结构化 409 呈现，不做 merge。
9. **不复制练习面。** 学习页的已捕获知识点只读；复习动作仍只在 PracticePage。
10. **用户内容优先。** 小娜旁注是短、辅助、可忽略的 aside；不能挤压正文，也不能
    用固定人格/能力判断替代学习内容。
11. **不记录敏感 telemetry。** D-4 测试和日志不写 artifact payload、标题、回答、
    `source_refs` 或 raw JSON；D-5 后续事件只允许动作类别和计数。
12. **不新增 runtime 依赖。** 文件选择复用 dialog；导出复用既有安全文本写命令；
    导入若需读文件，在 Rust 增加限定 `.json`、大小上限和 JSON object/version
    校验的窄 command，不引入新的 Web 文件系统依赖。

### Task 1: 固定 D-4 开工门与契约基线

- [x] 运行 D-1/D-2/D-3 focused Web/Python/Rust gates，记录 branch HEAD、
  `/chat` initial graph 与 `/study` route chunk 基线；
- [x] 为 M5 三种 payload、semantic pending/passed/failed、B-5 summary/detail 分离、
  owner governance roundtrip 建立或补齐契约测试；
- [x] 在主计划 B-4 增加真实完成记录与关键 commits，避免后续误判为未实现；
- [x] 全仓审计 M5/草稿/治理的现有读写入口，形成 D-4 迁移清单；
- [x] 确认 `cmd_study_data_*` 已全部使用 `DeskBridgeError`，列出仅需补齐的
  source-audit / semantic-review / bounded knowledge-point wire。

### Task 2: URL-space M5 bridge 与安全 DTO

**Python / Rust:**

- [x] `source-audit` 与 `semantic-review` 接口显式要求 `space_id`，通过
  `_desktop_ctx(space_id=...)` 校验 artifact ownership；A 本 artifact 在 B 本返回
  404，不得回退 current space；
- [x] 新增并注册 `cmd_study_artifact_source_audit` 与
  `cmd_study_artifact_semantic_review`，校验 path id，统一返回
  `{status, code, detail}` 对应的 `DeskBridgeError`；
- [x] 如 card 的本地化 tag 不能可靠识别 kq-kp，增加有界、当前 space 的
  knowledge-point projection，服务端依据可信 `source_refs.origin=kq-kp` 或 capture
  activity 判定；Web 不按中文标签猜来源；
- [x] projection 只返回学习页所需的 `item_id/front/gist/confidence/captured`，限制
  `limit <= 100`，不返回 session id、完整 source refs 或 activity detail；
- [x] source audit 继续只返回契约允许的有界标量 source refs；拒绝嵌套正文转储。

**Web API:**

- [x] 为三种 M5 payload 建立窄 DTO：knowledge concepts 的 `term/explanation`、resource
  的 `title/purpose/credibility`、note 的 `goal/hints/misconceptions/next_steps`；
- [x] artifact detail mapper 校验 `kind/space/status/review/payload`，未知或畸形内容
  进入 degraded，不用 `as` 强转直接渲染；
- [x] source audit、semantic review、knowledge points 与 governance command 均接入
  `normalizeRepositoryError`，测试 400/404/409/unavailable；
- [x] 所有新 repository 方法接受 `spaceId + AbortSignal`（owner 级治理除外），并
  保持 request generation 语义。

### Task 3: Learn repository 与页面 view-model

- [x] 扩展 `StudyRepository`：`loadLearnHome`、`loadArtifactDetail`、
  `loadKnowledgePoints`、`loadSourceAudit`、`runSemanticReview`；
- [x] `loadLearnHome(spaceId)` 并行读取 active M5 summaries、已捕获知识点与共享
  draft snapshot；任一子读取失败只降级对应 section，不让整页空白；
- [x] active M5 summary 按 kind 分别有界加载并保留 kind 级失败；detail 只在用户选择/展开某个
  artifact 时读取并按 `spaceId + artifactId` 缓存；
- [x] 设计纯 view-model：section state、selected artifact、detail loadable、draft
  review state、review reason 与 friendly error；
- [x] mapper/repository tests 覆盖部分失败、空 space、过时响应、跨本切换、畸形
  payload、truncated summary 与 lazy detail。

### Task 4: Shell-level 统一草稿 controller

- [x] 将当前 `StudyShell` 的 count-only load 提升为 `StudyDraftProvider/controller`，
  持有当前 space 的有界 items、kind counts、分页、detail cache 与每项 mutation；
- [x] controller 暴露 `refresh/openDetail/retryReview/activate/reject/archive`，统一处理
  pending、成功后的列表移除/count 更新、失败保留与重试；
- [x] 切换 space 时立即清除旧 detail/mutation 状态并 abort 旧请求，防止 A 本正文或
  队列闪现在 B 本；
- [x] `study-learning-event` 触发 controller refresh；refresh 采用 latest-wins，取消
  旧首页及 load-more 请求，避免并发响应回灌旧 snapshot；
- [x] 所属页通过 kind selector 使用同一 snapshot/controller，不自行再次请求
  `/artifacts?status=draft`；
- [x] provider tests 固定同一 artifact 从 inbox 或 page 操作后的同步结果，证明没有
  第二套状态机。

### Task 5: LearnPage 主内容

- [x] 新建 `LearnPage` 并接入 `StudyPageOutlet`；mount/space change 后焦点落 `h1`；
- [x] 页面以“本课知识点 / 课程知识库 / 资源包 / 辅导笔记”组织，正文是主列；
  宽屏才启用轻量 aside，窄窗按普通文档顺序落回正文后；
- [x] 已捕获 kq-kp 显示为只读 chips/摘要并标明“已加入复习”；入口跳 PracticePage，
  不在学习页复制评分；聊天仍是新增捕获入口；
- [x] knowledge base 使用 concepts 导航与可读 explanation；resource pack 呈现用途与
  可信度说明，外链只在有安全 URL 契约时开放；tutoring note 呈现目标、提示、误区、
  下一步，不泄露 reviewer prompt；
- [x] 多个 active artifact 用 summary 选择器切换；默认选择最近更新项，但不自动
  拉取所有 detail；
- [x] 每个 section 独立覆盖 loading/empty/error/degraded/stale；不存在 M5 内容时
  诚实引导用户去聊天生成，不展示示例数据；
- [x] **D-4 取消展示：** 未引入小娜旁注，避免无证据 learner label；未来若恢复完整
  页边 companion，归 v0.5 视觉切片，正文仍为主要阅读列。

### Task 6: 所属页就地草稿审核

- [x] LearnPage 从共享 controller 选择 `knowledge_base/resource_pack/tutoring_note`
  草稿，以铅笔夹页语言显示 title、kind、review mode/status 与更新时间；
- [x] 展开时才拉 detail；默认摘要不包含学习正文或 source refs；
- [x] semantic pending 提供“重新复核”；passed 后才允许知识库/资源包落墨；failed
  显示未通过但不自动拒绝；reviewer unavailable 继续 pending；
- [x] deterministic tutoring note 可直接由用户落墨；引用外部来源或包含答案而升级
  semantic 时服从 reviewer gate；
- [x] 落墨/抽走双击锁定，失败保留草稿和已展开正文；成功后共享 inbox/page 同步；
- [x] user-event 覆盖 review retry、blocked activation、pass→activate、reject、
  double click、failure retry 与跨本隔离。

### Task 7: 壳级统一草稿箱

- [x] 将 `DraftInboxButton` 从 count popover 升级为可审核 dialog；桌面宽度可用居中
  dialog，窄窗用底部 sheet，但 DOM/语义是同一组件；
- [x] 支持 all/kind 过滤、摘要分页/“加载更多”、review/status 标签和所属页跳转；
  count 始终来自同一 snapshot；
- [x] 选择草稿后复用 Task 6 的 detail/review actions，不复制 mutation handler；
- [x] 练习、扉页、计划、评估类草稿也可在 inbox 审核；跳到所属页时使用明确 kind→
  page 映射，未知 kind 留在 inbox 并显示 unsupported；
- [x] dialog 实现 focus trap、Escape、关闭后焦点归还、初始焦点、live status；关键
  操作不依赖 hover；
- [x] 200% 缩放和窄窗下 header/filter/content/actions 各自单轴滚动，不出现双轴页面
  滚动，也不被 WebView 窗口底部裁掉。

### Task 8: artifact 高级审计

- [x] 在 artifact detail 的明确“高级”入口提供来源审计与原始 JSON，学习正文默认不
  展开这些内容；
- [x] 来源审计按有界标量字段分行呈现，空来源显示明确空态；不把自动 review 描述成
  来源真实性保证；
- [x] 原始 JSON 仅在用户点击后读取单条 detail，以只读 `<pre>`/copy-safe 方式显示，
  保留换行与横向内部滚动，不注入 HTML；
- [x] source audit/detail 的 structured 404 视为 artifact stale：controller 的
  `invalidateArtifact()` 取消 detail/action 请求、删除 detail/action/error cache，
  panel 清除 raw/audit 状态，再通过统一 learning event 刷新 active/draft summary；
- [x] 测试证明进入 LearnPage 或打开 inbox 不会自动调用 source audit/raw detail。

### Task 9: owner 级高级治理菜单

- [x] 在 Study top bar 增加非拟物 `StudyAdvancedMenu`，包含：学习数据导出、从备份
  导入、迁移状态/失败导出、彻底删除；系统设置仍留在 chrome；
- [x] 导出先显式告知包含私人学习内容，再调用 owner export、JSON pretty-print 与
  dialog save，复用已有安全 text writer；取消保存不算错误；
- [x] 导入经 dialog 选 `.json`，Rust reader 限制扩展名、大小、UTF-8、JSON object
  和 `version=1`；UI 先显示文件级摘要与 empty-owner 前置条件，确认后才调用原子
  import；
- [x] import 409 明示“当前学习数据非空，不能覆盖”，不提供暗中 merge/delete；
- [x] 迁移状态默认只显示 key/status/time 与计数；失败 detail/raw export 由用户显式
  展开或另存，避免默认泄露旧内容；
- [x] 彻底删除要求二次确认并输入固定语句；成功后清除 repository/controller cache、
  revalidate spaces、关闭所有 dialog，导航到安全 STUDY 空态；
- [x] owner export/import/delete 不错误地携带当前 `spaceId`，也不暗示只操作当前本；
  所有文案明确它们作用于“全部学习数据”。

### Task 10: 旧面退役与双写审计

- [x] `StudySection`/旧 WorkspacePanel 中知识库、资源包、辅导和草稿管理的可写入口
  改为 `/study/:spaceId/learn` 或 unified inbox 跳转；
- [x] 旧面不得继续 activate/reject/review/import/export/delete；只读摘要若暂留，
  只能读新 repository/bridge；
- [x] 保留 `KnowledgePointChips` 的显式 capture 写路径，因为它是聊天中的 kq-kp
  一等入口，不属于重复的学习页 mutation；
- [x] 全仓 `rg` 审计 artifact status/semantic review/governance invokes，证明每个
  mutation 只有一个产品入口/controller；
- [x] legacy migration read path 按 D-5 约定保留，但不再成为日常知识/草稿管理面。

### Task 11: 可访问性、体积、回归与收口

- [x] Web focused tests：repository/mappers、draft provider、LearnPage、DraftInbox、
  advanced audit/governance、StudyShell/route regressions；
- [x] Python focused tests：URL-space audit/review、knowledge-point projection、M5/M6
  regression、source_refs minimization、governance atomicity；
- [x] Rust tests：id/path/size/version validation、structured 400/404/409、new command
  registration；运行 relevant `cargo test` 与 `cargo check`；
- [x] 运行 lint、`npm run test:components`、相关 node tests、`npm run build`，记录
  Learn/Draft dialog chunks 与 `/chat` initial graph；不得让 raw/governance UI 进入
  chat initial graph；
- [x] 自动 a11y 断言：heading focus、dialog trap/return、Escape、live status、label、
  键盘可达、reduced motion；
- [ ] **D-5 handoff：** Windows WebView2 手工轮：两个课程跨本隔离、active 内容、三种草稿 lifecycle、
  reviewer unavailable、来源/JSON、导出/取消、非空导入拒绝、空 owner roundtrip、
  删除确认、亮暗主题、中英双语、窄/中/宽窗、200% 缩放、纯键盘、desk child 失效；
- [ ] **D-5 执行约束：** 手工测试使用一次性 owner/fixture 或先导出可恢复备份；彻底删除测试不得作用于
  用户唯一真实学习数据；
- [x] 更新 master plan D-4 completion record、本计划 progress、必要的 troubleshooting；
  D-4 完成后再开 D-5。

## Suggested commit slices

1. `test(study): lock D4 M5 and governance contracts`
2. `fix(study): scope M5 review and audit bridge`
3. `feat(study): add learn repository projections`
4. `feat(study): share draft review controller`
5. `feat(study): build learn page`
6. `feat(study): complete unified draft inbox`
7. `feat(study): add advanced learning governance`
8. `refactor(study): retire duplicate knowledge draft actions`
9. `test(study): close D4 regression and manual smoke`
10. `docs(study): close D4 learning page`

每个 slice 只提交其负责文件与对应测试。不得把 root 其他轨道的 staged/dirty 改动
带入 D-4 worktree。

## Acceptance Criteria

1. `/study/:spaceId/learn` 对真实 active knowledge base/resource pack/tutoring note 提供
   可读内容，且没有 demo/mock fallback。
2. 已捕获 kq-kp 只从当前 space 的可信持久化数据呈现；学习页不复制复习 mutation。
3. 统一草稿箱与所属页在同一 controller 下审核；任一处操作后另一处立即一致。
4. semantic reviewer 异常保持 pending；知识库/资源包未 passed 不能 active；用户决定
   最终落墨或拒绝。
5. summary 不包含 payload/source refs；detail/source/raw 只在显式选择后按需读取。
6. A 本的 content/draft/detail/review/mutation 不会出现在 B 本；深链不依赖 current
   space 副作用。
7. 导出/导入/迁移诊断/彻底删除均在非拟物高级菜单中，作用域和风险文案准确；导入
   不覆盖，删除有强确认且成功后不留 stale cache。
8. 旧面不再提供重复的 M5/草稿/治理写路径；聊天 kq-kp capture 仍正常。
9. 窄窗、200% 缩放、纯键盘、亮暗主题、中英双语、reduced motion、desk child
   unavailable 均有可用路径。
10. Web/Python/Rust gates、production build 和 Windows WebView2 手工烟测全部通过，
    `/chat` initial graph 未引入 D-4 重内容回归。
