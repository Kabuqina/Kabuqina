# D-3 Implementation Plan — 练习页：卡片 / 测验 / 临摹 / 变式

> **执行说明：** 本会话没有 `superpowers:executing-plans` 技能；执行时沿用
> D-1/D-2 的测试先行、逐任务验收和本地提交纪律。本文是
> [v0.4.0 master plan](2026-07-06-v0.4.0-development-plan.md) 要求的
> just-in-time 实施计划。

**Goal:** 将 `/study/:spaceId/practice` 从占位页升级为当前课程唯一可写的
练习主舞台，承接卡片复习、常规测验、代码临摹/变式和推导临摹；所有结果
只经 trusted learning services 写入 activity。D-3 完成时，旧侧栏
`FlashcardPanel` / `QuizPanel` 不再执行 review 或 attempt，只保留进入新练习页
和“问小娜生成”的兼容入口。

**Inputs:**

- [v0.4.0 master plan](2026-07-06-v0.4.0-development-plan.md) D-3；
- [v0.4 notebook implementation design](../specs/2026-07-10-v0.4-notebook-frontend-implementation-design.md)；
- [frontend vision](../specs/2026-07-06-desk-notebook-frontend-vision.md)；
- [数学与代码练习系统](../specs/2026-07-05-study-math-code-practice-design.md)；
- [B-2 practice contract + grader plan](2026-07-06-practice-contract-grader-plan.md)；
- [B-3 deterministic generator plan](2026-07-11-b3-practice-generator-plan.md)；
- D-2 review closeout commit `b0d53054`。

**Tech Stack:** React 19 / React Router 7 / Tauri 2 structured desk bridge /
FastAPI / owned `hermes_core` learning services；CodeMirror 6 按需模块；已有
KaTeX；Vitest/RTL + pytest + Rust tests。

---

## Scope

### 本轮必须完成

- 当前 URL space 的卡片盒、due 队列和复习写回；
- active quiz 选择、常规题作答与一次 attempt 提交；
- `code` 的 Python 临摹/变式/solve 编辑面与 trusted grader 结果；
- `derivation` 的 DOM + KaTeX 步骤面、cloze 表达式/理由作答；
- B-3 `transcribe|variant` 生成、draft 就地审核和激活后进入练习；
- 错题本 `activityId` 来源恢复；
- 练习 API 的 URL-space、结构化错误和敏感字段边界；
- 旧侧栏练习 mutation 退役。

### 明确不做

- v0.5 的梯子④独立题、hint 阶梯、⑤讲解/费曼评估；
- 模型在 trusted route 内自动生成、判分或激活草稿；
- 通用 IDE、文件树、终端、调试器、任意语言执行或客户端执行代码；
- SymPy/CAS、LaTeX 解析、Excalidraw 推导白板；
- D-4 学习页、跨 kind 统一草稿箱和高级治理菜单；
- D-5 IA 遥测、legacy 数据删除或场景皮肤。

---

## Guardrails

- URL `spaceId` 是所有读取与 mutation 的事实来源。D-3 的 Python route、
  Tauri command 和 repository method 都必须显式携带它，不得回退 current
  space；owner 仍只由 runtime 注入。
- CodeMirror 只是输入面。学习者代码、`reference`、`test_code` 均不得在
  WebView 执行；提交只调用现有 `QuizService.submit_attempt` trusted path。
- 普通 question wire 永不下发 `reference` / `test_code` / `expr_py` /
  `accepted`。`target_code` 与 `target_steps` 只在 `transcribe` 练习中作为
  明示临摹原文出现，不得混入其他模式。
- `failure_summary` 仅可在本次结果 UI 内存中显示；不得写 localStorage、
  activity、日志、analytics、模型 prompt 或错误上报。UI 按 `failure_kind`
  做主分类，summary 只作有界补充。
- draft 生成后必须明确显示“待审核”；只有学习者 activate 后才能读取题目、
  提交或执行 grader。fallback=`model_draft_required` 只提供 AskNana 入口，
  不伪装为已生成。
