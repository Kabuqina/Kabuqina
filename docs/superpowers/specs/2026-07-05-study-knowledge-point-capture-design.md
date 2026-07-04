# STUDY 知识点单卡捕获设计（kq-kp chips → learning.db）

**日期：** 2026-07-05

**状态：** 设计稿，随 `student/study-module` 合并实施

**范围：** kq-kp 知识点 chips 的持久化改道：core `FlashcardService` 单卡捕获、
desk API、Tauri 代理、Web chips 重接线。不含 Gateway 暴露、不含 Learning
Index 投影变更（只埋活动钩子）。

**前置阅读：**
[immersive-learning-redesign.md](../../immersive-learning-redesign.md)（kq-kp
协议与 chips 的来源）、
[四层学习管线设计](2026-07-01-study-four-layer-learning-pipeline-design.md)
（artifact/审核/owner 契约）、其 M2 收口记录（FlashcardService 与迁移先例）。

## 1. 问题

immersive-learning M1（已在 main）让 assistant 的教学回复末尾携带 kq-kp
知识点块，前端渲染为 chips，点击加入复习队列。当前实现写
`flashcardStore`（localStorage `kabuqina.study.flashcards.v1`）。

四层管线 M2（`student/study-module` 分支，已收口）把闪卡实践迁到了
`learning.db`：卡片由 `flashcard_deck` artifact materialize 成
`learning_items`，复习是 `flashcard.review` 活动；旧 localStorage key 走一次
性幂等迁移（id `localStorage:kabuqina.study.flashcards.v1`），之后只读保留
一个发布周期。

合并后若不改道，chips 新增的卡写进已被迁移判定"处理完毕"的死存储，
永远进不了后端卡组。而后端目前**没有单卡入库路径**——只有整组草稿
（`learning_draft_create`）→ activate/reject，以及一次性迁移。

## 2. 语义定位：捕获是"用户显式保存"，不是"AI 批量生成"

这是本设计的核心判断，决定了审核路径：

- 卡片内容确实是 AI 生成的（name/gist 来自模型的 kq-kp 块），**但入库动作
  是用户在读过这张 chip（名称 + 要义悬浮提示）之后的显式点击**。这与
  legacy 迁移的判定同构——"里面的一切都是用户此前显式保存的，因此迁移
  一律导入为 active"（四层设计 §12）。
- 学习契约对 `flashcard_deck` 的语义审核要求本来就是"**批量时**语义"
  （§6 产物类型表）。单卡捕获是非批量情形，走确定性校验即可，合规。
- 迁移路由已开先例：受信路由可以 `OutputWriter.write_artifact` 后立即
  `FlashcardService.activate_deck`（study_routes.py 的
  `study_flashcards_migrate`）。捕获复用同一形态。

因此：**捕获走受信 UI/API 路径,写入即激活,不进草稿箱**。模型工具
不获得此能力——`learning` toolset 仍只能建整组草稿,不能自行激活自己
的内容（信任边界不变）。

## 3. Artifact 粒度：每次捕获一个单卡 artifact

考虑过的形态：

| 方案 | 问题 |
|------|------|
| 每空间一个滚动"知识点卡组"，点击追加 | OutputWriter 是 write-once + 状态转换，无 payload 追加语义；为此加 artifact 更新/重 materialize 是为 UI 便利打穿核心契约 |
| 无 artifact 的裸 `learning_items` | 破坏"卡片属于 artifact"的不变式；source_refs 挂在 artifact 上,裸 item 丢失来源审计 |
| **每次捕获 = 一个单卡 `flashcard_deck` artifact（采用）** | artifact 数量增多；用去重 + 上限缓解（见 §5） |

单卡 artifact 的好处正是四层设计最看重的两件事：

1. **来源自洽**（§5.1）：`source_refs` 内嵌 `origin=kq-kp`、会话 id、
   gist 摘录和 confidence——聊天 session 被清理后，卡片仍可审计"她当时
   为什么这么说"。
2. **零新增生命周期语义**：activate/reject/archive、materialize、复习
   调度全部复用 M2 现有代码路径。

## 4. Core：`FlashcardService.capture_card`

```python
def capture_card(
    self,
    *,
    front: str,
    back: str,
    hint: str = "",
    tags: Optional[List[str]] = None,
    source_refs: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
```

行为：

1. 清洗与校验（复用 `_clean_text`/`_clean_tags`；front/back 必填）。
2. **去重**：按 normalized front（strip + casefold）扫当前 owner/space 的
   `learning_items`（`item_type="flashcard"`）。命中则不写库，返回
   `{"duplicate": True, "item_id": <existing>}`——同一知识点在多条消息
   反复出现、反复点击是常态，幂等是第一需求。
3. **上限**：空间内卡片数 ≥ `FLASHCARD_SPACE_CAP`（500，对齐旧前端
   `FLASHCARD_MAX_CARDS`）时抛 `ValueError`（→ 400），不静默丢弃。
4. `OutputWriter.write_artifact(kind="flashcard_deck",
   title=front[:60], payload={"cards": [card]}, source_refs=...)`。
