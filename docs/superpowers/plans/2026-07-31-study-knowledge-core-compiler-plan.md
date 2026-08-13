# Study 知识核编译器实施计划

> 日期：2026-07-31
> 状态：`S3I-1～S3I-4 BACKEND IMPLEMENTED · S3I-5 FRONTEND HANDOFF · S3I-6 NOT STARTED`
> 里程碑：S3I
> 依赖：Study 五页行为规格、S3H 学习生产链、受限材料阅读器、知识核草稿与学习地图合同
> 覆盖：本计划取代 S3H 中“用户必须请小娜整理知识核”作为默认入口的设计；小娜保留为异常处理和主动重整入口。

> 2026-07-31 实施记录：本轮完成 S3I-1～S3I-4 的 core、Desktop Python、
> Tauri bridge 与 Activity 后端合同；没有修改 S3I-5 Web UI。前端接入说明见
> `docs/superpowers/handoffs/2026-07-31-s3i-5-knowledge-core-frontend-handoff.md`。
> S3I-6 的生产 build 与真实 PDF 手工验收仍是后续工作，因此本文的整体“完成定义”
> 尚未达成。

## 0. 决策

知识核是 Study 正常运行所需的编译产物，不是用户必须通过 Chat 请求的小娜作品。

默认生产链调整为：

```text
知识源导入并形成可靠目录
  → 用户采用学习计划
  → 系统为当前行动和下一个行动渐进编译知识核草稿
  → 合同校验与语义审核
  → 用户查看并采用
  → active 知识核进入学习地图
  → 学习与练习共用同一个 knowledgeCoreId
```

“问小娜”不再是启动学习的必经步骤，只在以下情况出现：

- 用户主动要求换一种拆分方式；
- 材料结构不足，需要协助编目；
- 来源冲突、文本质量差或编译失败，需要解释和处理；
- 用户希望基于自己的目标补充或删减候选知识核。

## 1. 当前缺口

现有实现已经具备：

- active `resource_pack` 及可靠材料目录；
- 按 artifact 和页码窗口读取材料的可信 reader；
- 带 `knowledge_core_id / outline_node_id / order / source_refs` 的
  `flashcard_deck` 草稿合同；
- semantic review、用户采用和 active 学习地图；
- 计划行动到目录节点的绑定；
- 学习与练习共享知识核位置。

缺少的是中间的自动生产者：

```text
outline node + source windows
  → bounded semantic extraction
  → reviewable knowledge-core draft
```

目前计划页只能发现“该节点没有 active 知识核”，然后打开小娜。这是诚实的兜底，但不是
完整产品链。

## 2. 产品边界

### 2.1 不变规则

1. 目录最多三级；知识核不作为第四级目录展示。
2. 一个目录节点可以包含多个有序知识核。
3. 学习页和练习页一次只呈现一个知识核，并共享同一游标。
4. 模型生成内容必须经过 `draft → review → user activate`，编译器不得自动激活。
5. 每个知识核必须绑定真实 `outline_node_id` 和可定位 `source_refs`。
6. 无可靠目录、无可读正文或无法定位来源时必须停住，不能用目录标题冒充知识核。
7. 打开材料、生成草稿和移动游标都不代表“掌握”或“完成”。
8. 编译器不是 Chat 会话，不向用户提出悬空问题；无法继续时返回结构化原因。

### 2.2 首版范围

首版编译：

- 只处理已采用计划中的 `learn` 行动；
- 先准备当前行动节点，再预取下一个 `learn` 行动节点；
- 每个目录节点生成一份知识核 deck 草稿；
- 默认从主知识源读取，只有已有 active 材料对齐关系时才读取辅助资料；
- 不一次性编译整本书；
- 不自动生成练习题。练习题继续使用 S3E 的材料原题优先、改编/生成题进入草稿的合同。

以下作为后续能力，不阻塞首版：

- 阅读器选中文字“加入学习”；
- 将高亮、笔记或书签转为知识核；
- 用户逐张删除、合并或重排草稿中的知识核；
- 整本书离线批量编译。

## 3. 领域模型

### 3.1 编译请求

```ts
type KnowledgeCoreCompilationRequest = {
  spaceId: string;
  outlineNodeId: string;
  planItemId?: string;
  trigger: "plan_activated" | "start_learning" | "prefetch" | "retry";
  expectedMapRevision: number;
  idempotencyKey: string;
};
```

请求不接受本地路径、自由 Prompt 或任意 material id。服务端根据当前课程真值解析：

- active plan 和 plan item；
- 已确认 outline node；
- active 主知识源；
- active material alignment；
- source artifact version/revision。

### 3.2 编译运行

