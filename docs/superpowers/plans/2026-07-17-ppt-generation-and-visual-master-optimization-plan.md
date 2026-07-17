# PPT 生成质量与视觉母版完整优化计划

> **性质：** 跨版本产品、设计与工程路线。本文把“生成结构/审稿/修改闭环”和
> “视觉母版/背景资产”放在同一张地图中，但不把全部工作承诺给 v0.5.0；每个进入
> 实现的切片仍须另出 just-in-time plan。
>
> **状态：** Draft v1（2026-07-17）。已根据学生反馈完成首轮 scope 裁决：
> v0.5.0 仍以 STUDY 为重心，只接一个可安全延期的 PPT 视觉薄切片。

## 0. 决策摘要

学生反馈的首要问题不是 PPT 缺少章节结构，而是现有母版主要由纯色背景、色块和
简单线条构成，缺少能被感知为“设计过”的图案、纹理、插画和页面节奏。现有内容
合同、15 种布局、五套 visual master、讲者备注和可编辑原生图形应继续作为稳定基线，
不为追求新视觉推倒重来。

完整优化分成两条相互独立、通过统一 deck contract 汇合的轨道：

1. **G · Generation/Review：** 结构化请求、逐页故事板、证据/素材、质量预检、
   预览、局部重生成和版本恢复；
2. **A · Art/Master：** 美术方向、授权素材、角色化背景、真实样张、渲染集成和
   PowerPoint/WPS 视觉验收。

### 0.1 版本裁决

| 版本 | 承诺范围 | 明确不做 | 阻塞关系 |
|---|---|---|---|
| **v0.5.0** | A-0/A-1；新增 2 套艺术化母版；同源真实样张；背景资产渲染管线；仅在 Web 现有 metadata 足够时修正“重生成沿用原母版” | 逐页编辑器、真实图片/图表、局部重生成、真实第三方 `.pptx` 复用 | **Should，非 release blocker**；未过视觉门则整项延期，不挤压 STUDY Must |
| **v0.5.x** | 补齐 4 套艺术化母版；G-1～G-6 的结构化请求、故事板、素材、预检、预览和局部修改 | 通用 PPT 画布、任意模板可靠复用 | 独立 JIT slices，按用户反馈排序 |
| **v0.6 候选** | 真实学校/公司 PPT 模板复用 MVP；模板角色识别、安全回退；更完整版本历史 | PowerPoint 的完整替代品、动画设计器、模板市场 | 复用既有模板路线，经重新技术评审后决定 |

若 v0.5.0 code freeze 时两套艺术化母版未同时满足授权、视觉和兼容门，产品继续保留
现有五套稳定母版，release notes 不宣称本项完成；不得为赶版本降低 STUDY、升级安全
或渠道裁剪的验收标准。

**v0.5 工程预算上限：** 默认只允许修改 `web/src/chat/pptx/`、母版选择器、静态资产、
测试和文档；不新增依赖、模型调用、`hermes_core`/Python/Rust schema 或 migration。
“沿用原母版”若不能利用现有 artifact metadata 在 Web 层完成，整项进入 v0.5.x，
不得为了顺手修正扩大 v0.5 hot files。

## 1. 与其他计划的边界

- [v0.5.0 开发计划](2026-07-17-v0.5.0-development-plan.md) 决定版本优先级和
  release gates；本计划不是第八个 v0.5 支柱。
- [v0.5.0 UX 交互设计计划](2026-07-17-v0.5.0-ux-interaction-design-plan.md)
  负责应用内通用 task/state/focus/keyboard 合同；PPT 专属故事板在 G 轨设计，但必须
  消费相同的 modal、dirty、pending、blocked 和恢复规则。
- [v0.5.0 UI 美术设计计划](2026-07-17-v0.5.0-ui-art-design-plan.md) 负责 Kabuqina
  应用 UI、Learning Space 和品牌资产；本计划负责**用户导出的演示文稿母版**。
- [PPT richer layouts + AI design](2026-06-22-ppt-richer-layouts-and-ai-design-plan.md)
  已完成布局和 design-intent 基线，本计划只在其上增量演进。
- [PPT real template reuse roadmap](2026-06-16-ppt-real-template-reuse-roadmap.md)
  继续承载真实 `.pptx` 对象复用方向；在 v0.5.0 不接入生产路径。

## 2. 当前基线与问题证据

