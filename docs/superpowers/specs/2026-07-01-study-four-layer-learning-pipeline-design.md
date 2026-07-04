# STUDY 四层学习管线设计

**日期：** 2026-07-01（2026-07-02 评审修订；2026-07-04 M3 收口）

**状态：** 已确认，M1-M3 已收口，M4 待实施

**范围：** STUDY 模块、共享 Agent Core、桌面端与 Gateway 的学习产物契约

**修订记录：** 2026-07-02 依据评审补齐了动工前必须冻结的契约：跨存储 fan-out 的部分成功语义（§4.1、§7）、跨库引用自洽约束（§5.1、§8.2）、语义 reviewer 失败态（§4.3、§6）、迁移的 draft/active 判定（§12）、Desktop owner id 来源与恢复（§8.3）、Gateway owner 粒度（§8.3、§10.3）、`tutoring_note`/`evaluation` 审核默认（§6）、M1 owner 地基验收（§13）、Web 测试栈（§14）。2026-07-04 收口 M2：课程空间、闪卡草稿激活/拒绝、真实复习活动、legacy 闪卡迁移、`learning.output.created` 非阻塞刷新链路已落地；M3 限定为 quiz。2026-07-04 收口 M3：quiz 草稿激活/拒绝、题目 materialize、确定性答题评分、`quiz.attempt` 活动、legacy quiz 迁移和 backend-driven QuizPanel 已落地；Gateway `/study` 命令仍为 M5。

## 1. 背景

当前 STUDY 模块已经包含课程背景、学习上下文、知识库、学习路径、资源包、辅导提示、闪卡和测验等能力。学生提交的新功能扩展了可用范围，但各功能仍主要以独立面板、独立 localStorage 和“让 AI 生成 JSON → 用户复制 → 再导入”的方式串联。

这会带来三个问题：

1. 每个功能都在重复定义输入、AI 生成、审核、保存和使用流程。
2. 学习产物无法被桌面端与 Gateway 可靠共享，也没有一致的课程边界和所有者隔离。
3. 已有的 `Read → Material Index → Planner → Writer` 四层架构只覆盖文件型交付物，尚未为学习型产物提供同样清晰的契约。

本设计不把 STUDY 做成另一套孤立 Agent，也不把学习能力强行塞进 PPT/文档管线。它保留四层思想，并为学习场景建立并列、可复用的实现：

```text
文件交付物：Read → Material Index → Deliverable Planner → File Writer
学习型产物：Read / Student State / Activity → Learning Index → Learning Planner → Output Writer
```

STUDY 是 Learning Planner 与 Output Writer 的第一个产品实践场景，但二者属于共享 Agent Core，不是 Web 端私有逻辑。

## 2. 目标

1. 用统一的“从读到写”框架规范 STUDY 的每一类功能，再决定保留、合并或调整交互。
2. 在 Planner 下建立轻量策略框架，使现有 PPT/文档规划与新增 Learning Planner 并列演进。
3. 在 Writer 下增加通用 Output Writer，负责非文件型结构化产物的校验、保存、版本和状态转换。
4. 以课程工作区为边界，统一保存知识、计划、练习、结果和学习活动。
5. 桌面端与 Gateway 共用语义、契约和存储，同时保持默认身份隔离。
6. 将 AI 生成内容统一置于可审核草稿状态；真实用户行为则直接记入学习状态。
7. 分纵向切片迁移现有功能，保持每个阶段都可用、可回滚。

## 3. 非目标

- 不在本阶段创建独立 Planner 执行引擎、工作流引擎或第二套 Agent loop。
- 不修改 Material Index v1 的现有契约。
- 不把所有 Planner 逻辑重写成类层级；框架只负责激活、提示、契约和审核策略。
- 不在本阶段实现跨设备同步、跨身份自动合并或云端课程空间。
- 不在共享 core 中加入 DPAPI；本地数据库使用 ACL 与数据最小化保护。
- 不承诺语义审核具有代码级正确性保证；它仍由模型提示驱动。
- 不在一次发布中完成全部 STUDY 迁移。

## 4. 架构决策

### 4.1 两条并列四层管线