新增独立的持久化运行对象，不复用 `tutor_activity_runs`。Tutor runtime 当前只允许
`tutor | review | practice`，知识核编译不是学习活动或练习证据。

```ts
type KnowledgeCoreCompilationRun = {
  runId: string;
  spaceId: string;
  outlineNodeId: string;
  planItemId?: string;
  trigger: string;
  status:
    | "queued"
    | "reading"
    | "generating"
    | "validating"
    | "draft_ready"
    | "needs_source"
    | "failed"
    | "cancelled";
  sourceFingerprint: string;
  policyVersion: string;
  draftArtifactId?: string;
  reasonCode?: string;
  createdAt: string;
  updatedAt: string;
};
```

状态转换：

```text
queued → reading → generating → validating → draft_ready
             └──────────────→ needs_source
             └──────────────→ failed
queued/running ─────────────→ cancelled
failed/needs_source ─retry─→ 新 run
```

`draft_ready` 只表示草稿已写入，不表示知识核已经采用。待采用状态由 artifact lifecycle
继续负责。

### 3.3 幂等与版本

编译键至少包含：

```text
space_id
+ outline_node_id
+ 主知识源 artifact_id/version
+ 已采用材料对齐 revision
+ compiler_policy_version
```

规则：

- 同一编译键最多一个非终态 run；
- 同一编译键已有可用 draft 时直接返回该 draft；
- 同一来源版本下已有 active 知识核时不自动重复编译；
- 来源或编译策略变化时建立新 revision，不原地覆盖 active 知识核；
- 稳定知识核 ID 根据课程、目录节点、来源定位指纹和概念指纹生成；
- 重编译时优先匹配来源定位和概念指纹，标题润色不能单独导致 ID 漂移。

## 4. 编译流水线

### 4.1 Scope resolver：确定目录范围

输入真实 `outline_node_id`，解析：

- 节点自身 locator；
- 第一个后代到下一个同级节点前的材料范围；
- 主材料 artifact/version；
- 可用的辅助材料对齐范围。

如果节点没有可靠 locator：

- 不按标题全文搜索后直接认定；
- 返回 `needs_source: outline_locator_missing`；
- 计划页提示先确认目录或从阅读器指定范围；
- 小娜入口可以帮助二次编目，但不能绕过确认。

### 4.2 Window planner：规划受限阅读窗口

- 单次 reader 继续保持最多 12 页；
- 首版单节点最多读取 48 页；
- 超过上限时按目录后代或段落边界分窗；
- 每个窗口保存 material、页码/章节 locator 和内容指纹；
- 不把尚未读取的范围声明为已覆盖；
- 多材料时先读主材料，只读取已有显式 alignment 的辅助窗口。

窗口规划是确定性的，不调用模型。

### 4.3 Semantic compiler：受限语义编译

后台编译器使用独立的受限模型运行，不创建普通 Chat 会话，也不继承任意对话历史。

允许输入：

- 当前课程的固定目标、偏好和时间约束；
- 当前真实目录节点及父路径；
- bounded source windows；
- 当前节点已有 active/draft 知识核摘要，用于去重；
- 严格 JSON 输出 schema。

禁止：

- web、terminal、任意文件工具；
- 读取其他课程；
- 修改目录、计划或 active artifact；
- 向用户发起澄清交互；
- 生成没有 source locator 的知识核；
- 将目录标题直接复制为知识核而没有可验证的核心问题。

每个候选知识核至少输出：

```ts
type KnowledgeCoreCandidate = {
  title: string;              // front：眼前要弄懂的一件事
  keyStatement: string;       // back：自足的关键一句
  sourceWindowIds: string[];
  sourceExcerptFingerprints: string[];
  conceptKey: string;
  order: number;
};
```

宿主代码根据可信窗口补齐 artifact、locator、`outline_node_id` 和稳定
`knowledge_core_id`。模型不能自行指定本地路径或伪造 material id。

### 4.4 Validator 与 draft writer

生成结果依次经过：

1. JSON schema 校验；
2. 空标题、重复概念和顺序校验；
3. source window 引用存在性校验；
4. 来源摘录指纹回查；
5. 与当前 active/draft 知识核去重；
6. 转换为现有 `flashcard_deck` 合同；
7. `OutputWriter` 写入 draft；
8. 触发现有 semantic review。

任何校验失败都不能留下半份 active 数据。可修复的格式错误允许一次受限修复；仍失败则
运行进入 `failed`。

## 5. 触发与渐进策略

### 5.1 计划采用后

采用 active plan 后：

1. 找到第一个未完成的 `learn` 行动；
2. 如果节点没有 active core、可用 draft 或非终态 run，enqueue 高优先级编译；
3. 同时为下一个 `learn` 行动 enqueue 低优先级预取；
4. `practice/review` 行动不触发知识核编译。

