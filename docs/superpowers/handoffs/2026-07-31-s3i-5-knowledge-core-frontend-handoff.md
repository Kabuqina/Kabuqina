# S3I-5 知识核编译器前端接入交接

> 日期：2026-07-31
> 后端状态：`S3I-1～S3I-4 IMPLEMENTED`
> 前端范围：`S3I-5`
> 注意：本轮没有修改 Web 的知识核编译 UI；S3I-6 端到端和真实 PDF 验收尚未完成。

## 1. 后端已经负责的事情

- 采用学习计划后，异步排入当前和下一个开放的 `learn` 节点，不等待模型。
- 完成或跳过计划项后，重新填充“当前 + 下一项”预取窗口。
- 替换计划时，只取消旧计划尚未开始的 `prefetch`；已开始的 run 仍可查询。
- 同一来源和策略的重复请求按编译键复用；已有 active core 时拒绝重复编译。
- 每窗最多 12 页、一次最多 48 页；没有真实 locator 时返回 `needs_source`。
- 编译模型无工具、无 Chat 历史、无 session 持久化。
- 结果只写 `flashcard_deck` draft，并自动发起 semantic review；绝不自动采用。
- run 会出现在 `/api/desk/activity` 的 Study 投影中，但不会成为 Tutor 活动或学习证据。

## 2. Tauri 命令

Web 请通过已有 `invoke` 边界调用，不直接访问 loopback HTTP。

| 命令 | invoke 参数 | 返回 |
|---|---|---|
| `cmd_study_knowledge_core_compilation_create` | `{ body: KnowledgeCoreCompilationRequest }` | `KnowledgeCoreCompilationRun` |
| `cmd_study_knowledge_core_compilation_list` | `{ spaceId, outlineNodeId?: string }` | `{ items, count }` |
| `cmd_study_knowledge_core_compilation_get` | `{ spaceId, runId }` | `KnowledgeCoreCompilationRun` |
| `cmd_study_knowledge_core_compilation_retry` | `{ spaceId, runId }` | 新的 `KnowledgeCoreCompilationRun` |
| `cmd_study_knowledge_core_compilation_cancel` | `{ spaceId, runId }` | 取消后的 run；终态调用保持原终态 |

建议在 `web/src/chat/study/study-api.ts` 增加：

```ts
export type KnowledgeCoreCompilationTrigger =
  | "plan_activated"
  | "start_learning"
  | "prefetch"
  | "retry";

export type KnowledgeCoreCompilationStatus =
  | "queued"
  | "reading"
  | "generating"
  | "validating"
  | "draft_ready"
  | "needs_source"
  | "failed"
  | "cancelled";

export type KnowledgeCoreCompilationRequest = {
  spaceId: string;
  outlineNodeId: string;
  planItemId?: string;
  trigger: KnowledgeCoreCompilationTrigger;
  expectedMapRevision: number;
  idempotencyKey: string;
  priority?: number;
};

export type KnowledgeCoreCompilationRun = {
  runId: string;
  spaceId: string;
  outlineNodeId: string;
  planItemId: string | null;
  trigger: KnowledgeCoreCompilationTrigger;
  status: KnowledgeCoreCompilationStatus;
  sourceFingerprint: string;
  policyVersion: string;
  draftArtifactId: string | null;
  reasonCode: string | null;
  sourceWindows: Array<{
    id: string;
    artifactId: string;
    sourceTitle: string;
    sourceRole: string;
    pageStart: number;
    pageEnd: number;
    locator: string;
    contentFingerprint: string;
  }>;
  createdAt: string;
  updatedAt: string;
};
```

`priority` 只接受 `-10..10`。普通点击学习建议传 `10`；后台预取由服务端负责，前端不要
一次创建整本书的 run。

## 3. HTTP 真值（排障用）

- `POST /api/desk/study/knowledge-core-compilations`
- `GET /api/desk/study/knowledge-core-compilations?space_id=...&outline_node_id=...`
- `GET /api/desk/study/knowledge-core-compilations/{run_id}?space_id=...`
- `POST /api/desk/study/knowledge-core-compilations/{run_id}/retry`
- `POST /api/desk/study/knowledge-core-compilations/{run_id}/cancel`

创建成功统一返回 `202`，包括立即落到 `needs_source` 或复用 `draft_ready` 的情况。
`active_core_exists`、`stale_learning_map`、plan item 不可用或节点不匹配返回 `409`。

