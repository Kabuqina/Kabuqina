# Study 端到端学习生产链实施计划

> 日期：2026-07-31
> 里程碑：S3H
> 依赖：Study 五页行为规格、S3A–S3G 前端、B-13 revisioned 学习地图

> **后续裁决：** S3H 已连通“显式请小娜整理”的生产路径，但它不是 Study 的默认完成形态。
> 正常的非对话式、渐进式知识核生产由
> [Study 知识核编译器实施计划](2026-07-31-study-knowledge-core-compiler-plan.md)（S3I）接续；
> S3I 完成后，小娜仅作为异常处理和主动重整入口。

## 0. 当前状态（2026-07-31）

- S3H-1–S3H-5 已实现：材料窗口读取、知识核草稿合同、审核采用、学习地图发布、
  计划目录校验、服务端当前位置、学习范围导航和同核练习已连通。
- 小型固定 fixture、Study 路由、四个相关前端页面、runtime import、Web production build
  与 Rust `cargo check --lib` 已通过。
- S3H-6 仍为黄色：产品方提供的《Python程序设计》PDF 需要在实际桌面进程中完成内容与视觉
  手工验收；在该验收完成前不把整个 S3H 标为绿色。

## 1. 为什么需要这个计划

S3A–S3G 已经完成五页容器、单知识核学习/练习界面、材料阅读器、计划行动 UI、
共享知识核游标和恢复合同；B-13 已经提供只读学习地图和 revisioned location。
但这些能力目前只会**消费**已经存在的知识核、练习和计划行动，没有完成以下生产链：

```text
已采用课程材料
  → 小娜基于可定位正文提出知识核草稿
  → 用户审核并采用
  → 物化为 active 知识核并进入学习地图
  → 计划行动绑定真实三级目录范围
  → 启动行动时选中该范围内的知识核
  → 学习/练习共享位置回投到计划页
```

因此“材料已在书立上，但计划只有目录、学习页没有知识核”是当前真实状态，不是单纯
的空态文案问题。

## 2. 不变的产品边界

1. 目录最多三级，来自已采用材料的可靠结构；推断目录必须先确认。
2. 计划项是目录范围下的行动，不是第四级目录，也不按每个知识核生成一项。
3. 学习与练习一次只显示一个知识核，并共用同一个 `knowledgeCoreId`。
4. 小娜生成的知识核、改编题和补充题必须先成为 draft；模型不能自行激活。
5. 每个知识核必须有可定位来源；无法定位的内容不能进入 active 学习地图。
6. 当前进度是“正在这个行动范围的这个知识核上”，不是掌握度、覆盖率或自动达标判断。
7. 完成/跳过计划行动仍由用户明确触发；移动知识核不自动宣称完成。

## 3. 目标数据合同

### 3.1 知识核草稿

课程材料知识核沿用 `flashcard_deck` 的审核和激活生命周期，但每张 card 增加：

| 字段 | 含义 |
|---|---|
| `knowledge_core_id` | 稳定知识核 ID；同一来源范围重复生成时保持稳定 |
| `outline_node_id` | 已确认三级目录中的真实节点 ID |
| `order` | 节点内及课程内稳定顺序 |
| `source_refs` | 材料 artifact、页码/章节 locator、来源摘录指纹 |

`front` 是学习页标题，`back` 是最关键的一句。card 级来源随物化后的 item 保存，
学习地图不得再依赖“整副卡片共用一个 artifact 级来源”的偶然结构。

### 3.2 计划行动

`learning_plan.phases[].tasks[]` 继续使用：

- `title`
- `mode = learn | practice | review`
- `outline_node_id`
- `done_when`

采用时校验 `outline_node_id` 必须存在于当前已确认目录；没有可靠目录时允许显式未绑定，
但不得伪造节点 ID。

### 3.3 共享学习位置

服务端 location 在 B-13 现有字段上增加：

- `planItemId`
- 由当前知识核解析出的 `outlineNodeId`

`planItemId` 必须属于当前 active plan 且其目录范围与知识核一致。前端
`localStorage` 仍只是离线投影，不能覆盖更新的服务端 revision。

## 4. 实施切片

### S3H-1 知识核纵向合同

- 扩展 `learning_contract.py` 对 card 级知识核字段和来源的严格校验。
- `FlashcardService.activate_deck()` 将字段物化到每个 flashcard item。
- `LearningMapService` 从 item 读取核 ID、目录、顺序和来源。
- 兼容已有单卡 `kq-kp` capture；旧普通 flashcard 不自动升级为课程知识核。

验收：

- 一份多 card draft 采用后生成多个稳定知识核；
- 每个核能回到材料 locator；
- 重复采用、刷新 map 不改变 ID 和顺序；
- 无来源或未知目录节点的 draft 不能激活为课程知识核。

### S3H-2 小娜材料整理能力