计划采用成功不等待模型完成，避免阻塞 UI。

### 5.2 点击“学习”（2026-08-03 收口）

计划页只负责选择目录范围并进入学习页，不读取或展示知识核编译状态。按钮按以下顺序决策：

1. 保存所选计划项和内部目录范围，立即进入学习页；
2. 学习页发现已有 active core 时直接呈现；
3. 没有 active core、draft 或非终态 run 时，由学习页自动创建高优先级编译；
4. 编译进行中、待采用和失败恢复都留在学习页呈现；
5. 后台调用 LLM 是产品能力，不要求先打开聊天，小娜聊天仅保留为用户主动求助入口。

不再以打开小娜和预填 Prompt 作为默认分支。

### 5.3 推进与预取

- 用户采用当前节点知识核后，学习入口立即可用；
- 用户进入当前节点第一个知识核时，检查下一个计划节点是否需要预取；
- 预取只生成 draft，不自动弹窗打断当前学习；
- plan 归档或替换后，取消尚未开始且已失去范围的预取 run；
- 已生成的 draft 保留可追溯关系，但不自动挂到新计划。

## 6. 用户界面

### 6.1 计划页（2026-08-03 收口）

计划页就是学习目录：行动长在对应目录下，主按钮只表达“开始学习 / 继续学习”。点击后进入
学习页。计划页不展开知识核列表、不增加第四级树，也不显示“关联目录”、编译、待采用、
失败或重试等实现状态；目录关联仅作为后台限定材料范围的数据完整性字段。

### 6.2 草稿审核

按目录节点展示一批候选知识核：

- 知识核标题；
- 关键一句；
- 目录位置；
- 知识源名称和页码/章节；
- “在阅读器中查看来源”；
- semantic review 状态；
- 明确的“采用知识核”。

首版沿用整份 deck 采用。逐条删改与排序列入后续，不在首版临时做一套不完整编辑器。

### 6.3 进行中

`ActivityProjectionService` 增加 knowledge-core compilation 投影：

- queued / reading / generating / validating → `running`；
- needs_source → `waiting`；
- failed → `failed`；
- draft_ready / cancelled → `completed`。

返回目标是对应课程的计划页，并携带 `outlineNodeId`。编译运行不是学习证据，不进入评估页
活动证据。

## 7. 后端与前端接口

建议新增：

```text
POST /api/desk/study/knowledge-core-compilations
GET  /api/desk/study/knowledge-core-compilations?space_id=&outline_node_id=
GET  /api/desk/study/knowledge-core-compilations/{run_id}?space_id=
POST /api/desk/study/knowledge-core-compilations/{run_id}/retry
POST /api/desk/study/knowledge-core-compilations/{run_id}/cancel
```

创建接口返回 `202` 和 run 投影；重复 idempotency key 返回同一 run。Web 轮询应使用退避，
页面卸载只停止轮询，不取消后台任务。

计划采用接口不直接运行模型，只提交 enqueue 意图。若 enqueue 失败，计划仍然采用成功，
并在计划页显示可重试状态。

## 8. 代码分层

### Agent core：`hermes_core/`

新增或修改：

- `learning/knowledge_core_compiler.py`
  - 请求合同、scope/window planner、候选校验、稳定 ID、draft writer；
- `learning/knowledge_core_compilation_store.py`
  - run 状态、幂等、恢复、取消；
- `learning/learning_plans.py`
  - plan activation 后产生编译意图；
- `learning/learning_contract.py`
  - 必要的 compiler provenance 字段校验；
- `learning/learning_map.py`
  - 不改变 active-only 地图原则；
- `tests/learning/`
  - 流水线、幂等、失败和版本测试。

编译语义属于 agent core，不放 overlay。

### Desktop Python：`python/src/`

新增或修改：

- `desk_server/knowledge_core_compile_runner.py`
  - 后台队列、受限模型调用、启动恢复和并发上限；
- `desk_server/routes/study_routes.py`
  - run 创建/查询/重试/取消；
- `activity_projection.py`
  - 编译运行只读投影；
- `desktop_entrypoint.py`
  - runner 生命周期；
- `capability_registry.py`
  - 声明非对话式编译能力，但不暴露任意路径；
- `tests/`
  - HTTP、进程恢复、Activity 和 runtime import。

材料路径解析和临时读取权限继续留在 Desktop Python，不下沉到 core。

### Web：`web/src/`

新增或修改：

- `chat/study/study-api.ts`
  - compilation API 类型；
- `study/repository.ts`
  - run 读写与轮询；
