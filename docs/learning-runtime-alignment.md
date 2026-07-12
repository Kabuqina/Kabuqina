# 学习 Agent 的运行时对齐：Harness 与 Graph 层评审

> Status: **评审结论 + 排期分配**（2026-07-12 G2 开门后补充 contracts-only 审查）
> Last updated: 2026-07-12
> 前置阅读：[immersive-learning-redesign.md](immersive-learning-redesign.md)（原则与 M1 行为层）、
> [四层学习管线设计](superpowers/specs/2026-07-01-study-four-layer-learning-pipeline-design.md)（数据层）
>
> **命名注意：** 本文的图层改造点编号使用 **LG1-LG6**（Learning-Graph）,
> 刻意避开重构轨道的 G0/G1/G2 **门**（gate）编号,二者无关。

## 0. 总判断

现有 harness 为「减少人类回合」优化：工具循环、tool-use enforcement、
budget、轨迹压缩,全部围绕"不停手直到产出"设计。学习 agent 的成功指标
相反——**学习者的回合才是产品**。M1 之后,教学节奏只活在
`LEARNING_CONDUCT_GUIDANCE` 的提示词里,是"软"约束;本文列出把它逐步
"硬化"进运行时的改造点,并分配到现有两条轨道（STUDY 里程碑轨、
phase 3.5 重平台轨）上。

分配的三条纪律：

1. **不给即将被 3.5 重平台的旧 agent loop 加新机制**——凡属循环语义的
   改造（停机条件、interrupt、checkpoint）一律作为 graph_engine 的
   contracts 需求,在 3.5 上实现,不在 run_agent 旧 loop 上做一次性投资。
2. **不让任何一项阻塞 STUDY 里程碑**——能搭现有里程碑顺风车的搭车,
   不能的独立成小补丁。
3. **soak 期间不碰引擎**（2026-07-05 新增,见 §3 状态）——Task 11
   Step 4 的 14 天 soak 已重启,graph_engine 及其 contracts 在 soak
   结束前冻结,3.5 桶的全部事项顺延至 v0.3.0 之后。

## 1. Harness 层改造点

### H1 · kq-kp 在 Gateway 侧裸奔（bug 级）

`LEARNING_CONDUCT_GUIDANCE` 注入在 `run_agent._build_system_prompt`,
web child 与 gateway child 共用;但剥离 kq-kp 块的代码只在 web 前端
（`knowledgePoints.ts`）。微信/飞书等 gateway 用户会看到消息尾部的原始
JSON 围栏块。

**短期修法（立即）：** 按 surface 门控——kq-kp 小节从常量中拆出,仅
desktop（web child）注入;或在 core 传输边界统一剥离。此修法只动
prompt 拼装层,不触及引擎,soak 期间安全。
**长期修法：** 见 LG3（廉价后置节点抽取,主消息天然干净）。

### H2 · "交还回合"应成为停机条件,不是提示词愿望

现在 loop 的终止 = 模型自认为答完。教学模式需要 tool-use enforcement
的镜像:讲解型回合"说完一个概念、以检查问题收尾"即为合法终点（软性
token 上限 + 问句收尾判定）。提示词随上下文变长会漂移,停机条件不会。

**归属：** 循环语义 → 3.5 轨,作为图的边而非旧 loop 补丁（见 LG2）。

### H3 · 学习状态需要每回合的注入管道

系统提示一次构建、全会话缓存（prefix cache 正确取舍）,但"因材施教"
需要新鲜数据。现成的口子是 `ephemeral_system_prompt`（每次 API 调用
注入、不进缓存）。M4 的 Learning Index 投影（到期卡、薄弱点、当前计划
项）应接进这个 ephemeral 槽：conduct 契约进缓存层（稳定）,学习状态进
ephemeral 层（每回合新鲜）。

**归属：** STUDY 轨,M4 落地投影后,同里程碑内接线。

### H4 · 轨迹压缩的价值函数要反转

`trajectory_compressor` 为工具型工作调优（保工具结果、丢闲聊）。对导师
而言,**学习者说错的那句话是全对话最值钱的 token**——那是误解模型的
唯一证据。压缩策略需将学习者发言（尤其答错的）标为高保留级。

**归属：** tutor loop 动工时一并做（长辅导会话出现之前不构成实际问题）。

### H5 · conduct 遵循度要有度量,否则换模型就静默退化

多 provider 环境下,节奏契约的遵循度随模型漂移（已有按模型注入行为
提示的先例）。四个数落进 `usage_events`：assistant 回合长度分布、
检查问题率、kq-kp 发射率、answer-then-teach 覆盖率。

**归属：** 独立小补丁,纯遥测追加,不触引擎;建议 v0.3.0 前落地,
给后续所有调整提供基线。

### H6 · memory 工具不能成为能力标签的后门

四层契约禁止固化能力标签,学习状态激活是受信操作;但 memory 是模型
自写的,容易养成 "user is weak at X" 类记忆。在 `MEMORY_GUIDANCE` 加
一条：学习者知识状态的观察一律走 learning store（evaluation 草稿）,
不进 memory。

**归属：** 一行提示词,随 H1 同一补丁。

## 2. Graph（graph_engine / 3.5）层改造点（LG1-LG6）

### LG1 · tutor loop 的 checkpoint 锚点 = learning space,不是 chat session