```text
                              ┌─ Deliverable Planner ─ File Writer
Read ─ Material Index ────────┤
                              └─（现有 PPT / PDF / HTML / DOCX）

Read ─┐
State ├─ Learning Index ─ Learning Planner ─ Output Writer ─ Learning Store
Event ┘                                             └─────── File Writer（可选）
```

两条管线共享“读取、确定性索引、规划、写入”的边界，但不共享不合适的数据模型：

- Material Index 描述来源材料中的证据，用于生成文件交付物。
- Learning Index 描述某一课程空间当前可用的学习上下文，用于教学决策和学习产物。
- Resource Pack 等混合产物可以由一次规划同时分发给 Output Writer 和 File Writer。

**跨存储 fan-out 没有共享事务。** Output Writer 写 `learning.db`，File Writer 写文件系统，二者不能原子提交。因此 fan-out 采用**以 Output Writer 为准的部分成功语义**：先由 Output Writer 落地并激活 artifact 记录，再由 File Writer 生成导出文件。File Writer 失败不回滚已保存的学习 artifact，只在该 artifact 上记录 `export_status=failed` 供重试；Output Writer 失败则整个产物视为未创建，已生成的孤儿文件按临时导出处理、可安全清理。实现不得出现"文件已给用户、但 `learning.db` 里查不到对应 artifact"的状态。

Learning Index 与 Material Index 并列，而不是在 Material Index 中增加学生状态、错题或复习进度。这样可以保持 Material Index 的确定性证据契约，也避免学习状态污染所有文件生成场景。

### 4.2 Planner 采用轻量策略框架

已存在的 `build_deliverable_planner_prompt` 是共享 Agent 的 Planner 提示，不是 Planner 类。对此有三种可选形态：

| 方案 | 优点 | 代价 |
|------|------|------|
| 继续增加普通函数 | 改动最小 | 激活条件、契约、审核规则会继续散落；难以查看完整 Planner 家族 |
| **轻量 `PlannerSpec` / Registry（采用）** | 显式并列 Planner；复用现有 Agent loop；便于测试激活、提示、契约和审核 | 需要建立注册与漂移检查 |
| 完整 Planner 基类与执行器 | 生命周期最统一 | 与现有 Agent loop 重叠，抽象和迁移成本过高 |

采用轻量策略框架：

```text
Planner
├─ Deliverable Planner
│  ├─ PPT specialization
│  └─ Document specialization
└─ Learning Planner
```

`PlannerSpec` 只声明：

- Planner id 与适用领域；
- 激活条件；
- prompt builder；
- 接受的 index / context 契约；
- 允许输出的 artifact kinds；
- 确定性校验和语义审核策略。

它不负责执行工具、不拥有重试循环，也不替换 `AIAgent`。现有 Agent loop 仍然完成推理和工具调用。

#### 单一事实来源

共享 core 中新增 `learning_contract.py`，作为学习产物种类、版本、状态、审核级别与 Planner/Writer 词汇的唯一事实来源。`PlannerSpec` 引用这些常量。

`python/src/capability_registry.py` 继续负责产品能力目录、管线展示和 readiness，不复制 Planner prompt 或产物 schema。它只引用稳定 id，并由漂移测试保证所引用的 Planner、artifact kind 和 stage 均存在。

### 4.3 Planner 输出必须经过 review

“Plan 需要 review”是管线契约，而不是某个 UI 按钮的偶然行为。

审核分两级：

1. **确定性校验，始终执行。** 校验 envelope 版本、artifact kind、必填字段、引用、数量限制、状态转换和 owner/space 边界。
2. **语义审核，按产物类型执行。** 知识库、学习路径、资源包、批量闪卡和测验必须经过 reviewer prompt，检查来源支撑、难度、重复、答案泄露、歧义和教学适配。

语义审核只能降低风险，不能被表述为代码级事实保证。外部来源材料仍保留手动审计入口；“自动安全门”不能删除用户检查来源、题目和答案的能力。

**reviewer 失败态。** 语义审核是额外 LLM 调用，会超时、被预算耗尽（见 DECISIONS 中 budget/exit-family 工作）或异常。确定性校验已通过、但语义 reviewer 未能产出结论时，草稿**停在 `review.status = pending`**：既不因 reviewer 失败自动 `active`，也不自动 `reject`。UI/命令应能看到"待复核"原因并允许重试。只有 reviewer 明确给出通过意见后，草稿才进入可被用户激活的状态。

