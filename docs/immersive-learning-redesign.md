# 沉浸式学习体验重构方案（Immersive Learning Redesign）

> Status: **M1 in progress**（A1/A2/A3 + B1 的协议与快捷动作部分已落地，见下方 M1 实现记录）
> Last updated: 2026-07-05
> 前置阅读：[learning-layer.md](learning-layer.md)（Learning Layer 的边界与交互模式定义）
> 后续评审：[learning-runtime-alignment.md](learning-runtime-alignment.md)（harness 与 graph 层的改造点与排期分配,含 kq-kp gateway 门控这一 bug 级事项）
> 姊妹设计：[数学与代码练习系统](superpowers/specs/2026-07-05-study-math-code-practice-design.md)（ACADEMY→REPORT 重组 + 技能型学习的五级梯子,v0.3.0 起分三版落地）
> 前端愿景：[书桌·笔记本·白板课·咖啡杯](superpowers/specs/2026-07-06-desk-notebook-frontend-vision.md)（B3 的最终形态——情景化界面的隐喻选择、数据映射与 v0.4/v0.5 分期）

## 0. 出发点

学习 agent 与通用/工作 agent 的本质区别：工作 agent 的目的是**代替**人产出，
学习无法被代替（agent 不能替人吃饭）。因此成功指标不同：

```text
工作 agent：产出的速度与质量（用户介入越少越好）
学习 agent：学习者身上发生的变化（产出只是手段）
```

由此推出四条设计铁律，作为后续所有前端 / 行为层改动的评审标准：

1. **永不扣留，永远附注（answer-then-teach）** — 用户直接索取答案时照给，
   但答案后永远跟着知识点附注与学习提示。靠"故意不好用"逼人学习只会流失用户。
2. **学习者动手，她引导** — 主舞台是学习者的材料、笔记、练习；她以旁注、
   提示、追问出现在边上，不喧宾夺主。
3. **慢节奏，小步幅** — 讲解型回合默认短：一回合一个概念，以检查理解的
   问题收尾，把话语权交回学习者；不刷屏。
4. **记住学到哪** — 学习状态（知识点、薄弱点、进度）是一等公民，由对话
   自动沉淀，透明可编辑，驱动复习闭环。

评审用的一把尺：**这个改动是在加深学习，还是在绕过学习？**

## 1. 现状诊断

| 层 | 现状 | 问题 |
|---|---|---|
| 灵魂 | `hermes_cli/default_soul.py` 的 DEFAULT_SOUL_MD 是通用助手 persona（"executing actions via your tools"） | 纯工作 agent 灵魂，无任何教学行为约束 |
| STUDY 快捷动作 | `web/src/chat/study/studyPrompts.ts` 7 个巨型 prompt，固定"输出格式请固定为 1…8"的报告结构 | 一键报告生成器 = "代替"范式的典型。防幻觉约束（已确认/待确认/推断）是好的，保留 |
| 学习上下文 | `studyStore.ts` 12 个 textarea 手填 localStorage | 维护负担全在用户；agent 从不写回；实际会荒废 |
| Flashcard / Quiz | `flashcardStore` / `quizStore` 客户端判分 + SRS | 方向正确（学习者动手），但"复制 prompt → 粘贴 JSON 回来"是工作 agent 的遗留交互 |
| 主界面 | `ChatPage.tsx`：侧栏 + 消息流 + 输入框 + WorkspacePanel | 标准工作台布局，把用户放在"下单等交付"的位置 |

结论：Flashcard/Quiz/防幻觉标注证明方向感一直是对的，但整体骨架
（灵魂、快捷动作、布局）仍是工作 agent 范式，需要成体系地换。

## 2. 方案分层

### A. 灵魂层（hermes_core，行为）

对应 learning-layer.md Phase 2 的要求：教学行为的 canonical 定义放进
`hermes_core`，不能只活在 web 前端的 prompt 字符串里。

- **A1 重写 DEFAULT_SOUL_MD** — 从通用助手改为学习导师 persona，
  写入四条铁律的行为版。身份（卡布奇娜/小娜）不变。
- **A2 学习行为段** — `agent/prompt_builder.py` 新增
  `build_learning_conduct_prompt()`，进系统提示：
  - 节奏契约：讲解型回合短小、单概念、以理解检查收尾；
  - answer-then-teach 规则：识别"直接索取"意图 → 完整给出 → 尾部附
    知识点与"你刚才跳过了什么"；
  - 苏格拉底开关：hint-first 仅在用户明示（"别直接告诉我"）或练习
    场景启用，默认关闭——引导和说教一线之隔。