学习者中途离开、数日后回来,是常态。session 是临时上下文（四层 §8.1）,
space 才是持久边界。图的 thread/checkpoint 按 `owner + space` 键控,
"上次讲到第二步"才能活过会话。**这是 contracts 解冻评审时要补入的
第一条需求。**

### LG2 · interrupt 是教学法本身,不是审批机制

工作 agent 用 human-in-the-loop 审批危险操作;学习 agent 的每个检查
问题天然是一次 interrupt——图在 `check` 节点挂起等学习者输入。这把
H2 的问题**结构性**解决:小步节奏从"请求模型自律"变成"图的边,
不走不行"。这也是 tutor loop 值得上图引擎的最硬理由。

### LG3 · kq-kp v2：从"主模型发尾巴"改为"廉价后置节点抽取"

现在知识点靠主模型在回复末尾自觉输出：占注意力、有 H1 裸奔问题、
遵循度依赖模型。图化后加一个便宜模型/规则的 post-node 对已生成回复
抽取知识点,主消息保持干净,所有 surface 天然无污染,符合
"good quality, nearly free"。落地后 H1 的门控修法可退役。

### LG4 · advance/remediate 做成显式条件边,教学法变得可测试

"该推进还是该补救"目前由模型在文本里自由心证。做成条件边 + 确定性
策略函数（输入:check 结果 + 薄弱点投影）,可写 golden 测试;
hint-first 被结构性锁在 practice 分支,防"对已懂的人搞苏格拉底"。

### LG5 · 不过度图化（自家教训）

churn + tracing 是重构的真实成本（重构备忘）;PlannerSpec 不许变成第二
执行器（四层 §15.5）。同理:自由聊天保持普通 agent loop,只有显式进入
的结构化活动（辅导一节、刷题一轮、复习一组）才走图。模式入口是用户
动作,不是意图猜测——与 B3 双模式对齐。

### LG6 · goal runner + learning.db = 温柔的到期提醒

有界 goal runner 已在跑 cron;一个调度任务定期查到期卡、发安静的桌面
提示,"她记得你学到哪"从被动变主动。默认静音、opt-in,不喧宾夺主。

## 3. 排期分配

**重构轨状态（2026-07-12）：** Task 11 Step 4 已按 v0.3.0
release-acceptance 关闭，G2 门也已打开；LG1/LG2/H2 的 requirements-only
审查记录见 [Learning Graph contracts](superpowers/specs/2026-07-12-learning-graph-contract-requirements.md)。
这次解冻只定义接口与不变量，不实现 tutor loop、checkpoint 或 interrupt
节点。原先状态（2026-07-05）：Task 11 Step 4 的 ≥14 天 soak 原被豁免,
但豁免合并进 main 后暴露多个 bug,soak 已**重启**,预计延续到
v0.3.0 发布之后仍未结束。因此 phase 3.5 的 **G2 门**（gate,条件 1 =
soak）保持关闭至 v0.3.0 之后;graph_engine 与其 contracts 在 soak 期间
冻结,本文 3.5 桶的全部事项（含 contracts 需求补入）随之顺延。

STUDY 轨不受影响,按 M1 merge → kp-capture 补丁 → M2 merge → M4 →
M5 → M6 推进。

| 项 | 内容 | 桶 | 触发条件 / 时点 |
|----|------|----|----------------|
| H1 | kq-kp gateway 门控 | **立即** | bug 级;只动 prompt 层,soak 期安全;v0.3.0 发布前必须（v0.3.0 会带着 M1 conduct 出门） |
| H6 | MEMORY_GUIDANCE 加一行 | **立即** | 随 H1 同一补丁 |
| H5 | conduct 度量进 usage_events | **立即~M2** | 纯遥测,soak 期安全;v0.3.0 前落地留基线 |
| H3 | Learning Index → ephemeral 槽 | **STUDY 轨** | M4 投影落地后,同里程碑接线 |
| LG6 | 到期复习提醒（goal runner） | **STUDY 轨** | M2 合并后（需要到期卡数据）,可随 M4 |
| LG1 | checkpoint 按 space 键控 | **3.5 轨·需求** | **v0.3.0 之后**,soak 结束、contracts 解冻评审时补入 |
| LG2 | interrupt 一等节点语义 | **3.5 轨·需求** | 同上 |
| H2 | 教学停机条件 | **3.5 轨·需求** | 作为 LG2 的推论一并补入,不做旧 loop 补丁 |
| LG4 | advance/remediate 条件边 | **3.5 轨·实现** | tutor loop 动工时（soak 结束 + G2 门开 + M4 数据就绪之后） |
| LG3 | kq-kp v2 后置抽取节点 | **3.5 轨·实现** | 同上;落地后退役 H1 门控 |
| H4 | 压缩价值函数反转 | **3.5 轨·实现** | 同上,随 tutor loop |

**汇合点：** tutor loop 是两条轨的交汇——需要 3.5 图引擎解冻且 LG1/LG2
语义定型 + M4 的学习状态数据（H3 的投影管道）。它对应 immersive 方案的
M3/B3 与四层管线的 M5/M6 时代,是下一个大设计文档的主题,本文不展开。

**soak 期间的行动清单只有三项：** H1（含 H6）、H5,以及把本文作为
LG1/LG2/H2 的需求存档——soak 结束后的 contracts 解冻评审以本文为
输入,不需要在 soak 期间对引擎做任何占位改动。