| Surface | 当前行为 | 缺口 |
|---|---|---|
| PPT 入口 | `WorkspacePanel.tsx` 提供论文、课程、课设、沙盘四类入口，只收 goal、emphasis 和 visual master | 受众、时长/页数、必须使用的材料、模板和输出语言没有结构化请求对象 |
| 大纲审核 | `OutlineReviewModal.tsx` 展示整段 Markdown，可整段通过、补充要求或自行编辑 | 看不到逐页来源、布局和密度，不能排序、增删或只改一页 |
| 生成结果 | `PptxRenderCard` 自动渲染并立即回传保存 | 用户没有整套缩略图确认，也不能局部重做或回退 |
| Writer contract | `_deck_slide_spec` 白名单支持布局、表格、图、占位符、metrics、emphasis、notes | 没有真实 image/chart asset contract、稳定 slide id 和 source refs |
| Renderer | PptxGenJS 输出可编辑文字/形状，五套母版共享 15 种布局 | 母版背景仍以 flat fill/色块/线条为主，缺少页面角色化美术资产 |
| 上传模板 | `template_path` 只抽取颜色和字体；失败静默回退 | 不是实际模板复用，产品文案不能暗示 Logo/版式/对象会被保留 |
| 重新生成 | 使用界面当前选中的母版重走整套生成 | 可能无意改变原文件风格，且没有 generation manifest/版本可追溯 |
| 验证 | Python contract tests、Web source assertions、render smoke 已覆盖基本合同 | 缺真实视觉回归矩阵、PowerPoint/WPS 样张和学生审美验收 |

## 3. 产品原则

1. **学生感知优先。** “明显比纯色块更好看”必须由真实样张和学生走查证明，不以
   增加代码字段或母版数量代替。
2. **可编辑性不退化。** 背景装饰可以是 SVG/PNG；标题、正文、表格、图表和主要
   内容继续使用 PowerPoint 原生可编辑对象，不把整页栅格化。
3. **内容与美术解耦。** 同一 deck/storyboard 可切换母版；母版不得改写事实、数字、
   章节或讲者备注。
4. **确定性工作免费。** 布局、预检、素材选择、渲染审计尽量本地确定性执行；除非
   后续另行批准，不为“设计评分”增加第二次模型调用。
5. **诚实降级。** 无真实图片时显示明确占位符；真实模板未复用时只称“提取配色/
   字体”；质量警告不得伪装成已自动修复。
6. **授权先于美观。** moodboard 可以广泛收集，进入安装包/生成文件的每个资产必须
   有可追踪的修改、商业使用和再分发依据。
7. **STUDY 优先。** PPT Should 不得占用 Tutor、练习④⑤、Learning Space 或升级安全
   的 Must 预算；v0.5 切片可以整体关闭并安全回退。

## 4. 成功指标与样张矩阵

### 4.1 固定样张

建立 12 组可重复输入：四类 structure × 三种材料质量（完整、稀疏、混杂/含图片）。
每组冻结材料 hash、期望 must-cover、目标页数区间和不得编造的事实。禁止只用专门为
模板准备的短文本做验收。

### 4.2 评分维度

每份输出同时记录：

- **内容正确性：** must-cover、数字/引用、无重复/空白/纯占位页；
- **视觉质量：** 第一眼区分母版、背景有层次、正文可读、页面节奏不单调；
- **可控性：** 选择的母版、页序、修改和重新生成结果符合用户动作；
- **可编辑性：** PowerPoint/WPS 中可编辑正文、表格、主要图形；
- **兼容性：** 中文字体、16:9、无溢出、无损坏、离线可生成；
- **成本与性能：** 不新增隐式模型调用，背景资产不造成不可接受的 bundle/PPTX 体积。

视觉验收至少包含 owner、2 名目标学生和 1 名非项目设计/产品人员的盲选；记录样本
很小，不把它包装成统计显著性。v0.5 两套新母版须在同内容对照中被多数参与者认为
比当前 flat masters 更适合直接汇报，且没有可读性 P0/P1。

## 5. G 轨 · 生成结构、审稿与修改闭环

### G-0 · 基线、contract inventory 与失败分类

- 冻结 §4 的 12 组材料和当前五母版输出；
- 对 planner → writer → renderer → workspace artifact 建字段流向图；
- 分类 content error、contract error、render error、asset error、compatibility error，
  每类指定 owner 和用户可见恢复动作；
- 记录当前模型调用数、生成耗时、PPTX 大小和布局分布，后续只做 delta comparison。

**Gate G0：** 样张、字段 inventory、错误 taxonomy 和基线审计可复现。

### G-1 · Versioned `PptRequest` 与 generation manifest

