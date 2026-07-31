# 交接简报：Kabuqina 基础组件 Sheet

> **给：** 承接组件 sheet 制作的设计方（Claude Design）
> **本文自包含。**读这一份就能开工，不必先读项目其他文档。
> **产出物：** 一张覆盖全部基础组件、明暗两态的组件 sheet。

---

## 1. 一句话任务

**把一套已经冻结、已经过对比度校验的设计令牌，做成一张可看的组件 sheet。**

不是重新配色，不是探索视觉方向。方向早已确定并冻结，你要做的是把它**呈现出来**，
让后续实现有一张可对照的基准图。

## 2. 这个产品是什么（只讲影响视觉的部分）

Kabuqina 是一个 Windows 桌面学习应用。核心隐喻是**一张书桌**：

- 用户在**课程本**上学习（象牙色纸张，装订成册，标签在顶边）
- 在**工作夹**里做东西（牛皮纸，散页可重排，标签在侧边）
- 桌上有**参考书**（立着的书脊）、**卡片盒**、一只**咖啡杯**（AI 助手"小娜"）、一盏**台灯**（明暗切换）

因此组件不是通用组件。"书脊""复印件""铅笔卡"这些各自承担语义，第 5 节逐个说明。

## 3. 硬约束（改了就是错的）

### 3.1 不要"优化"配色

令牌值**已冻结并做过 WCAG 校验**。三处已无余量，调浅即不达标：

| 组合 | 当前比值 | 说明 |
|---|---|---|
| `--ink-soft` on `--paper-soft` | 4.79 | 刚过 AA，不可再浅 |
| `--brown-ink` on `--manila` | 4.51 | 临界 |
| `--warning` on `--warning-bg` | 4.69 | 刚从 3.99 修上来 |

### 3.2 必须成立的等式

这些关系一旦破坏，界面不报错，只会**静默说谎**：

| 等式 | 表达什么 |
|---|---|
| 当前标签背景 **完全等于** 它所连的纸色 | 这本正打开着，标签与纸连成一体 |
| `--purple-faint` **明显区别于** `--paper-strong` | 铅笔（未生效）vs 落墨（已确认）——暗色下靠色相差承担，蓝通道差 18 |
| 复印件用**去饱和 + 硬投影**，**绝不用虚线** | 虚线是铅笔家族专用，表示"尚未生效" |

### 3.3 材质语义不可互换

- **象牙纸**（`--paper` 系）＝ 课程本、对话纸
- **牛皮纸**（`--manila` 系）＝ 杂记本、工作夹 —— **区别的是"是不是课程"，不是好看**
- **虚线** ＝ 只表示"尚未生效"（铅笔草稿、待新建）
- **楷体** ＝ 只用于**用户亲手写的字**；系统产出的文字绝不用楷体

### 3.4 技术底线

**DOM / CSS / SVG 承重。禁止：位图纹理、重 canvas、皮革或逼真木纹、游戏引擎式渲染。**
纸感要克制——是"纸"不是"做旧羊皮"。玻璃/纸纹关闭后层级必须仍然成立（层级由纸张三阶
与四种线重承担，不依赖模糊）。

## 4. 设计令牌（完整值，直接用）

主题切换方式：`<html data-theme="dark">`。`--lamp-glow` 与 `--lamp-lit` 只在 `:root`
定义，两个主题同值（灯泡不随环境变色）。

### 浅色 `:root`

