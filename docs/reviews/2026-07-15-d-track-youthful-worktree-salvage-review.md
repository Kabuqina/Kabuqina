# D 轨旧 worktree 未提交改动移植评估

> 日期：2026-07-15
> 来源 worktree：`D:\project\Kabuqina\.claude\worktrees\youthful-burnell-ca6cae`
> 来源分支：`claude/youthful-burnell-ca6cae`
> 来源 HEAD：`d91b55e5 feat(study): align learning runtime conduct`
> 目的：供 D 轨负责人判断哪些未提交改动应按当前 `main` 重新实现；本文件不建议直接合并旧 worktree。

## 1. 结论

这个 worktree 是 2026-07-05 留下的旧基线未完成修复，不是可直接继续推进 D4 的工作分支。

- 来源 HEAD 已被 `main` 包含，没有分支独有提交。
- 来源分支相对当前 `main` 落后 116 个提交。
- worktree 有 8 个未暂存修改，约 `+80/-11`；没有 staged 或 untracked 文件。
- 8 个文件集中在 2026-07-05 20:19–20:21 被修改，未形成 commit。
- 其中一部分仍修复当前 `main` 的真实恢复性缺口，值得移植。
- 另一部分引用了 D3 后已删除的旧组件，或没有覆盖当前调用点，不能原样合并。

建议：在基于最新 `main` 的 D 轨 clean worktree 中重新实现有效部分并补齐当前调用点；通过回归后再删除来源 worktree 和分支。

## 2. 未提交文件

| 文件 | 原改动意图 | 当前判断 |
|---|---|---|
| `web/src/chat/study/captureIndex.ts` | 学习存储读取失败后退避重试，并暴露 `forceRefresh()` | **建议移植** |
| `web/src/chat/study/captureIndex.test.mjs` | 覆盖退避窗口和强制恢复 | **建议移植并按当前实现复核** |
| `web/src/chat/study/KnowledgePointChips.tsx` | 存储不可用时允许用户点击重试 | **建议移植** |
| `web/src/locales/strings.ts` | 中英文不可用提示增加“点击重试” | **建议随交互移植**；注意与 A-R3 的共享文件冲突 |
| `web/src/chat/hooks/useSendMessage.ts` | 将学习事件常量改从 `captureIndex` 导入 | **可选整理，不能单独照搬** |
| `web/src/chat/study/flashcardLearningStore.ts` | 删除重复的学习事件常量 | **可选整理，须先更新全部当前调用点** |
| `web/src/chat/study/FlashcardPanel.tsx` | 将学习事件常量改从 `captureIndex` 导入 | **过期，不移植**；该文件已不在当前 `main` |
| `web/src/chat/study/QuizPanel.tsx` | 将学习事件常量改从 `captureIndex` 导入 | **过期，不移植**；该文件已不在当前 `main` |

## 3. 值得移植的行为修复

### 3.1 当前缺口

当前 `main` 的 `captureIndex.initialize()` 在第一次 fetch 失败后将状态设为 `unavailable`。后续再次调用 `initialize()` 会立即返回，不再尝试访问学习存储。

这意味着桌面服务启动较慢、短暂网络/IPC 错误或学习空间尚未就绪时，知识点捕获入口可能在整个页面会话中永久不可用。除非其他代码恰好派发 `study-learning-event`，用户没有明确恢复入口。

### 3.2 旧 worktree 的方案

旧改动实现了：

1. 默认 15 秒重试退避，避免每次组件挂载都请求后端。
2. 退避期结束后，普通 `initialize()` 可以重新 fetch。
3. 对外暴露 `forceRefresh()`，允许用户主动绕过退避。
4. `KnowledgePointChips` 在 `unavailable` 时不再永久禁用；点击会触发 `forceRefresh()`。
5. 中英文 tooltip 明确提示“点击重试”。
6. 测试覆盖：
   - 退避窗口内 `initialize()` 不重复请求；`forceRefresh()` 可立即恢复。
   - 退避结束后 `initialize()` 会重新请求并恢复 `ready`。

### 3.3 移植时必须重新确认

- `forceRefresh()` 是否应复用已有 pending promise，避免用户连续点击产生并发 refresh。
- 状态从 `unavailable` 进入 `loading` 时，按钮的 disabled、tooltip 和可访问性文案是否一致。
- 重试成功后是否会通知所有订阅者，并正确更新“已加入复习”状态。
- `retryBackoffMs: 0` 的测试是否依赖毫秒边界；必要时使用可注入 clock，避免偶发测试。
- D4 若正在调整统一草稿箱或学习 repository，不要在 UI 层复制第二套重试状态机；恢复逻辑仍应集中在 capture index/repository 边界。