用结构化、可版本化的请求替代四段长期漂移的前端 prompt 字符串。最小字段包括：

- `schema_version`、`request_id`、`structure`、`title`、`language`；
- `audience`、`duration_minutes` 或 `slide_count_target`、`goal`、`emphasis`；
- `material_refs`、`must_use_refs`、`template_path`、`visual_master_id/version`；
- `output_path`、`created_at`、planner/model provenance 和 deterministic audit version。

高级字段放进“更多设置”，默认路径仍只需材料、场景和母版。manifest 作为 session/
artifact metadata 保存，不默认把材料正文复制进明文 sidecar；只保存路径、hash、页码/
位置和生成参数。旧 prompt 和旧 artifact 继续可读，缺字段使用安全默认值。

**v0.5 条件子集：** 先审计现有 artifact metadata；若它已经携带原
`visual_master_id/version`，只修正 Web 读取和 prompt 选择，确保“重新生成”不会跟随
当前 selector 意外换肤。若 metadata 不存在或需要 schema/migration，G-1 全部延后。

### G-2 · 逐页 storyboard 合同与审核

为每页增加稳定 `slide_id`、`role`、`slide_type`、`layout`、`title`、`body blocks`、
`notes`、`source_refs`、`asset_refs`、`warnings`。审核 UI 由原始 Markdown 升级为逐页
卡片/列表，支持：

- 查看每页标题、角色、布局、来源、讲者备注和警告；
- 拖动排序、添加、删除、复制、修改单页；
- 对单页提出 refine 要求，或保留 raw Markdown 导入/编辑作为高级兼容入口；
- dirty/back/keyboard/pending/timeout 使用 X 轨已冻结的通用合同；
- approve 的是带 revision 的 storyboard，writer 拒绝过期 revision。

### G-3 · 确定性 preflight

阻断项只包含结构损坏、workspace/path 安全错误、无法渲染的 schema；以下质量问题
默认作为可解释 warning，不擅自重写内容：

- must-cover 缺失、重复 agenda/内容页、空白页或纯占位页；
- 文本密度、标题过长、布局单一、speaker notes 缺失；
- 数字无 source ref、citation 不可定位、图表缺数值；
- 真实素材存在却仍使用占位符；
- 背景与前景预计低对比、字体或资产不可用。

用户可返回编辑、带 warning 继续或取消。audit 规则 versioned，测试固定输入输出。

### G-4 · 真实图片、截图和数据图表

- 只从 workspace/已批准目录读取用户材料，沿用 path policy；不自动联网搜图；
- slide contract 增加 bounded `media`/`chart`，包含 source path/hash、caption、crop、alt、
  page/cell refs，不把任意 HTML/SVG 脚本带入 renderer；
- 优先使用材料目录已有截图/结果图；表格/CSV 有足够数值时生成 PowerPoint 可编辑图表；
- 图片只可编辑位置/裁剪，图表数据与系列可编辑；找不到真实资产时诚实回退占位符；
- 同一素材去重，控制解码尺寸、PPTX 体积和 EXIF/隐私信息。

### G-5 · 预览、局部重生成与版本恢复

- 正式保存前显示由**同一 deck spec/asset manifest**生成的整套缩略图；
- 支持只换布局、只换母版、只重生成选中页，不能把“局部”暗中变成全套重写；
- 局部模型重生成只接收该页所需 source refs、相邻页摘要和固定 storyboard contract；
- 每次生成形成新 revision，保留上一版的 manifest 和输出路径，提供明确比较/恢复；
- 取消、超时、渲染失败和 workspace 写入失败不得覆盖上一份成功文件。

### G-6 · Post-render QA

Render audit 增加实际使用的 master/asset/version、每页布局、placeholder、媒体、字体、
overflow heuristic 和文件大小。自动门负责 XML/zip/schema、页数、对象和资产完整性；
真实视觉裁切、字体替换和 WPS/PowerPoint 差异通过固定样张截图/人工矩阵验证。不能把
“生成了 base64”当作视觉通过。

## 6. A 轨 · 视觉母版、美术资产与真实样张

### A-0 · 美术 brief、moodboard 与授权台账

搜罗分为两个互不混淆的集合：

1. **Reference only：** 记录 URL、截图日期、吸收的抽象特征和禁止复制的具体元素；
2. **Shipping candidate：** 记录作者、原始 URL、license/订单、允许修改与再分发的条款、
   attribution、文件 hash、修改记录、应用内和生成 PPT 中的 notice 位置。