- 练习写路径只有新 PracticePage 一处。旧侧栏不得同时保留 review/submit/
  activate/reject；D-3 不制造双写或第二份练习状态。
- 键盘快捷键仅在练习焦点域生效；输入框、textarea、contenteditable、
  CodeMirror 和按钮聚焦时，Space/1/2/3/4 handler 必须退出。
- 首次 loading、empty、error、degraded、stale、mutation pending 均有诚实
  状态；刷新错误保留内存中的作答，但禁用会跨信任边界的 mutation。
- `/chat` 初始依赖图不得包含 PracticePage、CodeMirror 或 KaTeX 的新增入口；
  不能通过调高 Vite chunk warning limit 过门。

---

### Task 1: D-3 开工门、现状审计与依赖基线

- [ ] 记录 D-3 基线：D-2/D-2.1 自动门、当前 `/chat` initial graph、
  `StudyRoute` chunk 和 npm dependency tree。D-2 手工 smoke 只要求验证当前
  可达状态：五页导航/URL、空态、草稿计数 popover、返回聊天/问小娜、窄窗和
  200% zoom；没有 active plan/evaluation/attempt 或对应 draft 时，计划
  complete/skip、草稿落墨和错题 retry 明确记为 **N/A**，不作为 D-3 阻断门。
- [ ] D-2 mutation 的正确性以现有 component/route tests 为开工证据；若需要
  手工走完整 mutation，另做 disposable dev fixture/临时学习库，禁止要求用户
  在真实数据中手造内部 artifact，也禁止把测试夹具随 production bundle 发布。
- [ ] 确认 B-2/B-3 production contracts 全绿：code/derivation public wire、
  sandbox grader、deterministic transcribe/variant draft、自检失败 fallback。
- [ ] 用 contract tests 固定当前敏感字段排除：public code question 无
  `reference/test_code`；public derivation cloze 无 `expr_py/accepted`；只有
  transcribe 才有 `target_code/target_steps`。
- [ ] 安装最小 CodeMirror 6 runtime 模块：`@codemirror/state`、
  `@codemirror/view`、`@codemirror/commands`、`@codemirror/language`、
  `@codemirror/lang-python`；不引入 `basicSetup` 大包、Monaco 或第二套高亮器。
- [ ] 记录 `package.json` / lockfile diff 和 clean dependency audit；前端依赖
  不要求 Python bundle rebuild，但 production Web build 必须验收。

### Task 2: URL-space D-3 API 与 structured bridge

**Core / Python:**

- [ ] 为 flashcards list/review 和 quizzes list/questions/submit/practice-generate
  的 desk routes 强制显式 `space_id`；不存在、已删除或不属于 owner 的 space
  统一 404，不泄露归属。
- [ ] capture/migration 等仍由旧兼容面调用的接口不得被 D-3 偷用；若保留
  current-space 兼容，写清退役点，不把它们包装进新 repository。
- [ ] 在 `LearningStore` / `LearningExecutionContext` 增加 exact scoped
  quiz-attempt lookup，字段读取只限解析 retry target 所需内容。
- [ ] 在 `WrongbookService` 增加 `retry_target(activity_id)`：只接受当前
  owner+space 的 `quiz.attempt`，返回 bounded opaque
  `{artifact_id, item_ids}`；`item_ids` 仅含本次未通过题的 id，不返回 prompt、
  response、answer、tags、failure summary 或 activity detail。
- [ ] 新增
  `GET /api/desk/study/practice-source?space_id=&activity_id=`；未知、过期、
  非 quiz attempt 或已不可用 artifact 使用统一 not-found/invalid 合同。

**Rust / Web API:**

- [ ] 将 D-3 Tauri commands 全部迁到 `DeskBridgeError` +
  `desk_json_request_structured`，显式验证 `space_id/artifact_id/item_id`；本地
  invalid id 返回稳定 `{status,code,detail}`。