```css
--page:#E8E7EB; --ink:#40354F; --ink-strong:#4D3C60; --ink-mid:#5F5367; --ink-soft:#756983;
--purple:#6F4B86; --purple-dark:#563A6D; --purple-pale:#F2EBF6; --purple-faint:#F8F3FA;
--purple-wash:#EEE3F2; --purple-line:#D2C2D7; --lavender:#A98CB9;
--paper:#FBF8F1; --paper-strong:#FFFDF8; --paper-soft:#FAF7F3; --surface:#FFFFFF; --wash:#EEE9E5;
--desk:#E9DFD0; --desk-deep:#DDD0BF; --desk-hi:#EFE9DD; --desk-lo:#E4DACB;
--desk-glow:transparent; --veil:rgba(64,53,79,.28); --veil-strong:rgba(64,53,79,.42);
--frame-line:#A9A0AA; --line:#D9CFCA; --line-strong:#C8BAC2;
--line-warm:#DDD3CB; --line-cool:#D5CBD1; --line-faint:#EEE7E1; --gray:#A49AA6;
--manila:#F5EAD8; --manila-hover:#F0DFC5; --manila-line:#DDD0BD; --tan:#C78C70; --brown-ink:#8D604C;
--lamp-glow:rgba(255,193,116,.8); --lamp-lit:#E5A54B;
--warning:#9A5A3C; --warning-bg:#FBEDE2;
--danger:#873E35; --danger-line:#B56A5F; --danger-bg:#FFF8F6;
--success:#3F715B; --success-strong:#355A49; --success-line:#B5CABD; --success-bg:#E9F3ED;
--info:#4D678C; --info-ink:#52677E; --info-line:#AABED5; --info-bg:#E9EFF7;
--shadow:0 10px 30px rgba(74,56,70,.12); --shadow-soft:0 4px 14px rgba(74,56,70,.09);
```

### 暗色 `[data-theme="dark"]`

```css
--page:#1D1A21; --ink:#E8E2EC; --ink-strong:#F0EAF5; --ink-mid:#C9BFD1; --ink-soft:#A89BB3;
--purple:#B795CC; --purple-dark:#CEB3DE; --purple-pale:#473A54; --purple-faint:#413352;
--purple-wash:#524360; --purple-line:#635378; --lavender:#86729B;
--paper:#322D36; --paper-strong:#3A3440; --paper-soft:#2B2731; --surface:#403A4A; --wash:#453E4D;
--desk:#33291F; --desk-deep:#2A211A; --desk-hi:#3A2F24; --desk-lo:#2B2219;
--desk-glow:rgba(255,193,116,.13); --veil:rgba(38,33,44,.82); --veil-strong:rgba(46,40,52,.96);
--frame-line:#4E4657; --line:#4C4550; --line-strong:#5D5466;
--line-warm:#4A423D; --line-cool:#544C5C; --line-faint:#423B44; --gray:#6F6678;
--manila:#493D2D; --manila-hover:#544631; --manila-line:#61503A; --tan:#CF9A7C; --brown-ink:#D9B494;
--warning:#D99A72; --warning-bg:#46332A;
--danger:#E5A094; --danger-line:#8A564D; --danger-bg:#3E2A27;
--success:#8CC2A4; --success-strong:#A5D6BC; --success-line:#435948; --success-bg:#253B30;
--info:#93B2D9; --info-ink:#AAC3E0; --info-line:#3D4E66; --info-bg:#273243;
--shadow:0 10px 30px rgba(0,0,0,.45); --shadow-soft:0 4px 14px rgba(0,0,0,.35);
```

### 字体

```css
界面：  "Segoe UI", "Microsoft YaHei UI", "Microsoft YaHei", system-ui, sans-serif
手写：  "KaiTi", "STKaiti"        /* 只给用户亲手写的内容 */
数学：  Georgia, "Times New Roman", serif   /* 只给公式 */
```

## 5. 组件清单

每项都要**明暗两态**。带 ★ 的是承担语义的物件，不是通用控件，务必按说明做。

### 5.1 通用控件

| 组件 | 说明 |
|---|---|
| 按钮 · 主 | `--purple` 填充，白字；hover 转 `--purple-dark` |
| 按钮 · 次 | `--surface` 底，`--line-cool` 描边 |
| 按钮 · 危险 | `--danger` 字，`--danger-line` 边，`--danger-bg` 底 |
| 按钮 · 禁用 | `opacity:.55`，`cursor:not-allowed` |
| 输入框 / 文本域 | `--surface` 底，`--line-cool` 边 |
| 焦点环 | `box-shadow: 0 0 0 3px #fff, 0 0 0 6px #6F4B86` —— **双层**，保证任何底色上可见 |
| 状态标签（pill） | 四色各一：warning / danger / success / info，用对应的 `*-bg` + 前景 |
| 骨架屏 | `--wash` 底，`prefers-reduced-motion` 下不闪 |