优先级依次为：自有原创/委托并取得权利 → MIT/CC0 等可明确再分发资产 → 有书面
embedded digital-product 权利的采购资产。授权不明、只允许个人使用、禁止应用集成、
禁止模板再分发或要求无法稳定兑现署名的资产不得进入 product bundle。

SlidesCarnival 可作为 reference；其 CC BY 4.0 路径要求署名且禁止模板原样再分发：
<https://www.slidescarnival.com/faqs>。Hero Patterns 当前为 MIT，可作为图案研究候选，
但必须保留 copyright/license notice：
<https://github.com/lowmess/hero-patterns/blob/master/LICENSE>。unDraw 官方授权明确提示不要
把素材集成进应用或重新打包，因此默认排除：<https://undraw.co/license>。任何来源在
真正采用时重新保存许可快照；本文不是法律意见。

**Gate A0：** 20～30 套 reference moodboard、6 个 art direction brief、shipping
candidate 台账和拒绝清单经 owner review；未过授权门不进入设计稿。

### A-1 · 背景资产与 master manifest 合同

每套母版不是一张背景反复铺满，而是六个页面角色：

| Role | 美术强度 | 安全区要求 |
|---|---|---|
| `cover` | 强，允许主图案/插画/大留白构图 | 标题、副标题、署名三块安全区 |
| `section` | 中强，章节编号和主题图案 | 标题必须在 200% 等效检查下清晰 |
| `content` | 弱，低透明纹理/角落或边缘母题 | 正文主区域无高频纹理 |
| `data` | 弱，网格/坐标/图例辅助 | 数据墨水优先，背景不伪造数据 |
| `media` | 中，图片框/胶片/画册构图 | 不遮挡 caption/source |
| `closing` | 强，与 cover 呼应 | Q&A/感谢/联系方式可读 |

建议新增 `MasterAssetManifest`：`id`、`version`、`roles`、`palette slots`、`safe zones`、
`contrast surface`、`format`、`source/license/hash`、`fallback`。资产默认放在
`web/src/assets/pptx/<master-id>/`，随 Web bundle 离线提供，不从运行时 CDN 拉取。

- 16:9，SVG 优先；必须使用位图时提供经过压缩的 PNG/WebP 源和 PPTX 兼容输出；
- SVG 使用可替换 palette tokens，允许 built-in palette 和上传模板配色重着色；
- raster-only 背景不得宣称可跟随上传模板配色；
- 主要内容保持原生可编辑，装饰背景可不可编辑；
- Windows/WPS 安全字体优先，任何额外字体必须单独过授权与 fallback；
- 定义单页/PPTX/bundle 体积预算，在 A-0 基线后冻结数字，不凭空写阈值。

**Gate A1：** manifest schema、safe-zone overlay、license ledger、fallback 和体积基线通过。

### A-2 · 六个目标 art directions

| ID（暂定） | 场景 | 视觉母题 | 首发版本 |
|---|---|---|---|
| `academic_paper` | 论文/文献汇报 | 纸张颗粒、页码、编辑批注线、书刊排版 | **v0.5.0** |
| `tech_blueprint` | 课设/代码答辩 | 蓝图网格、电路/节点线、柔和光晕 | **v0.5.0** |
| `campus_editorial` | 社团/课程/综合展示 | 校园刊物、图片拼贴、版面标记 | v0.5.x |
| `notebook_study` | 课程学习汇报 | 笔记纸、便签、胶带、克制手绘符号 | v0.5.x |
| `business_topography` | 沙盘/商业分析 | 等高线、路线、金融坐标和数据纹理 | v0.5.x |
| `organic_science` | 科学/通用清新 | 有机曲线、植物/细胞轮廓、颗粒渐变 | v0.5.x |

每个 direction 至少产出六 role backgrounds、title/body/data palette、字体栈、装饰组件、
三页真实样张和禁止组合。v0.5 新增两个新 ID，不就地改变既有五个 ID 的外观，避免
旧 deck/回归样张发生不可解释漂移；后续可把旧五套标记为“经典/简洁”，根据使用与
反馈决定保留、升级或退场。

### A-3 · Renderer 集成

- 新建集中式 master asset registry，`visualMasters.ts` 只声明设计 token/recipe，
  renderer 不硬编码散落路径；
- 背景层永远先于内容对象，content/data role 可加不透明 reading surface；
- cover、section、content、data、media、closing 根据 slide role/layout 确定性选择；
- SVG palette token 在本地转换为 data URI；解析失败、资产缺失或 WebView2 不支持时
  回退现有 flat master，不中断 PPT 生成；