- [ ] `study-api.ts` 收紧 DTO：补齐 `mode/timed_out/ungraded/gradable/
  ungraded_steps/failure_kind/failure_summary/scored`；响应类型不得用 arbitrary
  `unknown` 掩盖 question/attempt contract。
- [ ] 新增 practice-source command/type；测试断言 query/body 使用 URL
  space，bridge 不显示后端 detail。
- [ ] Python route tests 覆盖 A/B deep link、missing space、wrong-owner、
  retry target content exclusion、400/404/409；Rust tests覆盖结构化错误。

### Task 3: Practice repository 与页面 view-model

- [ ] 扩展 `StudyRepository`，只暴露 D-3 需要的 typed methods：
  `loadPracticeHome`、`loadQuizQuestions`、`reviewFlashcard`、`submitQuiz`、
  `generatePracticeDraft`、`resolvePracticeSource`、practice draft
  activate/reject。
- [ ] `loadPracticeHome(spaceId)` 并行读取 cards、due cards、active quizzes、
  `flashcard_deck|quiz` draft summaries；返回页面安全摘要，不把 artifact
  envelope 或答案塞入壳 VM。
- [ ] active quiz 选择以显式用户选择为准；wrongbook source 可选择 resolved
  artifact 并聚焦首个 failed item。若 artifact 已归档，显示“来源已不可用”，
  不偷偷改练其他题。
- [ ] Repository 所有方法接受 `spaceId + AbortSignal`；Tauri invoke 不能物理
  abort 时仍用 request generation 防止快速切课的旧响应覆盖。
- [ ] 增加 pure mapper/repository tests：URL-space 透传、并发部分失败、
  structured error normalization、敏感字段不进入 home VM、wrongbook 恢复。

### Task 4: PracticePage 状态机与就地草稿审核

- [ ] 新建 `PracticePage`，替换 practice placeholder；页面 chunk 自含 controller
  和 view-model，`StudyShell` 不 import 任何编辑器实现。
- [ ] 页面主状态明确为 `home / flashcard-review / quiz-taking / result`；
  mutation 独立为 pending/error，不用多个布尔值组成不可验证状态。
- [ ] 首次加载骨架；refresh 保留 previous；cards/quizzes/drafts 任一读取失败
  只降级该区。空态分别说明“无到期卡”“无 active quiz”“无待审练习”。
- [ ] practice draft 就地显示 kind、title、review status、来源类型；activate/
  reject 复用 generic explicit-space artifact status，pending 只锁当前 draft。
  activate 成功后 patch home VM 并 revalidate，可直接进入新题。
- [ ] fallback=`model_draft_required` 显示诚实原因和 AskNana 入口；不发送隐藏
  reference/test，prompt 只描述“为此题创建变式”并使用 opaque source id。
- [ ] 未提交作答只存组件内存。切 quiz、退出练习模式或离开 route 时提供明确
  放弃确认；刷新/错误不得自动清空。验证当前 Router 下的 blocker 方案，
  禁止 monkey-patch history。
- [ ] 页面 mount/space change 后焦点落 `h1`; 模式切换后焦点落练习域标题；
  result 用 `aria-live=polite`，grader pending 使用真实 status。

### Task 5: 卡片盒与 due review

- [ ] 首页显示当前课程 cards total / due / mature 和 due queue 入口；不复制旧
  space switcher 或新建课程功能，它们属于 Study shell。
- [ ] 进入复习后显示 front；显式按钮或 Space 翻卡；揭示后显示 back/hint，
  1/2/3/4 分别映射 again/hard/good/easy。
- [ ] 快捷键 handler 绑定练习域并检查 `event.repeat`、active element 和 mode；
  mutation pending 防双击/双键，成功后移动到下一张并使用后端返回状态。
- [ ] 单张失败保留当前卡与 revealed 状态，可重试或退出；整轮完成显示 reviewed
  count 和当前 due remaining，不再写 legacy context。