## 5. Learning Index

### 5.1 职责

`learning_index_build` 是确定性工具，只读取已保存且当前有效的数据：

- 课程空间元数据；
- Read / Material Index 中的来源引用；
- 已激活的知识库、学习计划、资源包、闪卡和测验；
- 用户实际学习活动、答题结果与复习记录；
- 当前学生偏好和明确保存的学习状态；
- 到期复习项、薄弱点和未完成计划。

它输出一个有版本的、大小受限的课程快照，供 Learning Planner 使用。

**来源必须自洽。** Read / Material Index 的来源可能存在于 `state.db`、聊天 session 或临时文件中，这些在 `learning.db` 之外、且可能被清理。`learning.db` 与它们没有外键约束。因此凡进入 Learning Index 和 learning artifact 的来源引用，**必须内嵌足以自洽的稳定摘录**（引用 id + 必要片段），不得依赖运行时仍能回读某个 session/state.db/临时文件。来源原件消失时，已保存产物仍应可读、可审计。

### 5.2 非职责

Learning Index 不：

- 调用 LLM；
- 选择教学策略；
- 自动激活 AI 草稿；
- 修改 Material Index；
- 将“未审核内容”当作课程事实；
- 根据单次错误永久标记学生能力。

### 5.3 激活内容规则

默认只把 `active` 产物写入 Learning Index。`draft`、`rejected` 和 `archived` 产物只出现在管理视图中，不进入教学上下文。用户直接产生的行为记录可以立即参与索引，例如：

- 闪卡评分；
- 测验作答和得分；
- 用户手动修改学习偏好；
- 计划项完成或跳过；
- 用户确认的纠错结果。

## 6. Learning Output Envelope

Output Writer 接受统一的 `LearningOutputEnvelope v1`，但 `payload` 不是任意对象。它必须按 `kind` 使用判别联合 schema。

公共字段：

```json
{
  "version": 1,
  "kind": "flashcard_deck",
  "space_id": "course-space-id",
  "title": "Chapter 3 Review",
  "source_refs": [],
  "payload": {},
  "review": {
    "mode": "semantic",
    "status": "pending"
  }
}
```

v1 产物类型：

| `kind` | 核心 payload | 默认审核 |
|--------|--------------|----------|
| `student_state` | 可编辑偏好、目标、约束，不含固定能力标签 | 确定性 |
| `knowledge_base` | 概念、解释、来源引用、待核查项 | 语义 |
| `learning_plan` | 目标、阶段、任务、顺序、完成标准 | 语义 |
| `resource_pack` | 资源条目、用途、来源、可信度说明 | 语义 + 手动审计入口 |
| `flashcard_deck` | 卡组与卡片，含正反面、标签、来源 | 批量时语义 |
| `quiz` | 题目判别联合、答案、解析、评分规则、来源 | 语义 |
| `tutoring_note` | 辅导目标、提示层级、误区和下一步 | 默认确定性；引用外部来源或含题目答案时升级语义 |
| `evaluation` | 观察、证据、薄弱点、建议，不做人格/能力定性 | 默认语义（可降级）|

每个 kind 都有独立 schema、尺寸限制和迁移规则。例如 quiz 的选择题、判断题和简答题必须使用各自的题型 schema，不能依靠前端猜测字段。

`review.status` 的取值与转换：`pending`（确定性已过、等待语义结论或人工激活）、`approved`（语义通过、可激活）、`rejected`。语义 reviewer 不可用时停在 `pending`（见 §4.3），不得静默跳过。仅确定性审核的 kind（如 `student_state`）跳过语义步骤后直接可激活。

## 7. Output Writer

Writer 家族调整为：

```text
Writer
├─ File Writer
└─ Output Writer
```

File Writer 继续生成 PPTX、PDF、HTML、DOCX 等文件。Output Writer 负责非文件型、可持续使用的结构化产物：

1. 验证 `LearningOutputEnvelope` 与 per-kind payload。
2. 从运行时上下文注入 owner，拒绝模型传入 owner id。
3. 写入 `learning.db`，生成 artifact id 和版本。
4. 将 AI 内容保存为 `draft`。
5. 执行允许的状态转换：`draft → active/rejected`、`active → archived`。
6. 发出产物事件，供桌面端或 Gateway 展示。
7. 对真实用户行为直接写入 activity/item 状态，不伪装成 AI artifact。