- 学习 planner 明确区分“普通复习卡”和“课程知识核草稿”。
- 提供材料整理专用、bounded 的 agent tool/port：只接收当前课程 active 材料和已抽取
  目录/正文片段，不接受任意本地路径。
- 小娜按目录范围分批读取材料，生成一个或多个 `flashcard_deck` draft；长材料可续跑，
  中断后通过“进行中”恢复。
- 生成结果进入草稿箱，不直接进入学习页。

验收：

- 对已导入 PDF 能生成带目录节点和页码的知识核草稿；
- 没有可靠目录时先生成待确认目录，不绕过确认直接造知识核；
- 澄清问题通过现有 Study 小娜交互输入回答，不形成无入口的阻塞。

### S3H-3 审核、采用与地图发布

- 草稿审核面显示知识核标题、关键一句、目录位置和材料定位，不显示内部 ID。
- semantic review 通过后，用户点击采用才激活并物化。
- 激活/拒绝后刷新学习地图；若首个有效知识核出现而尚无 location，建立可恢复的初始位置。
- 旧 active 知识核更新采用 archive + 新 revision，不原地篡改已有证据。

验收：

- 未采用草稿不会出现在学习页；
- 采用后学习页立即显示第一个知识核；
- 拒绝不改变现有学习地图；
- 删除或替换知识核时按五页规格执行 stale 降级。

### S3H-4 计划与目录范围

- 小娜生成计划前读取已确认目录节点，并在 task 中保留真实 `outline_node_id`。
- 计划采用时物化行动项；未知节点显式报错并留在 draft。
- 计划页在目录节点下显示行动，不把行动变成第四级目录。
- 无 active plan 时明确区分“材料目录”和“待采用计划”，不能看起来像一个已运行的计划。

验收：

- active plan 至少物化一个行动项；
- 已绑定行动只出现在对应目录节点；
- 未绑定行动进入独立“待安排范围”，不伪装来源；
- 计划替换后旧计划归档，历史完成记录仍可追溯。

### S3H-5 当前行动与知识核联动

- 启动计划项时只在该 `outline_node_id` 范围内选择：
  1. 该行动已有 location：恢复精确知识核；
  2. 否则进入该范围第一个知识核；
  3. 该范围无知识核：留在计划页并提示先整理该节。
- location 持久化 `planItemId`；学习/练习切换保持它。
- 计划页读取 location，把对应行动标成“正在进行”，显示当前知识核标题和学习/练习模式。
- 用户完成或跳过当前行动后清除/推进行动关联，但不自动推断掌握度。

验收：

- 重启后计划页仍指向同一行动、同一知识核；
- 学习 ↔ 练习后计划页进度不丢；
- 前后知识核只能在行动目录范围内推进；
- 目录、知识核或行动失效时不跳到别的课程或无关范围。

### S3H-6 真实材料端到端验收

以产品方提供的《Python程序设计》PDF 为手工基线，同时使用小型固定 fixture 做自动化：

1. 导入材料并确认目录；
2. 请小娜整理一个目录范围的知识核；
3. 审核并采用知识核草稿；
4. 生成、审核并采用学习计划；
5. 从计划行动进入学习页；
6. 学习同一知识核后切到练习；
7. 返回计划页看到当前行动和知识核；
8. 重启应用并恢复同一现场。

自动化不得读取产品方本机绝对路径；测试使用仓库 fixture。最终 PDF 视觉与内容判断由产品方手测。

## 5. 代码范围

主要修改：

- `hermes_core/learning/learning_contract.py`
- `hermes_core/learning/flashcards.py`
- `hermes_core/learning/learning_map.py`
- `hermes_core/learning/learning_plans.py`
- `hermes_core/learning/planner_registry.py`
- `hermes_core/tools/learning_tools.py`
- `python/src/desk_server/routes/study_routes.py`
- `web/src/chat/study/study-api.ts`
- `web/src/study/repository.ts`
- `web/src/study/studyLocationSync.ts`
- `web/src/study/pages/PlanPage.tsx`
- `web/src/study/pages/LearnPage.tsx`
- 草稿审核与“进行中”相关组件

测试落点：

- `hermes_core/tests/`：合同、物化、地图、计划/location 一致性；
- `python/tests/`：HTTP/loopback、审核激活和 runtime import；
- `web/src/**/*.test.ts(x)`：草稿采用、范围选择、计划进度投影、恢复；
- `npm run build` 与 Python runtime import verification。

## 6. 完成定义

S3H 只有在以下条件同时满足时才能标记完成：

- 新导入的真实课程材料无需预置 fixture，也能通过小娜产出待审知识核；
- 用户采用后学习页出现真实、可定位的单个知识核；
- active plan 有可操作的行动项，计划页能显示当前行动和当前位置；
- 学习与练习保持同核，重启后恢复；
- 所有 AI 内容均经过 draft → review → user activate；
- 没有来源、没有可靠目录或关联失效时诚实停住，不用旧卡片/tag/别的题补空；
- core、Python 路由、Web 组件测试和 production build 通过。