- `study/pages/PlanPage.tsx`
  - 五态学习入口；
- `study/DraftInboxButton.tsx`
  - 节点范围审核与来源跳转；
- `study/desk/StudyMaterialReader.tsx`
  - 从草稿定位来源；
- `shell/ActivityPanel.tsx`
  - 编译运行状态和返回；
- 对应组件测试。

现有 `studyNanaRequest` 只保留为失败/主动重整兜底，不再承担正常启动学习。

## 9. 实施切片

### S3I-1：运行合同与持久化

- 定义 request/run/status/reason code；
- 增加独立 run store 和幂等键；
- 支持崩溃恢复：启动时将遗留 running 标记为可重试失败，或安全重新入队；
- Activity 只读投影接入。

验收：

- 重复请求不产生重复 run；
- 重启不留下永久“正在整理”；
- run 不写学习证据。

### S3I-2：确定性范围与窗口规划

- 按真实 outline locator 解析范围；
- bounded reader 分窗；
- 多材料只读取 active alignment；
- 生成可验证的 source window manifest。

验收：

- 不读取任意路径；
- 不跨课程；
- 无 locator 时返回 `needs_source`；
- 12 页单窗和 48 页首轮上限被测试锁定。

### S3I-3：受限语义编译与草稿

- 接入结构化模型输出；
- 候选校验、去重和稳定 ID；
- 写入 card 级来源完整的 `flashcard_deck` draft；
- 自动发起 semantic review，不自动 activate。

验收：

- 不创建 Chat session；
- 无来源候选不能写入；
- active map 在用户采用前不变化；
- 同输入重试不产生重复知识核。

### S3I-4：自动触发与渐进预取

- plan activation enqueue 当前 + 下一个 learn node；
- 点击学习按五态决策；
- 节点推进时补充预取；
- plan 替换取消失效预取。

验收：

- 正常路径不打开小娜；
- 计划采用不等待模型；
- 不编译整本书；
- active core 存在时不重复运行。

### S3I-5：审核、计划页与进行中 UI

- 计划页显示编译、待采用和失败状态；
- 草稿审核可以回到精确来源；
- Activity 展示后台运行；
- 失败时提供重试、知识源和问小娜三个有边界的入口。

验收：

- 用户可以从计划目录完成“整理 → 查看 → 采用 → 学习”；
- 计划页仍不展开第四级知识核；
- draft 采用后学习页出现第一个真实知识核。

### S3I-6：端到端与真实材料验收

自动化 fixture：

1. 导入带可靠目录的测试 PDF；
2. 采用含两个 learn 节点的计划；
3. 当前节点与下一节点产生两个编译 run；
4. 当前节点生成 draft，地图仍为空；
5. 用户采用 draft；
6. 点击学习进入该节点第一个知识核；
7. 切到练习仍保持同核；
8. 重启后恢复同一位置。

产品方使用《Python程序设计》PDF 手工验证：

- 节点拆分粒度是否像“一个需要弄懂的问题”；
- 标题与关键一句是否忠于教材；
- 来源页码能否准确打开；
- 当前 + 下一个节点的等待时间是否可接受；
- 失败时是否能理解下一步。

## 10. 测试矩阵

必须覆盖：

- 可靠目录 / 弱目录 / 无目录；
- 单材料 / 已对齐多材料 / 未对齐材料；
- 节点少于 12 页 / 跨窗 / 超过 48 页；
- active core 已存在 / draft 已存在 / run 正在进行；
- 重复点击 / 重启 / 网络失败 / API key 缺失；
- 模型返回非法 JSON、重复概念、未知 window id、空来源；
- 来源版本变化、计划替换、目录节点失效；
- draft review 失败、拒绝、采用；
- Learn ↔ Practice 同核和 location 恢复。

验证命令至少包括：

```powershell
python -m pytest hermes_core/tests/learning -q
cd python; python -m unittest discover -s tests -p "test_*.py" -v; cd ..
cd web; npm run test:components; npm run build; cd ..
python python/tools/verify_runtime_imports.py
```

## 11. 完成定义

同时满足以下条件才算知识核编译器完成：

- 用户采用计划后，无需发起 Chat，小娜也不会自动打开；
- 系统只渐进准备当前和下一个学习节点；
- 每个候选知识核都能回到真实知识源位置；
- 编译结果只进入 draft，用户采用前不进入学习地图；
- 采用后计划页的“学习”直接进入具体知识核；
- 学习与练习保持同一 `knowledgeCoreId`；
- 编译运行可查询、可恢复、可重试，并出现在“进行中”；
- 无目录、无来源和模型失败时诚实停住；
- 自动化测试、production build 和真实 PDF 手工验收通过。
