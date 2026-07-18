# 场景视觉素材清单（书桌 · 笔记本 · 白板 · 咖啡杯）

**日期：** 2026-07-06

**用途：** 交给设计工具（Claude design）逐项产出的工作清单。素材服务于
[前端愿景](2026-07-06-desk-notebook-frontend-vision.md)（隐喻映射表 §3 =
本清单的"撒谎检查表"：每个素材必须对应真实功能/数据）。

> **2026-07-18 delta：** 全局书桌 first viewport 不重排原母版，只在笔记本前缘/下层新增
> 共用的制作/成果工作夹；Activity/Recent 留在 product chrome，不新增桌上票据。详细
> 构图和状态以
> [v0.5.0 UI 美术设计计划](../plans/2026-07-17-v0.5.0-ui-art-design-plan.md) V-0A/V-2
> 为准。它们必须有 DOM/CSS 中性占位，不能等待私有插画才可用。

**两条纪律（先读）：**

1. **许可**：所有产出文件回库时必须带 `LicenseRef-Kabuqina-Brand` SPDX
   标记（见 assets/brand/README.md 规则）。**P1 场景成品在 A-R1b 资产
   管线决策（Tier 1/2）拍板前不要 commit 进公开仓库**——先存私有位置；
   P0 小件可以进（带标记）。
2. **格式**：一律矢量 SVG（位图纹理禁令，见愿景 §7）；动画素材要求
   **分层 + 命名规范**（热气、眼睛、盖子各自独立 group，命名如
   `steam/`, `eyes/`, `lid/`），前端用 CSS/motion 驱动分层,不要烘焙
   动画帧。所有素材出 light/dark 两版或用 CSS 变量驱动配色（对齐
   `kabuqinaBrandTokens`）。

---

## 第 0 步 · 风格基调页（Style Tile，最先做，只做一页）

在画任何素材前，先让设计工具产出一页定调：桌面材质与主色、纸张白与
纸纹强度、光照方向（建议左上，全套素材统一）、阴影语言（柔和双层）、
线条粗细与圆角半径、与现有 kq-glass 视觉和 lucide 图标线宽的兼容性。
**这一页通过后才开工具体素材，防止风格漂移。**

**状态（2026-07-10）：已通过。** 可维护源文件为
[`Style Tile.html`](../prototypes/Style%20Tile.html)，离线分发副本为
[`Kabuqina Style Tile（离线版）.html`](../prototypes/Kabuqina%20Style%20Tile%EF%BC%88%E7%A6%BB%E7%BA%BF%E7%89%88%EF%BC%89.html)。
v0.4 生命周期首项已由“设置”裁决为“扉页”；小娜杯仅保留为 v0.5
品牌兼容参考，不进入 v0.4 P0 投产。

---

## P0 · v0.4.0 笔记本信息架构就要用的（小件，先做）