Resource Pack 可以同时产生结构化学习资源和导出的文件清单，因此 Planner 可将同一个已审核计划分别交给 Output Writer 与 File Writer；两个 Writer 各自拥有自己的输出契约。二者无共享事务，按 §4.1 的以 Output Writer 为准的部分成功语义执行（先 Output Writer 落地，再 File Writer 导出，导出失败不回滚学习 artifact）。

## 8. 状态与持久化

### 8.1 课程工作区

学习数据按 `learning_space` 组织。一个 space 对应一门课程、一个长期主题或一个项目式学习单元。聊天 session 只提供临时上下文，不是学习数据的持久边界。

每个 owner 可以：

- 创建多个课程空间；
- 选择当前空间；
- 查看该空间的草稿、活动和有效产物；
- 在空间之间显式复制或导入内容。

### 8.2 独立数据库

在公共 Hermes root 下使用独立的 `learning.db`，而不是扩展现有 `state.db`。原因是 Gateway profile 使用不同 `HERMES_HOME`，而学习语义需要由桌面与 Gateway 共用；同时独立数据库便于 schema 演进、备份和回滚。

数据库使用 SQLite WAL，并复用现有 SessionDB 的并发原则：短事务、busy timeout、写入锁重试和启动时 schema reconciliation。

v1 表：

| 表 | 用途 |
|----|------|
| `learning_spaces` | owner 下的课程空间与当前状态 |
| `learning_artifacts` | 版本化 envelope、kind、review 与 lifecycle 状态 |
| `learning_items` | 闪卡、题目、计划项等可单独操作的子项 |
| `learning_activities` | 作答、评分、复习、完成、跳过等用户行为 |
| `learning_migrations` | localStorage 迁移进度和幂等标记 |

数据库保存结构化学习数据，不保存 API key，不默认复制完整聊天或原始外部文件。来源使用稳定引用和必要摘录，遵守数据最小化——但摘录量必须满足 §5.1 的自洽约束，即来源原件（session/state.db/临时文件）消失后产物仍可读、可审计。

### 8.3 Owner 隔离

默认身份隔离，未来再提供显式绑定：

- Desktop 使用稳定的本地 owner id。该 id 从产品数据目录（`%LOCALAPPDATA%\com.kabuqina.app`）下一个持久 owner 记录派生并随 `learning.db` 一同备份；不从机器指纹或用户名派生，以免换机/改名后失配。**owner id 与其 learning 数据同目录持久化，是 `learning.db` 的一部分**，因此重装但保留数据目录时 id 不变；数据目录被重建导致 id 缺失时，生成新 id 并把已存在但"无主"的 space 呈现为可显式认领的迁移入口，绝不静默丢弃或自动重绑。
- Gateway 使用 `gateway:<platform>:<hashed-user-id>`。owner 粒度是**发消息的个人**，不是群/频道：群聊中的 space、草稿和 approve/reject 按 sender 隔离，群内其他成员默认既不可见也不可批；因此 sender 身份识别必须可靠，无法可靠识别 sender 的消息不得执行信任边界操作。
- 所有查询和写入都必须同时约束 `owner_id` 与 `space_id`。
- 模型工具 schema 中不出现 `owner_id`；由运行时 `LearningExecutionContext` 注入。
- 将来若支持身份绑定，必须显式确认并记录映射，不能根据昵称或平台资料自动猜测。

## 9. Core、Policy 与桌面层分工

遵循仓库的 core/overlay 决策规则：

### `hermes_core/`

- `PlannerSpec` / Planner registry；
- `learning_contract.py`；
- Learning Index、Output Writer 与 learning toolset；
- `learning.db` 存储语义；
- Gateway `/study` 命令的通用语义；
- `LearningExecutionContext` 及 owner 注入接口。

这些行为在 web child 与 gateway child 中应一致，因此属于自有 Agent Core。

### `python/src/`

- Desktop owner id 的建立与注入；
- desk_server 的受信 API；
- 非阻塞桌面事件桥；
- 数据目录、ACL 和本地运行时集成。