- 记录每页实际 asset id/version/hash 到 `RenderAudit`；
- 仍支持五个 legacy masters 和上传模板 palette override；上传 palette 与不可重着色
  raster 冲突时明确选择/提示，不静默产出低对比结果。

### A-4 · 母版选择器与真实样张

当前 CSS 配色预览不能代表实际输出。选择器改为消费与 renderer 同源的 preview
manifest，展示 cover + content + data 三页缩略样张，并标注适用场景、浅/深、图案
强度和“经典/艺术化”。不得手工维护一套与最终 PPT 不一致的营销缩略图。

选择动作即时预览但不改已生成 artifact；“重新生成”默认沿用 artifact 的原母版，
用户必须显式选择“更换母版”才改变。图片加载失败时显示母版名和 palette fallback，
不能空白或阻断入口。

### A-5 · 视觉、兼容和可访问 QA

每个新 master 至少验证：

- 四类 structure、中文/英文、短/长标题、3/5/8 bullets、表格/diagram/chart/media；
- 封面、章节、正文、数据、媒体、结束六种 role；
- PowerPoint 与 WPS 打开、保存、重新编辑；
- 100%/投影观看、低分辨率屏幕、灰度打印抽查；
- 无低对比、文字落入图案高频区、背景伪装成数据、字体缺失、图片拉伸或超大文件；
- 离线、资产缺失、旧 artifact、上传模板 palette 和五 legacy masters 的 fallback；
- license/NOTICE、source hash 和 bundle manifest 完整。

**Gate A5：** 固定样张截图、兼容矩阵、学生盲选、体积/性能 delta 和授权清单均通过。

## 7. v0.5.0 薄切片实施包

本节是 scope contract，不直接授权 mega diff。建议拆为四个小提交/JIT slice：

### Slice 5A · 资产合同与 renderer 背景层

**主要文件：**

- Modify: `web/src/chat/pptx/visualMasters.ts`
- Modify: `web/src/chat/pptx/renderDeck.ts`
- Create: `web/src/chat/pptx/masterAssets.ts`
- Create: `web/src/assets/pptx/README.md`
- Test: 新建 runtime/unit tests；扩展 `web/src/chat/chatUx.test.mjs`

**完成：** role asset manifest、SVG/PNG 离线加载、safe fallback、RenderAudit asset 字段。

### Slice 5B · 两套原创/已清权母版

**主要文件：**

- Create: `web/src/assets/pptx/academic-paper/*`
- Create: `web/src/assets/pptx/tech-blueprint/*`
- Create: `docs/licenses/pptx-visual-assets.md`

**完成：** 每套六 role backgrounds、设计 token、许可/hash 台账、真实三页样张。

### Slice 5C · 同源选择器预览

**主要文件：**

- Modify: `web/src/chat/WorkspacePanel.tsx`
- Reuse/Create: `web/src/chat/pptx/masterPreview.ts`
- Test: `web/src/chat/chatUx.test.mjs` + 组件交互测试

**完成：** 两套新母版可见、三页样张同源、加载失败 fallback、键盘/读屏可选择。

### Slice 5D · 原母版重生成（条件项）与 release QA

**主要文件：**

- Modify: `web/src/chat/WorkspacePanel.tsx`
- Test: 原母版保持、显式换肤、旧 artifact fallback

**完成：** JIT plan 先审计真实保存边界；只有现有 metadata 足够时，重新生成才在
v0.5 默认使用原母版。若不足，记录延期而不加 schema。无论条件项是否进入，两套新
母版都必须完成 A-5 矩阵；release notes 只描述实际进入安装包的能力和限制。

### 7.1 v0.5 stop rule

以下任一发生即停在现有五母版并把 5A～5D 整体移入 v0.5.x：

- 授权不能明确支持应用内嵌/生成文件分发；
- 需要修改稳定 planner/writer schema 才能显示背景；
- Web/PPTX/bundle 体积或生成耗时超过 A-0 冻结预算且无法局部优化；
- PowerPoint/WPS 出现损坏、不可读或难以安全回退；
- 占用 STUDY Must owner/hot files，导致 Tutor/Practice/Learning Space gate 延迟。

## 8. v0.5.x 与 v0.6 排序

v0.5.x 建议按以下顺序推进，前一项有真实用户证据再进入下一项：