| # | 素材 | 变体/状态 | 数据映射 |
|---|------|----------|---------|
| 1 | 生命周期分页图标 ×5（扉页/计划/学习/练习/评估） | active / inactive / hover 三态；16-20px 线性风格,与 lucide 兼容 | M6 分页标签 |
| 2 | 知识点 chip 新形态（贴纸/标签风） | 未收藏 / 已收藏 / 保存中 / 失败 / 推断(带 * 或虚线) 五态 | kq-kp chips |
| 3 | 卡片盒（Leitner 盒）最小版 | 关闭 / 有到期卡(徽标数字) / 空 三态；侧栏尺寸(~24-32px)+面板尺寸(~64px)两档 | flashcard due 队列 |
| 4 | 错题本页标 | 页签/角标形态 + "错题"小图标；有内容 / 空(见 #6) | M4 weak_points |
| 5 | 复习卡片框架（正/反面） | 正面(问题) / 背面(答案) / 翻转中；含 SM-2 四键(再来/困难/良好/轻松)的按钮区形态 | flashcard 复习 |
| 6 | 空态插画 ×4（克制、小幅） | 笔记本空白页(新空间) / 卡片盒空 / 无错题(**值得庆祝的空态**) / 无到期卡 | 各入口空态 |
| 8 | 页边注便签/气泡形态 | 小娜短旁注的容器：默认 / 强调(检查问题) 两态 | 旁注对话 |
| 8b | 扉页版式 | 纸上表单的克制设计;**铅笔字迹(draft) / 墨水字迹(active)** 两种状态的字体/颜色语言 | student_state(M4) |
| 8c | 夹页(草稿)形态 | 夹在本子里的铅笔活页：夹入 / 落墨粘合(激活) / 抽走(拒绝) 三态;M6 统一草稿箱 = 活页合集 | 草稿审核 |

## P1 · v0.5.0 书桌场景丰富资产（A-R1b 决策后投产）

这里的 P1 指**品牌/插画丰富度**。全局书桌的空间结构、文字入口、五类组合 fixture 与中性
DOM/CSS/SVG placeholder 已提升为产品 P0，不依赖本节私有资产；P1 未就绪时不能退回旧
Workbench 或通用 Dashboard。

| # | 素材 | 变体/状态 | 数据映射 |
|---|------|----------|---------|
| 9 | 桌面台面 | light/dark；材质用 CSS 渐变+SVG 噪点表达,设计稿给出参数化描述而非位图 | 场景容器 |
| 10 | 摊开的笔记本主体 | 空白页 / 有内容页的**框架**（不是成品插画）；装订、页边区、纸纹强度 | learning_space |
| 11 | 笔记本封面 ×N | 一课一本：4-6 种封面色/纹理变体 + 书脊标题区；可有一款素色“杂记本”封面，但只用于用户显式创建/选择的自由 space，不是自动 default/capture target | 课程/自由 space 切换 |
| 12 | 桌角书堆 | 2-3 本叠放组合；单本“打开阅读”态框架；只呈现当前 space canonical source_refs 已关联材料 | 本课已引用材料 query |
| 13 | 白板 | 白板框 + 笔槽托盘（Excalidraw 容器的边框语言）；进入/退出白板课的过渡关键帧示意 | tutor loop（v0.5） |
| 14 | 小娜杯 Chat anchor | v0.5 只做现有 fallback 可承载的静态/idle 形态 + “问小娜”DOM 文字与 provider/context badge；speaking/thinking/notify/sleeping/celebrating 六态、吸收 CompanionWindow 与跨 surface 合并移至 v0.5.x/scope swap | Chat semantic action；不新建 companion state |
| 15 | 翻页/换本转场关键帧 | 分页切换、换课程(换本)两组；配合 View Transitions 的起止形态 | 导航转场 |
| 16 | 卡片盒完整版 | 打开态(抽卡)、盒内分格(Leitner 档位)的示意 | SRS 档位可视化 |
| 16b | 书签 | 夹在本中露头的书签：默认 / 高亮("继续上次"悬停) 两态;颜色随本 | 当前计划项 / checkpoint |
| 16c | 书立(合上的本子) | 3-5 本立放、书脊朝外;末端一本空白本("开新本") | 课程空间切换 |
| 16d | 学习日志页版式 | 只读时间线的纸面版式;事件行(答题/复习/完成)的小图标 | learning_activities |
| 16e | 制作/成果薄工作夹 | 从笔记本前缘/下层只露出“＋制作 / 成果”DOM 标签；单 selected activity、多任务摘要+数量及成果 empty/available/missing；不得遮挡本页或卡片盒 | CreateActivity query + DeliverableRecord/Version |
| 16f | Product chrome Activity/Recent | 非家具的 empty/count/attention 组件；waiting/blocked/running 的 icon 只作辅助，完整文字与列表由 DOM 呈现 | ActivitySummary 查询投影 |

## P2 · 锦上添花（有余力再做）

| # | 素材 | 说明 |
|---|------|------|
| 17 | 成就/里程碑小徽章 | 连续复习 N 天、单元完成——克制,不做游戏化;杯子动作优先于徽章 |
| 18 | onboarding 三格引导插画 | "她怎么陪你学"(讲解→知识点→复习) |
| 19 | 场景版社交预览/商店图 | v0.5.0 发布用 hero(书桌全景+小娜) |
| 20 | 加载微动画 | 热气打圈 loading;墨水线条 progress |

---

## 给设计工具的输出要求（每项交付时核对）

- SVG,分层命名(动画组独立),viewBox 规范(方形件 24/32/64,场景件按
  实际比例);
- 颜色引用 CSS 变量名或给出 token 对照(接 `kabuqinaBrandTokens`);
- light/dark 两版或变量驱动;
- 每个素材一句"数据映射"说明(对应上表)——**映射不出真实功能的素材
  不收**(愿景 §3 撒谎检查表);
- 文件头/元数据注明 Copyright (c) 2026 ladylydia, All Rights Reserved。