5. `self.activate_deck(artifact_id)` → materialize 单卡 item。
6. **记录捕获活动**：`record_activity(activity_type="flashcard.capture",
   artifact_id=..., item_id=..., detail={"origin": "kq-kp",
   "confidence": ...})`。这是给 M4 Learning Index 的钩子——被捕获的
   知识点是"学习者借助 agent 跳过了什么"的直接证据，weak_points 投影
   未来可消费（本设计不改投影）。
7. 返回 `{"duplicate": False, "artifact_id": ..., "item_id": ...,
   "front": ..., "dueAt": ...}`。

owner/space 一律来自注入的 `LearningExecutionContext`,schema 不出现
owner id（§8.3 不变式）。

## 5. Desk API 与 Tauri

```text
POST /api/desk/study/flashcards/capture
{
  "front": "贝叶斯定理",
  "back": "后验 = 先验 × 似然 / 证据",
  "hint": "",
  "tags": ["知识点"],
  "source": {
    "origin": "kq-kp",
    "session_id": "<current chat session>",
    "confidence": "confirmed"
  }
}
→ 200 {"duplicate": false, "artifact_id": "...", "item_id": "...", "dueAt": "..."}
→ 200 {"duplicate": true, "item_id": "..."}      # 幂等命中
→ 400 空间卡片达到上限 / front、back 缺失
```

- 路由复用迁移路由的 `_ensure_space`：无空间时自动建默认空间——chips
  在聊天页,不能要求用户先去 STUDY 面板建空间才能保存。
- `body.source` 由路由转换为 `source_refs`（受信层拼装,不信任前端传
  任意 refs 结构;只接受白名单字段 origin/session_id/confidence/gist）。
- 错误映射沿用 M2/M3：`ValueError→400`、`KeyError→404`、
  `ContractError→409`。
- Tauri：`cmd_study_flashcard_capture`,thin proxy,沿用现有 study.rs
  的路径校验模式。

## 6. Web 重接线

### 6.1 chips 的写路径

`KnowledgePointChips.tsx` 的 `addPoint`：

```text
旧：saveDeck(upsertCards(loadDeck(), [normalizeCard(input)]))
新：cmdStudyFlashcardCapture({ front, back, tags, source })
```

`knowledgePointToCardInput` 映射保持不变（front=name, back=gist,
tags=["知识点", source?]）,confidence 走 source 字段而非 tag。

### 6.2 "已在队列"状态

不能再同步读 localStorage 判断 added。新增轻量模块
`web/src/chat/study/captureIndex.ts`：

- 模块级缓存 `Set<normalizedFront>`,惰性初始化:首次有 chips 挂载时调
  一次 `cmdStudyFlashcards()` 填充;
- 订阅 M2 的 `study-learning-event` 与自身 capture 成功回执增量更新;
- 对 chips 暴露 `has(front)` / `subscribe()`。

代价是每个会话一次 flashcards 拉取,而不是每条消息一次。

### 6.3 失败态

- capture 请求失败：chip 短暂显示失败态,可重点。**不回落写
  localStorage**——四层设计 §14 的"数据库不可用时不丢失用户输入"由
  "消息还在,chip 可重点"满足,双写会重新制造分叉存储。
- backend 未就绪（hermes 未启动完/learning toolset 缺失）:chips 照常
  渲染但按钮禁用,tooltip 说明。

### 6.4 测试

沿用 `node:test` + transpileModule 栈：

- `captureIndex.test.mjs`：惰性初始化、事件刷新、增量更新;
- `knowledgePoints.test.mjs` 不变（解析与入库解耦,正是为此）;
- chatUx 断言从 `upsertCards(loadDeck(), [card])` 改为
  `cmdStudyFlashcardCapture`;
- core：`test_flashcards.py` 增 capture 用例——去重幂等、上限、活动
  写入、owner/space 越权。

## 7. 迁移期与顺序

1. 本设计随 `student/study-module` 合并实施（分支先合回 main,chips
   改道作为合并后的第一个补丁,或直接在合并分支上做）。
2. **开发期数据无搁浅**:合并前 chips 写入 legacy localStorage 的卡,
   与旧手动卡同在 `kabuqina.study.flashcards.v1` 里,会被 M2 的一次性
   迁移一并带进 learning.db。M1（immersive）尚未发布,不存在"迁移已
   跑完之后才产生 chip 卡"的真实用户。
3. 改道完成后,`flashcardStore.ts` 只剩迁移读取用途,随四层 §12 的
   周期在 M6 清理。

## 8. 明确不做

- 不给模型工具开单卡直写或自我激活（信任边界不变）。
- 不做捕获的语义审核（非批量,契约允许;用户点击即确认）。
- 不改 Learning Index 投影（只写 `flashcard.capture` 活动,消费留给 M4）。
- 不做 Gateway 捕获入口（core service 共享,将来 `/study` 命令可加）。
- 不做批量捕获（一条消息最多 5 个点,逐个点击可接受;真有需求再议）。