- [ ] RTL/user-event 覆盖 Space、1..4、输入/按钮聚焦不截获、pending 双击、
  error retry、空队列、快速切 space 和纯键盘完整一轮。

### Task 6: 常规 quiz 主流程

- [ ] active quiz 列表显示 title 和安全题数摘要；选择后再加载 questions，
  不预取所有题正文。
- [ ] choice / true_false / short_answer 复用现有确定性提交 contract，但重写为
  PracticePage 组件，不复制旧 Panel 的 current-space 与 local state glue。
- [ ] 支持上一题/下一题、未答提示和最终一次 submit；提交期间锁定导航，失败
  保留所有 responses。
- [ ] result 显示 score、correct count、weak tags 和逐题安全反馈；不得渲染
  `reference/test_code/expr_py/accepted`，也不得把 result 持久化到浏览器。
- [ ] “再练一次”只重置页面内 responses；新的 attempt 由再次 submit 产生，
  旧 activity 不覆盖。
- [ ] 测试覆盖四类普通状态、partial answer、submit failure/retry、result、
  wrongbook artifact 恢复及 unavailable source。

### Task 7: CodeMirror code practice surface

- [ ] `CodePracticeSurface` 使用第二层 `React.lazy` / dynamic import；只有当前题
  `type=code` 时加载 CodeMirror 模块，形成独立 `study-codemirror-*` chunk。
- [ ] 编辑器使用受控 adapter：props 只含 language/mode/starter/targetCode 和
  onChange；unmount 清理 `EditorView`，外部 response 更新不会重建失焦。
- [ ] Python `solve|variant` 以 starter 初始化；提交整个 buffer 为
  `{code}`。非 Python 或 `gradable=false` 显示 unsupported，不假装能判分。
- [ ] `transcribe` 明示只读 target，并用 CodeMirror decorations 标出学习者
  buffer 与 target 的逐字符偏差；diff helper 独立纯测、按 contract 20k 上限
  O(n) 运行，不用模型或第三方 diff 大包。
- [ ] 前端绝不运行 code。提交后只呈现 trusted result 的 correct/timed_out/
  failure_kind；bounded `failure_summary` 可在本次 result 展开，离开结果即释放。
- [ ] CodeMirror 提供可读 label、键盘 Tab 策略、错误关联和高对比 decoration；
  200% zoom / `<640px` 不产生页面横向滚动，编辑器自身可横滚。
- [ ] 测试用 editor adapter fake 验证 PracticePage；CodeMirror integration test
  验证初始化、输入、decoration 更新、cleanup 和 chunk import，不用源码 regex
  冒充交互测试。

### Task 8: DOM + KaTeX derivation surface

- [ ] `DerivationPracticeSurface` 使用普通语义 DOM；非 cloze 步用已有 KaTeX
  renderer 展示，cloze 步提供 expr 和 justification 输入，不引入自由白板。
- [ ] `target_steps` 只在 transcribe 模式作为并排/上方临摹原文；普通
  derivation 不得显示目标答案。提交 shape 固定为
  `{steps: {index: {expr, expr_py, justification}}}`。
- [ ] v0.4 不在前端解析 LaTeX 或自动生成 `expr_py`。当 public question 的
  `check=numeric-equivalence` 时提供独立、可选的 machine-check expression
  输入并原样提交 `expr_py`；`normalized-match` 不显示该控件。任何模式都不
  下发 expected `expr_py`。
- [ ] result 区分 correct、ungraded、ungraded_steps 和 human-check，不把未判分
  显示为错误；理由没有 accepted 时明确“本步未计分”。
- [ ] 测试覆盖多步/全 cloze、表达式和理由、KaTeX fallback、ungraded、键盘顺序、
  长公式横滚、窄窗和 200% zoom。

### Task 9: 临摹/变式生成闭环

- [ ] 在 active code/derivation question 的安全动作区提供“生成临摹”；仅对
  B-3 支持的 Python source 提供“生成变式”，不做强制线性梯子。