### `web/src/`

- 学习生命周期 UI；
- 草稿审核、激活、拒绝、归档；
- localStorage 一次性迁移；
- 闪卡、测验与课程空间交互。

### 不使用 overlay 承载学习语义

学习产物、Planner 和存储不是桌面专属胶水，不应通过 monkey patch 实现。只有 Tauri/loopback 特有的投递和身份来源留在桌面集成层。

## 10. 工具、事件与 Gateway

### 10.1 Learning toolset

新增 `learning` toolset，并加入安全 keep-list。建议按操作能力拆分，而不是暴露通用 SQL 或任意 payload 写入：

- 列出/创建/选择课程空间；
- 构建 Learning Index；
- 创建类型化草稿；
- 列出草稿和有效产物；
- 记录受约束的学习活动；
- 获取到期复习与测验摘要。

激活、拒绝、归档等信任边界操作只允许受信 UI/API 或确定性 Gateway 命令执行，普通模型工具调用不能自行批准自己的内容。

### 10.2 桌面事件

学习草稿不使用当前最长阻塞 300 秒的 `DeskInteractionManager`。创建成功后立即返回 artifact id，并发出非阻塞事件：

```text
learning.output.created
```

Web 根据事件刷新草稿列表或显示通知。用户何时审核与 Agent turn 解耦。

### 10.3 Gateway 命令

Gateway 使用确定性命令激活学习工作区和草稿，不把权限操作交给自然语言意图识别：

```text
/study list
/study new <name>
/study use <space>
/study drafts
/study approve <artifact-id>
/study reject <artifact-id>
```

命令处理器从平台上下文建立 owner（个人级，见 §8.3），并验证 artifact 属于当前 owner 和 space。群聊中一名成员的 approve/reject 只作用于该成员自己的 space，不影响同群其他 owner。自然语言仍可请求生成草稿，但不能替代 approve/reject 命令。

## 11. STUDY 交互整合

迁移后的主导航按学习生命周期组织，而不是按“功能卡片堆叠”：

```text
课程设置 → 学习计划 → 辅导/学习 → 练习/复习 → 评估/调整
```

现有功能的合并方向：

| 当前能力 | 归入流程 | 处理方式 |
|----------|----------|----------|
| 12 项学习上下文 | 课程设置 | 合并为课程空间与可编辑 student state，渐进展示字段 |
| 知识库 | 课程设置 / 学习 | 作为有来源、可审核的 knowledge artifact |
| 学习路径 | 学习计划 | 由 Learning Planner 生成草稿，审核后激活 |
| 资源包 | 学习计划 / 学习 | 结构化 artifact；保留外部来源手动审计 |
| 快捷辅导动作 | 辅导/学习 | 变成基于当前 Learning Index 的 Planner 意图，不维护独立数据岛 |
| 闪卡 | 练习/复习 | 卡组是 artifact；评分和复习调度是直接 activity 写入 |
| 测验 | 练习/复习 | 题库是 artifact；答题和成绩是直接 activity 写入 |
| 学习评估 | 评估/调整 | 使用真实活动证据生成 evaluation 草稿，用户确认后影响计划 |

减少“复制 JSON → 粘贴导入”的主路径。AI 产出后，用户在统一草稿箱预览、审核并激活；高级菜单保留导入、导出、来源审计和原始 JSON 查看。

## 12. 旧数据迁移

现有 STUDY localStorage 数据采用一次性自动导入：

1. Web 检测每个旧 key 是否存在，以及 `learning_migrations` 是否已完成该 key。
2. 每个 key 独立解析、校验和导入，使用幂等 migration id。
3. 成功项写入默认课程空间。现有 localStorage 没有 draft/active 概念——里面的一切都是用户此前显式保存的，因此**迁移一律导入为 `active`**，并记录 `origin=legacy_local_storage`（不引入无法从旧数据判定的前置条件）。迁移后新产生的 AI 内容才走 `draft → active` 审核路径。
4. 单个 key 失败不阻塞其他 key，UI 显示可重试和导出原数据入口。
5. 旧 localStorage 保留一个发布周期，只读作为回滚保障。
6. 下一发布周期确认迁移稳定后再移除旧读取路径；不静默删除无法解析的数据。