### 5.2 纸与线（层级基准）

| 组件 | 说明 |
|---|---|
| 纸张三阶 | `--paper`（纸面）/ `--paper-strong`（浮起的纸）/ `--paper-soft`（压低的纸），三者并置展示 |
| 线四重 | `--line-warm`（纸与纸之间）/ `--line-cool`（控件描边）/ `--line-faint`（极弱分隔）/ `--line-strong`（结构边），并置展示差异 |

### 5.3 ★ 承担语义的物件

| 物件 | 形态 | 它表达什么 | 拿掉会误解什么 |
|---|---|---|---|
| ★ **铅笔卡** | 虚线 + `--lavender` 边 + `--purple-faint` 底 + 空心序号 | AI 拟的，**用户确认了才算数** | 生成内容与已确认内容混为一谈 |
| ★ **落墨卡** | 实线 + `--paper-strong` 底 + 实心序号 | 用户已确认，进入正式顺序 | 同上 |
| ★ **复印件** | `filter:saturate(.55)` + 硬投影 `3px 3px 0 -1px var(--wash)`，**实线边** | 这是副本，原件在别处 | 用户以为改它会动到原件 |
| ★ **书脊** | 竖排中文（`writing-mode:vertical-rl`），约 30×96，牛皮纸底 | 参考书**立着**（需要时抽一本） | 材料退化成一张可浏览的清单 |
| ★ **横向标签**（书立） | 顶边，圆角朝上；**当前那个的背景 === 纸色**，并向下压 1px | 本子立着露顶边 —— 换课＝换一本本子 | 课程身份与内容脱节 |
| ★ **纵向标签**（工作夹） | 左边缘，圆角朝左；**当前那个的背景 === 夹内纸色**，并向右压 1px | 夹子插着露侧边 —— 与本子是两类东西 | 两个域看起来是同一种容器 |
| ★ **台灯** | 关：`--ink-soft` 描边图标；开：`--lamp-lit` + `drop-shadow(0 0 7px var(--lamp-glow))` | 明暗切换 = 开关灯 | 深浅模式沦为设置项 |
| ★ **咖啡杯** | 右下角锚点（本轮只需占位形状；正式品牌美术属另一轨） | AI 随时在，但不抢主视觉 | 助手变成常驻面板 |

### 5.4 桌面底

暖木渐变，供组件放在上面看效果：

```css
浅色：linear-gradient(180deg, var(--desk-hi) 0%, var(--desk) 55%, var(--desk-lo) 100%)
暗色：同上，另加右上角台灯暖斑
       radial-gradient(620px 420px at 94% 0%, var(--desk-glow), transparent 62%)
```

## 6. 交付格式

**单页 HTML + CSS**，要求：

1. 令牌写在 `:root` 与 `[data-theme="dark"]` 两个块里，**变量名与本文完全一致**——这样产出可以直接并回代码库；
2. 页面顶部给一个明暗切换，两态都能看；
3. 每个组件旁标注它用了哪些令牌；
4. 不引入外部字体、图片或 JS 框架，纯 HTML/CSS（可有极少量原生 JS 做主题切换）。

## 7. 需要更多背景时

（只在需要时看，不是必读）

- 物件语义详解：`docs/superpowers/plans/2026-07-25-v0.5.0-materiality-vocabulary.md`
- 令牌用途 / 禁止用途 / 对比度实测：`docs/superpowers/specs/2026-08-01-v0.5.0-v1-visual-token-spec.md`
- 现有实现（组件的真实 CSS）：`docs/superpowers/prototypes/2026-07-25-v0.5.0-product-canonical/src/styles.css`
- 美术计划总纲：`docs/superpowers/plans/2026-07-17-v0.5.0-ui-art-design-plan.md` §4

## 8. 验收

- [ ] 全部组件明暗两态齐全
- [ ] 令牌名与本文一致，无自创色值
- [ ] 三条等式成立（当前标签 === 纸色 ×2、铅笔面区别于纸面）
- [ ] 复印件用去饱和不用虚线
- [ ] 关闭所有模糊与纹理后，层级仍然读得出来