1. A-2 剩余四套艺术化母版；
2. G-1 完整请求/manifest + G-3 preflight；
3. G-2 逐页 storyboard 审核；
4. G-4 workspace 真实图片与可编辑图表；
5. G-5 缩略图预览、局部重生成与版本恢复；
6. G-6 post-render QA 自动化。

v0.6 重新评审真实模板复用路线，先证明能安全复制模板 slide/object、识别角色、替换
明确文本并保留无关对象，再接入 `pptx_write`；失败始终回退 visual master。完整画布、
任意动画、在线模板市场、自动联网搜图和多人协作不在当前路线承诺内。

## 9. 测试与验证门

每个实现切片按影响面运行，不把命令清单当作视觉证据：

```powershell
cd web
npm run lint
npm run test:chat-ux
npx tsc --noEmit
npm run build
cd ..

cd hermes_core
python -m pytest tests/tools/test_document_tools.py tests/agent/test_prompt_builder.py -q
cd ..
```

当 slice 修改 Python desktop integration 时补跑：

```powershell
cd python
python -m unittest discover -s tests -p "test_*.py" -v
cd ..
```

此外必须保存：12 组固定样张、两套新母版的 role matrix、PowerPoint/WPS 人工结果、
bundle/PPTX size delta、生成耗时、许可快照和学生盲选记录。没有真实样张时，自动测试
全绿也不能宣告 A 轨完成。

## 10. 风险与缓解

| 风险 | 缓解 |
|---|---|
| 搜到的模板好看但不能随应用再分发 | reference/shipping 双台账；A-0 授权门；原创/open 优先 |
| 每页同一张强背景导致阅读困难 | 六 role backgrounds；content/data 低强度；safe zones + reading surface |
| 背景图片让 PPT 失去可编辑性 | 只允许装饰背景栅格化；内容/表格/图表保持原生对象 |
| 新母版与上传模板 palette 冲突 | SVG token 重着色；raster 明示限制；低对比则回退 flat master |
| 实际输出与 selector 预览不一致 | preview 与 renderer 共用 manifest/asset/token，不维护第二套 CSS 假预览 |
| 母版数量增加但质量仍普通 | 两套先做深；固定样张盲选；不过门不以数量交差 |
| PPT 工作挤压 STUDY | v0.5 Should、stop rule、独立 owner/hot-file 审计、可整体延期 |
| 逐页编辑演变成完整 PowerPoint | storyboard 只编辑结构/内容/布局意图；不做自由画布和任意对象操作 |
| 自动质量检查擅自改写内容 | preflight 默认 warning；确定性层只阻断损坏/安全错误 |
| 真实模板能力被营销提前承诺 | UI/release notes 明确“视觉母版”与“仅提取配色/字体” |

## 11. 完成定义

### v0.5.0 slice 完成

- 两套新母版每套六种 role，有完整 license/hash/attribution/fallback；
- selector 展示与 renderer 同源的三页真实样张；
- 12 组固定 deck 中无损坏、空白、不可读、明显裁切或错误资产；
- PowerPoint/WPS 可打开、保存和编辑主要内容；
- 学生对照走查证明视觉提升，且没有 P0/P1 可读性问题；
- 若现有 Web artifact metadata 足够，重新生成默认沿用原母版，显式换肤才改变；
  若不足，已明确延期且没有为此扩大 schema/migration；
- 五 legacy masters、旧 artifact、离线和资产失败均安全回退；
- 没有新增模型调用，没有扩大 workspace/network 权限；
- STUDY Must gates 未因本切片延期。

### 完整路线完成

- 六套艺术化母版均通过 A-5；
- PptRequest/storyboard/manifest versioned 且旧 artifact 可读；
- 用户可以逐页审稿、预览、局部修改和恢复版本；
- workspace 真实图片/图表有来源、隐私和编辑性合同；
- preflight/post-render audit 可解释、可复现、不伪造成功；
- 真实模板复用若进入生产，能力边界、失败回退和营销文案一致。

## 12. 立即下一步

1. 维护已录入登记表的 U-21/U-22/U-23 scope 和本文回链；
2. 建立 A-0 moodboard 表和 shipping license ledger 模板，不先下载资产进仓库；
3. 用当前四类 PPT 各导出一份基线，形成同内容母版对照；
4. 冻结 `academic_paper` 与 `tech_blueprint` 的 art brief、role safe zones 和验收样张；
5. 为 Slice 5A 写 JIT implementation plan；确认背景层可以完全在 Web renderer 内增量实现；
6. 5A 过门后才生产/接入两套母版；任何 stop rule 命中即延期，不改 STUDY 排期。