- **A3 知识点标注协议** — assistant 回复末尾输出一个机器可读块：

  ```text
  ```kq-kp
  [{"id": "...", "name": "贝叶斯定理", "gist": "一句话", "source": "材料锚点", "confidence": "confirmed|inferred"}]
  ```
  ```

  前端剥离该块、渲染为知识点 chips（见 B1）。解析失败静默降级为不显示，
  绝不污染正文。
- **A4 学习状态写回协议** — 类似的 `kq-study-update` 结构块，携带对
  studyStore 字段的增量建议；前端解析后由用户一键确认合并（后期可信任
  自动合并）。这是铁律 4 的机制基础，替代 12 个 textarea 手填。

### B. 交互层（web 前端）

**B1（近期，随 M1）**

- 知识点 chips：每条 assistant 消息尾部渲染 A3 产出的 chips，
  点击 → 加入复习队列（打通 `flashcardStore`）。这是"她记得你借助她
  跳过了什么"的入口。
- STUDY 七个快捷动作对话化改写：去掉固定 8 段输出格式，改为
  "每回合最多一个问题、信息够了只给一小步"；保留防幻觉标注约定。
- 分节展开：长讲解按标题折叠，默认展开第一节，"继续"由学习者点——
  节奏权在人（chat display 层改动）。
- 12 字段学习上下文折叠为一张摘要卡片 + "由对话更新"入口（吃 A4）。

**B2（中期）**

- Flashcard/Quiz 免粘贴：生成请求走后台 turn 直接入库；支持
  "从本次会话抽卡"（会话里已标注的知识点是现成素材）。
- 复习闭环：开屏显示"今日待复习 N 张"；直接索取答案时标注的知识点
  自动进入候选卡队列。

**B3（远期，交互范式大改的本体）**

- 新增 **Learning Space** 视图，三区布局：
  - 左：知识点树 / 学习路径（学到哪、薄弱点热区）；
  - 中：当前材料 / 练习 / 推导——**学习者的操作区，主舞台**；
  - 右（窄栏）：她的旁注对话，短消息、慢节奏。
- chat 从主舞台降级为旁注条。任务型工作（生成 PPT/文档等）仍走现有
  ChatPage——学习模式与任务模式并存，入口分开。

### C. 编排层（对接 phase 3.5 graph_engine）

引导式教学天然是多回合有状态的流，正是 `agent/graph_engine` 该承载的：

- **tutor loop 图**：probe（摸底）→ explain（小步讲）→ check（理解
  检查）→ advance / remediate 分支循环，每回合把观察写回学习状态。
- 给 graph_engine 的需求清单（先写进 contracts 层面的需求，不阻塞 3.5）：
  - 可中断、可恢复的多回合节点（学习者中途跑题/离开是常态）；
  - study-state 读写 port；
  - 廉价知识点抽取节点（规则或便宜模型，贴合"good quality, nearly
    free"哲学——结构确定性的部分不花钱）。

## 3. 里程碑

| 里程碑 | 内容 | 依赖 |
|---|---|---|
| **M1 理念验证** | A1 + A2 + A3 + B1（纯 prompt + 前端，无新后端模块） | 无；注意改 hermes_core Python 后需 sync-runtime-sources |
| **M2 闭环** | A4 + B2 | M1 的协议稳定 |
| **M3 范式切换** | B3 + C（Learning Space + tutor loop 图） | phase 3.5 graph_engine 落地 |

M1 刻意做薄：不动布局、不加模式开关，只换灵魂、加附注协议、改快捷
动作节奏。如果 M1 上手后"学习感"没有出现，说明理念表达有问题，
在大改布局前就能纠偏。

## M1 实现记录（2026-07-05）

- **A1** — `hermes_core/hermes_cli/default_soul.py`：学习导师 persona（身份不变，
  立场重写）。注意：SOUL.md 只在首次运行时播种，已有安装保留旧 SOUL.md——
  因此行为契约不放 SOUL，见下一条。
- **A2** — `hermes_core/agent/prompt_builder.py` 的 `LEARNING_CONDUCT_GUIDANCE`，
  由 `run_agent._build_system_prompt()` 紧跟 identity 槽注入，自定义 SOUL.md
  也无法剥离教学行为（有测试锁定）。
- **A3** — 协议前端侧 `web/src/chat/study/knowledgePoints.ts`（剥离 + 解析，
  防御式，流式期间未闭合的块不动）；chips 组件
  `web/src/chat/study/KnowledgePointChips.tsx`（点击 → flashcardStore 入库,
  已在队列的置灰）；接入 `ChatMessage.tsx`（正文/复制/朗读均用剥离后文本）;
  导出链路 `chatExport.ts` 把块转成可读的知识点列表。
- **B1（部分）** — `studyPrompts.ts` 七个快捷动作对话化（一次一问、小步交付、
  防编造与 no-emoji 保留），`chatUx.test.mjs` 断言同步改为新教学契约。