## 4. 事件常量去重不能原样合并

旧 worktree 试图把 `STUDY_LEARNING_EVENT` 从 `flashcardLearningStore.ts` 迁到 `captureIndex.ts`。方向可以接受，但旧 patch 已与当前树形结构脱节：

- `FlashcardPanel.tsx` 与 `QuizPanel.tsx` 已被后续 D3 删除/迁移。
- 当前 `main` 中 `useSendMessage.ts` 仍从 `flashcardLearningStore.ts` 导入该常量。
- 当前 `main` 中 `StudySection.tsx` 也仍从 `flashcardLearningStore.ts` 导入该常量，而旧 patch 没有修改它。
- `captureIndex.ts` 与 `flashcardLearningStore.ts` 目前各定义一次相同字符串。运行时事件仍能匹配，但存在双重定义的维护风险。

如果 D 轨决定顺手去重，应在最新 `main` 上搜索全部 `STUDY_LEARNING_EVENT` 引用，统一更新当前仍存在的调用点，并确保定义只保留一处。建议把该整理与恢复性修复分成可独立 Review 的 commit 或至少独立 diff 区块。

## 5. 推荐执行方式

1. 不要在旧 `youthful-burnell-ca6cae` worktree 上继续 D4。
2. 不要直接提交这 8 个旧文件，也不要对旧分支做整分支 merge。
3. 从包含 D3/D3 Review 修复的最新 clean `main` 创建或使用 D 轨 worktree。
4. 先移植 `captureIndex.ts`、`captureIndex.test.mjs`、`KnowledgePointChips.tsx` 的恢复行为。
5. 根据最终交互更新 `strings.ts`；A-R3 完成前不要把该共享文件合入 `main`。
6. 若要去重事件常量，按当前树重新搜索和修改，不移植已删除组件的旧 diff。
7. 跑完针对性测试与 Web build 后，再判断是否合并。
8. 新实现合入并确认旧 patch 无剩余价值后，删除来源 worktree 和 `claude/youthful-burnell-ca6cae` 本地分支。

## 6. 最低验证门槛

至少应验证：

- `captureIndex` 现有测试全部通过。
- 新增的退避重试和强制重试测试稳定通过。
- 第一次 fetch 失败后，退避期内不会重复请求。
- 退避期结束或用户主动点击后可以恢复。
- 连续点击不会产生不可控的并发请求。
- 已捕获知识点仍不会重复创建卡片。
- 中英文提示和按钮可访问性状态一致。
- `rg "STUDY_LEARNING_EVENT" web/src` 只有预期的一处定义，所有 import 均指向该定义；如果本次不做去重，则明确记录为独立 cleanup，而不是留下半迁移状态。
- `npm run build` 通过。

## 7. 合并判断

可合并的不是旧 worktree 本身，而是基于最新 `main` 重做并验证后的恢复性修复。

建议 D 轨负责人回复以下三项：

1. 是否确认当前 D4 设计仍需要 `captureIndex` 这一层缓存/索引。
2. 是否在本次一并完成事件常量去重，还是登记为后续 cleanup。
3. 新实现的 commit、测试结果，以及旧 worktree 是否可以删除。

## 8. D 轨处置结果（2026-07-15）

1. **保留 `captureIndex` 边界。** 当前聊天消息中的 `KnowledgePointChips`
   仍依赖它维护已捕获知识点集合，并且 Study repository 不覆盖这一条聊天内
   去重/恢复路径。恢复状态机继续集中在 index，而不是复制到组件。
2. **本次一并完成事件常量去重。** 唯一定义迁到无副作用的
   `web/src/study/learningEvent.ts`；聊天发送、课程 seed、Study 壳及各学习页面
   均从该模块导入。产品源文件不再直接散写 `study-learning-event` 字符串。
3. **已基于当前树重做并验证恢复修复。** 具体行为包括 15 秒失败退避、可注入
   clock、退避后自动恢复、用户强制恢复、所有入口复用同一个 pending promise，
   以及重连期间 disabled/tooltip/`aria-busy` 一致状态。验证结果：
   `test:capture-index`、`test:chat-ux`、13 files / 62 tests 的组件测试、全量
   ESLint 和生产 build 均通过。

提交使用基于 HEAD 的独立 Git index，只纳入 D 轨文件及 `strings.ts` 的 D 轨
本地化 hunk；A-R3 已 staged 的共享文件改动继续保留在真实 index，不混入本
提交。旧 worktree 的 8 个未提交 patch 已无剩余独有实现价值，本次 D 轨独立
提交落地后即可删除该 worktree 与本地分支。