迁移必须覆盖现有三个已发布 key——`kabuqina.study.context.v1`、`kabuqina.study.flashcards.v1`、`kabuqina.study.quiz.v1`——及未来新增 key，并用实际旧版本样本测试。（注意 `kabuqina-study-*` 是 window 事件名而非存储 key，迁移只处理 `.v1` 存储 key。）

## 13. 交付里程碑

每个里程碑都是可独立验收的纵向切片。

### M1：共享基础

- `learning_contract.py` 与 per-kind schemas；
- `PlannerSpec` / registry 及 Deliverable Planner 适配；
- **`LearningExecutionContext` + owner 注入**（Desktop owner id 来源、Gateway owner 派生），作为所有后续切片的安全地基，必须在 M1 落地，不能延后；
- `learning.db`、owner context 与基础 store；
- Learning Index / Output Writer 最小骨架；
- capability registry 引用与漂移测试。

验收：现有 PPT/文档规划行为不变；两个 child 可以在不同 owner 下安全读写隔离的课程空间；**owner 越权、模型伪造 owner、跨 Gateway 用户访问的隔离测试在 M1 即为绿**（不等到后续里程碑）。

### M2：课程空间 + 闪卡

- 课程空间选择；
- flashcard deck 草稿、审核、激活；
- 真实评分和复习活动；
- localStorage 闪卡迁移；
- 非阻塞桌面事件。

验收：完整走通 `Read/State → Index → Plan → Review → Output → Practice`，不再需要复制 JSON。

收口记录（2026-07-04）：M2 以 `flashcard_deck` 纵向切片落地。Core 新增 `FlashcardService`，将 active deck materialize 为 `learning_items`，并以 `flashcard.review` 记录真实复习活动；Desk API 暴露 `/api/desk/study/spaces`、`/api/desk/study/drafts`、`/api/desk/study/artifacts/{id}/activate|reject`、`/api/desk/study/flashcards`、`/api/desk/study/flashcards/review`、`/api/desk/study/migrations/flashcards`；Tauri 对应注册 `cmd_study_*` 代理；Web 使用 `study-learning-event` 刷新课程空间、草稿和卡片列表。legacy 闪卡迁移 id 固定为 `localStorage:kabuqina.study.flashcards.v1`，迁移后的旧卡片直接进入 active practice state。Gateway `/study` 命令仍为 M5，不在 M2 中提前实现。

### M3：测验

- quiz 判别联合 schema；
- 题目审核和激活；
- 答题、评分、解析和活动写入；
- localStorage quiz 迁移。

验收：题目内容与答题行为分离；重新生成题库不会覆盖历史成绩。

收口记录（2026-07-04）：M3 以 `quiz` 纵向切片落地。Core 新增 `QuizService`，将 active quiz materialize 为 `learning_items` 的 `quiz_question`，并以 `quiz.attempt` 记录真实提交活动；评分保持确定性，`choice` 精确匹配选项索引，`true_false` 匹配布尔值，`short_answer` 仅将规范化文本与 `answer`/`accepted` 比较。Desk API 暴露 `/api/desk/study/quizzes`、`/api/desk/study/quizzes/{artifact_id}/questions`、`/api/desk/study/quizzes/{artifact_id}/submit`、`/api/desk/study/migrations/quizzes`，并复用通用 artifact activate/reject 路由分派 quiz；Tauri 注册 `cmd_study_quizzes`、`cmd_study_quiz_questions`、`cmd_study_quiz_submit`、`cmd_study_migrate_quizzes`；Web QuizPanel 从 backend 读取课程空间、草稿、active quiz 和提交结果。legacy quiz 迁移 id 固定为 `localStorage:kabuqina.study.quiz.v1`。语义/LLM 短答评分和 Gateway `/study` 命令仍留到后续里程碑。

### M4：学生状态、评估与学习计划

- student state；
- evaluation；
- learning plan 与计划项活动；
- 评估结果影响后续 Planner 输入，但不自动固化能力标签。

### M5：知识库、资源包、辅导与质量门

- knowledge base / resource pack / tutoring note；
- 必需的语义 reviewer；
- 外部来源审计；
- Gateway `/study` 命令。

### M6：生命周期 UI