计划采用的现有命令 `cmd_study_artifact_activate` 在采用 `learning_plan` 时额外返回：

```ts
{
  compilationRuns: Array<{
    runId: string;
    outlineNodeId: string;
    status: KnowledgeCoreCompilationStatus;
  }>;
  compilationEnqueueFailed?: true;
}
```

计划采用本身已经成功时，即使后台排队部分失败，也不会回滚计划采用；前端可据
`compilationEnqueueFailed` 刷新节点 run 状态。

## 4. 计划页“学习”五态

按当前 `learning_map`、该节点 draft 和最新 run 决策，优先级如下：

1. **已有 active knowledge core**：直接使用现有 location/learn 导航，不创建 run。
2. **已有可审核 draft**：打开该 `draftArtifactId` 的审核；审核通过仍需用户调用现有
   `cmd_study_artifact_activate`。
3. **最新 run 为 queued/reading/generating/validating**：按钮显示“正在整理”，原地轮询，
   不打开小娜。
4. **最新 run 为 needs_source/failed**：显示结构化失败态，提供“重试 / 查看知识源 /
   问小娜”三个入口；小娜只作异常兜底。
5. **没有 active core、draft 或 run**：创建 `trigger: "start_learning"` 的 run。成功后进入
   第 2 或第 3 态，而不是打开 Chat。

`draft_ready` 不等于已采用；`cancelled` 也不应显示为成功。列表可能保留历史 run，节点状态
应优先使用 `updatedAt` 最新的一条，并在地图已有 active core 时始终以地图为准。

建议轮询进行中 run；离开页面可停止轮询，后台仍继续。返回 Activity 或再次进入计划页时，
用 list/get 恢复，不在 `localStorage` 复制 run 真值。

## 5. reasonCode 与动作

| reasonCode | 前端主文案/动作 |
|---|---|
| `outline_locator_missing` | 目录缺少可靠页码；主按钮“查看知识源” |
| `primary_material_unavailable` | 主知识源不可用；主按钮“查看知识源” |
| `source_range_empty` / `source_text_unavailable` | 当前范围无法读取；允许重试并查看来源 |
| `model_unavailable` | 模型或密钥不可用；允许重试，必要时进入设置 |
| `process_restarted` | 应用重启中断；显示可重试 |
| `compilation_failed` | 通用失败；允许重试和问小娜 |

不要向用户展示内部异常文本，也不要根据 title 猜来源或知识核。

## 6. Activity 接入

`GET /api/desk/activity` 已增加：

```ts
{
  domain: "study";
  kind: "knowledge_core_compilation";
  status: "waiting" | "running" | "failed" | "completed";
  sourceStatus: KnowledgeCoreCompilationStatus;
  compilationRunId: string;
  outlineNodeId: string;
  planItemId: string | null;
  draftArtifactId: string | null;
  reasonCode: string | null;
  canResume: false;
  canRetry: boolean;
  returnTarget: string;
}
```

`needs_source` 投影为 `waiting + canRetry`，`failed` 投影为 `failed + canRetry`，
`draft_ready/cancelled` 投影为 `completed`。S3I-5 应把 `cancelled` 文案显示为“已取消”，
不要仅凭公共 `completed` 显示“整理完成”。

## 7. 建议修改与验收

前端修改范围：

- `web/src/chat/study/study-api.ts`：类型和五个 invoke 包装；
- `web/src/study/repository.ts`：节点 run 查询、创建、轮询、重试；
- `web/src/study/pages/PlanPage.tsx`：五态入口；
- `web/src/study/DraftInboxButton.tsx`：定位该节点 draft 和采用后刷新地图；
- `web/src/study/desk/StudyMaterialReader.tsx`：用 card `source_refs` 精确打开页码；
- `web/src/shell/ActivityPanel.tsx`：编译 Activity 文案和返回。

最低前端测试：

- 计划采用后显示当前 + 下一节点状态，不打开小娜；
- 重复点击不重复创建；
- `draft_ready` 打开审核，不直接进入 Learn；
- 采用 draft 后刷新 map 并进入第一个真实 `knowledgeCoreId`；
- `needs_source/failed` 三个边界入口正确；
- Activity 从运行中返回对应计划节点；
- cancelled 不显示为成功；
- 计划页不展开第四级知识核。