- [ ] 调用 B-3 时 mutation 锁定 source item；generated=true 后显示 draft，
  不自动 activate；self_checked 只说明模板自检通过，不宣传完整沙箱隔离。
- [ ] generated=false/fallback 时不产生空卡，不循环请求模型；AskNana 入口
  仍需学习者明确发起。
- [ ] draft activate 后重新读取 public questions，确认敏感字段排除，再进入
  对应 code/derivation surface；reject 后从页面移除并广播
  `study-learning-event` 更新壳 draft count。
- [ ] 测试覆盖 transcribe、variant、unsupported fallback、double click、
  activate conflict/revalidate、reject 和 source lineage 的 opaque id 传递。

### Task 10: 旧侧栏退役与双写审计

- [ ] `StudySection` 中 `FlashcardPanel` / `QuizPanel` 改为轻量兼容卡：当前课程
  练习摘要、进入 `/study/:spaceId/practice`、AskNana 生成入口；删除卡片复习、
  quiz 作答、draft activate/reject 和创建/切换 space 控件。
- [ ] 旧 panel 不 import CodeMirror、PracticePage 或 D-3 controller；如果组件
  已无独立价值，合并成一个 `OpenPracticeCard`，实际删除留 D-5。
- [ ] 更新 `chatUx.test.mjs` 与 component tests，断言 `/chat` 不再调用
  `cmdStudyFlashcardReview/cmdStudyQuizSubmit/cmdStudyQuizGeneratePractice`，且
  没有第二个练习 mutation surface。
- [ ] 全仓 `rg` 审计 `review_card / submit_attempt / generatePractice /
  localStorage` 前端调用；逐项记录 production caller，只允许 PracticePage。
- [ ] 旧 legacy migration 读取按 D-5 约定保留，不在 D-3 清除用户数据。

### Task 11: 可访问性、体积、回归与收口

- [ ] Web：D-3 pure + repository + PracticePage + editor/derivation component
  tests；full `test:components`、`test:chat-ux`、lint、TypeScript、production build。
- [ ] Python：新 D-3 route tests + M2/M3/B-2/B-3/M4/M6 regression；core retry
  target content-exclusion tests。
- [ ] Rust：D-3 structured bridge tests + relevant `cargo test` / `cargo check`；
  build script 扫 bundle 时继续使用已记录的 resource override，仅用于检查。
- [ ] 记录 `/chat` initial graph、StudyRoute/PracticePage/CodeMirror raw+gzip；
  证明 CodeMirror 不在 `/chat` 静态或动态依赖图，且未复制 KaTeX runtime。
- [ ] 自动 a11y/RTL 断言：heading focus、aria-current、live region、所有 mutation
  纯键盘、shortcut focus exclusion、reduced motion、窄窗和 200% zoom。
- [ ] Windows WebView2 手工烟测：卡片键位、普通 quiz、code transcribe/
  variant、derivation、wrongbook retry、draft activate/reject、离线/desk child
  失效、亮暗主题、中英双语。
- [ ] 更新 master plan D-3 completion record 与本计划 completion record；
  `git diff --check`，本地提交，不 push。

---

## Suggested commit slices

1. `fix(study): scope D3 practice bridge to URL spaces`
2. `feat(study): add practice repository and page state`
3. `feat(study): move flashcard and quiz practice into notebook`
4. `feat(study): add lazy code and derivation practice surfaces`
5. `fix(study): retire legacy sidebar practice mutations`
6. `test(study): close D3 accessibility and performance gates`

每个提交必须独立通过其受影响测试；不得把依赖安装、后端合同、整页 UI 和旧面
删除压成一个不可审查的巨型提交。

---

## Acceptance Criteria

- `/study/:spaceId/practice` 是卡片 review、quiz attempt、practice generation
  和 draft review 的唯一可写前端；旧侧栏无重复 mutation。