- 按课程设置、计划、学习、练习、评估重组 STUDY；
- 统一草稿箱；
- 高级导入/导出/来源审计；
- 清理一个发布周期后的旧 localStorage 读取路径。

## 14. 测试与质量门

### Core 单元测试

- Planner 激活、prompt 拼装、允许 kind 和 review policy；
- Deliverable Planner 适配前后 prompt 行为等价；
- per-kind schema 的有效/无效样本；
- Learning Index 只包含 active 产物和允许的活动；
- Output Writer 状态机、版本和并发写入；
- owner/space 越权、模型伪造 owner、跨 Gateway 用户访问；
- WAL、busy retry、schema reconciliation；
- `/study` 命令解析、确认和权限校验。

### Desktop 集成测试

- runtime owner 注入；
- common Hermes root 解析；
- desk API 与非阻塞 `learning.output.created` 事件；
- web child 与 gateway child 并发访问同一数据库但保持 owner 隔离；
- 默认与 power-user tool policy 都正确暴露 learning toolset。

### Web 测试

沿用现有 Web study 测试栈——`node:test` + `node:assert`，通过 `typescript.transpileModule` 转译（见 `web/src/chat/study/studyStore.test.mjs`），仓库当前没有 Vitest 配置。除非单列一项"迁移到 Vitest + React Testing Library"的工作，否则本设计不引入第二套 runner，以免 store 逻辑用一套、组件用另一套。覆盖：

- 课程空间选择和切换；
- 草稿预览、approve、reject、archive；
- 闪卡评分与测验提交；
- 每个 legacy key 的成功、部分失败、重试和幂等迁移；
- 数据库暂不可用时不丢失用户输入；
- 来源审计入口不会被自动安全门隐藏。

### 每个里程碑的门禁

- 受影响的 Core/Python/Web 测试；
- `web` lint 与 build；
- capability registry validation；
- 旧 PPT/PDF/HTML/DOCX Planner 回归；
- 数据迁移与 owner 隔离回归。

## 15. 风险与约束

1. **Planner 事实性仍是提示约束。** 确定性 schema 和审核不能证明内容正确，来源引用和人工审核仍重要。
2. **双进程并发。** desktop 与 Gateway 不共享内存，所有选中空间和 owner 状态必须显式持久化或注入。
3. **契约漂移。** Planner、Output Writer、capability registry 和 Web 类型必须由共享 id、生成类型或漂移测试约束。
4. **迁移可逆性。** 一个发布周期内不得依赖删除旧 localStorage 来证明迁移成功。
5. **抽象过度。** PlannerSpec 不能演变成第二个执行器；若字段不参与激活、提示、契约或审核，应暂不加入。
6. **UI 一次性重构风险。** 先用闪卡和测验证明数据链路，最后再调整整体信息架构。

## 16. 最终决策摘要

- 四层框架适用于每一项 STUDY 能力，但学习场景使用并列的 Learning Index。
- Planner 使用轻量策略注册框架；Deliverable Planner 与 Learning Planner 并列，现有 Agent loop 继续执行。
- Writer 增加通用 Output Writer；STUDY 是第一个消费者。
- 所有 AI 学习内容先保存为 draft，并始终经过确定性校验；需要语义审核的类型通过 reviewer 后，仍由用户决定是否激活。
- 用户真实行为直接写入 activity，不经过草稿审批。
- 学习数据保存在公共 Hermes root 的独立 `learning.db`，以 owner + course space 隔离。
- Desktop 与 Gateway 默认是不同 owner；未来仅通过显式绑定合并。
- Gateway 使用确定性 `/study` 命令承担 approve/reject 等权限操作，owner 粒度为个人。
- 采用纵向切片交付，先基础与闪卡，再测验、状态/计划、知识/资源，最后重组 UI。
- 跨存储 fan-out 以 Output Writer 为准，采用部分成功语义，不出现"文件已给用户但 artifact 查不到"。
- 语义 reviewer 不可用时草稿停在 `pending`，绝不自动激活或拒绝。
- 学习产物内嵌自洽摘录，来源原件消失后仍可读可审计。
- 现有 localStorage 迁移一律导入为 `active` 并记 `origin=legacy_local_storage`。
- `LearningExecutionContext` + owner 注入是 M1 地基，owner 隔离测试在 M1 即为绿。