- **B1 未完成，留到下一轮**：长回复分节展开；12 字段学习上下文折叠为摘要卡片。

## 与 STUDY 四层学习管线的关系（2026-07-05 比对）

`student/study-module` 分支的 [四层学习管线设计](superpowers/specs/2026-07-01-study-four-layer-learning-pipeline-design.md)
（M1-M3 已收口,M4 已规划）与本方案是**互补的两条轨**：

```text
四层管线 = 数据/架构轨：learning.db、draft→active 审核、课程空间、owner 隔离
本方案   = 行为/交互轨：导师灵魂、节奏契约、answer-then-teach、kq-kp 协议
```

对方管线没有教学行为层（本方案 A1/A2 填空）；本方案没有持久化与信任边界
（对方管线补齐）。四层管线 §11 的"减少复制 JSON 主路径"与本方案的
对话化改造目标一致。

**M1 merge decision (2026-07-05):** stop at M1 by integrating only the shared
learning foundation (`learning_contract`, `learning.db`, owner/space isolation,
Learning Index, Output Writer, PlannerSpec, minimal `learning` toolset) while
keeping the immersive behavior M1 UI (`kq-kp` chips and conversational STUDY
prompts). M2/M3 backend-driven Flashcard/Quiz UI, desk routes, Tauri study
commands, and M4 state/evaluation work remain out of this merge. The one
exception is the M1 postfix trusted single-card capture path below, added so
`kq-kp` chips no longer write to legacy localStorage.

**合并时必须解决的冲突（按优先级）：**

1. **chips 的写入目标（已解决,2026-07-05 M1 postfix）**——知识点 chips
   已从 `flashcardStore`（localStorage `kabuqina.study.flashcards.v1`）
   改为受信单卡捕获路径（`FlashcardService.capture_card` +
   `POST /api/desk/study/flashcards/capture`），写入即激活,按 front 去重
   幂等,记 `flashcard.capture` 活动。设计记录见
   [知识点单卡捕获设计](superpowers/specs/2026-07-05-study-knowledge-point-capture-design.md)。
2. **A4（kq-study-update 写回协议）作废** —— 被 M4 的 `student_state` /
   `evaluation` artifact + "prompts 指示 agent 用 learning_draft_create"
   完全取代,且 M4 方案更优（owner 隔离、可审计）。A4 未实现,直接从
   本方案移除,B2 的写回部分改为消费 M4 的 API。
3. **studyPrompts 双改**（文本冲突,语义可合成）——本方案把七个动作对话
   化;分支把 flashcard/quiz 生成 prompt 工具化（learning_draft_create）。
   合并后需要第三轮：对话化的节奏 + 结尾用 learning 工具建草稿,
   两者叠加而非二选一。M4 方案已要求 profile/path/evaluation prompts
   工具化,届时以对话化版本为底稿。
4. **12 字段上下文折叠（B1 遗留项）让位于 M4** —— M4 会把
   `kabuqina.study.context.v1` 迁移为 backend `student_state` 并做最小
   Web 面;B1 的"摘要卡片"不再单独做,并入 M4 的 StudySection 改造。
5. **B3 学习空间 vs M6 生命周期 UI** —— 同一块领土：M6 按
   `课程设置→计划→学习→练习→评估` 重组,B3 定义屏幕形态（学习者主
   舞台+旁注对话）。必须合并设计,建议 B3 的三区布局作为 M6 的呈现层。

**无冲突可直接合流的**：灵魂/学习行为段（分支未动 run_agent/soul）;
kq-kp 协议本身（消息级轻量标注,与 artifact 管线正交——长期可把
"知识点被保存"记为 `learning_activities`,喂给 Learning Index 的
weak_points 投影）。

## 4. 风险与取舍

- **标记协议污染正文** — 严格约定尾部块；前端剥离；解析失败静默降级。
- **慢节奏 vs 赶 deadline 的用户** — 铁律 1 保底：永不扣留。节奏契约
  只作用于讲解型回合，任务型请求不受限。
- **hint-first 变说教** — 默认关闭，只在明示与练习场景开。用在卡住处
  是引导，用在已懂处是折磨。
- **双模式复杂度** — M1/M2 不引入模式概念，只改行为与附注；模式切换
  推迟到 B3 与布局一起做。
- **协议与 3.5 的接口错位** — C 节需求清单先行，graph_engine 的
  contracts 定型前对齐一次。

## 5. 成功标准（M1 即可度量）

- 学习会话中用户回合的字数/回合数占比上升（学习者说得更多）;
- "直接索取答案"的回合 100% 带知识点附注；
- 知识点 chip → 复习卡的转化率、due 复习完成率（M2 起）；
- 讲解型回合的 assistant 平均长度下降。