- 所有 D-3 调用 owner+URL-space scoped；A/B deep link、快速切课和 wrongbook
  retry 不串数据，missing/foreign space 使用稳定结构化错误。
- due cards 可完整键盘复习；Space 与 1..4 只在练习域且非输入焦点时生效。
- choice/true-false/short-answer/code/derivation 均消费真实 active quiz；attempt
  只由 trusted service 写 activity，失败不丢页面内作答。
- CodeMirror 仅在 code question 动态加载，WebView 不执行代码；public wire 与
  DOM 不含 `reference/test_code/expr_py/accepted` 等私有判分材料。
- derivation 使用 DOM + KaTeX，ungraded/human-check 不冒充错误或通过；不引入
  Excalidraw、CAS 或 LaTeX parser。
- transcribe/variant 生成物始终先是 draft；unsupported fallback 诚实，模型
  无自动激活或判分权限。
- loading/empty/error/degraded/stale/pending、焦点、纯键盘、窄窗、200% zoom、
  reduced motion 和离开未提交作答均有真实测试。
- `/chat` 初始图无 PracticePage/CodeMirror；Web/Python/Rust 门全绿，bundle +
  Windows WebView2 手工 smoke 完成。

---

## Progress update — 2026-07-12

### Automated implementation and gates complete

- URL-space D-3 bridge、wrongbook opaque retry source、structured desktop errors：
  `353c5343`；
- PracticePage、卡片 review、quiz attempt、CodeMirror/KaTeX surfaces、B-3 draft
  generation、result wire minimization and legacy sidebar retirement：`d5133fd2`；
- editor/derivation interaction coverage：`e8a70f60`；首页 section-level degraded
  state and quiz-draft activation direct entry：`9aa6e8c5`。
- Latest Web gates: `npm run test:components` (13 files / 57 tests),
  `npm run test:chat-ux`, lint, TypeScript and production build all pass. The
  production build keeps `StudyRoute` at 10.90 kB gzip and leaves CodeMirror
  (121.59 kB gzip) and derivation/KaTeX (77.85 kB gzip) in independent lazy
  chunks, outside the `/chat` initial JS. `npm audit --omit=dev --json`
  reports zero production vulnerabilities.
- Latest Python D-3 regression: 29 passing tests across study routes, code
  grading, capture/M2, M4 and M6. The focused `WrongbookService` core and
  Rust bridge checks passed with the D-3 bridge slice.

### Manual smoke and D-3 closeout — 2026-07-15

- User completed the normal Python bundle/package smoke before this pass. Windows
  WebView2 smoke then passed current-space switching, card `Space`/`1..4`, normal
  quiz submission/result, wrongbook retry, dirty-leave cancel/confirm, and A/B
  state isolation. A dirty retry in the Python notebook did not leak its question,
  answer, queue, or mode into the empty Hadoop notebook.
- A disposable Hadoop quiz created through the trusted learning services exercised
  Python CodeMirror solve, deterministic transcribe and variant generation, draft
  activate/reject, trusted code grading, and derivation cloze. The activated
  transcription scored `2/2`; the derivation expression scored correctly while
  the reason remained explicitly human-check/ungraded. The two active smoke
  artifacts were archived after the pass and the rejected variant no longer
  appears in the product UI.
- Light/dark and Chinese/English rendered correctly and the original light/Chinese
  preference was restored. Force-stopping the desk child left the Tauri shell
  alive and produced the honest “学习空间暂时不可用” retry/back-to-chat state;
  the supported power-user restart path restored the child and the notebook.
- Development-mode observation: the first CodeMirror and derivation lazy imports
  under the Vite server triggered dependency pre-optimization and required one
  page reload. After the reload both surfaces passed. The production build already
  contains independent `CodePracticeSurface` and `DerivationPracticeSurface`
  chunks, so this is recorded as a dev-server cold-load observation rather than a
  release-bundle failure.

Bundle evidence, automated gates, Windows WebView2 smoke, fixture cleanup, and the
master-plan completion record are complete. D-3 is closed.
