# Kabuqina Workbench UX Design

> **Authority note（2026-07-18）：** 本文保留为 Chat 三列布局与 workbench interaction 的
> 历史实现基线；“个人 AI 工作台”、Chat-first、Capability 一级导航以及
> `WORK / REPORT / STUDY` 同级模式不再是 v0.5 产品架构权威。当前产品承诺、一级 IA、
> surface 职责与跨面合同以
> [v0.5.0 产品全景与体验架构计划](../plans/2026-07-18-v0.5.0-product-experience-architecture-plan.md)
> 为准。复用本文组件/三列原则时必须经过 Gate E1/E2，不得把旧结构直接美化为最终 IA。

| 属性 | 值 |
|------|-----|
| **Version** | 1.1 |
| **Date** | 2026-05-13 |
| **Status** | Historical implementation baseline; product positioning superseded |
| **Priority** | P1 |
| **Related Docs** | [Companion Window Design](./2026-05-14-kabuqina-companion-window-design.md) |

---

## 1. Summary

将 Kabuqina 的主聊天从「即时通讯工具」升级为「个人 AI 工作台」。保持 Nana  conversational 与可接近的语调，但界面应成为用户**投放材料、追踪进度、获取产出**的稳定场所。

**方向：三列工作台**

| 列 | 职责 | 可折叠 |
|--|------|--------|
| **Left Rail** | 持久导航与工作历史 | ✅ |
| **Center Work Stream** | 实时聊天与活跃任务流 | — |
| **Right Workspace Panel** | 当前工作区上下文 | ✅ |

两侧面板必须可独立折叠；Center 进入 Focus Mode 时占据主导空间。这**不是** B2B 代理任务板——任务不应喧宾夺主，取代个人助理的定位。

---

## 2. Goals & Non-Goals

### 2.1 Goals（按优先级）

| # | 目标 | 优先级 |
|---|------|--------|
| G1 | 让聊天具备「任务感」与「工作区感」，但不变成项目管理应用 | P0 |
| G2 | Shell UI 作为首要产品体验，弱化跳转到 Hermes Dashboard 的入口 | P0 |
| G3 | 提供稳定场所查看：当前材料、任务状态、产出物、快捷操作 | P0 |
| G4 | Left Rail 与 Right Panel 可独立折叠 | P0 |
| G5 | 提供 Focus Mode：Center Chat 成为主导工作区 | P1 |
| G6 | 保留 Nana 友好语调，同时增强工作 affordances | P1 |
| G7 | 优化首次运行 UI 精致度，让用户自信进入工作台 | P1 |

### 2.2 Non-Goals

- ❌ 不构建完整看板、多代理控制室或企业任务控制台。
- ❌ 不将 Hermes Dashboard 访问作为主要行动号召（CTA）。
- ❌ 不在 Right Workspace Panel 内复制 Settings、Capability 或完整会话历史。
- ❌ 不 redesign 冻结的 `hermes_core/` UI。

---

## 3. Terminology

| 术语 | 定义 |
|------|------|
| **Workbench** | 三列布局的整体容器。 |
| **Left Rail** | 左侧窄栏，承载导航与历史。 |
| **Center Work Stream** | 中间主区域，承载聊天、进度、输入。 |
| **Right Workspace Panel** | 右侧面板，展示当前工作上下文。 |
| **Focus Mode** | 两侧面板均折叠，Center 最大化的布局状态。 |
| **Nana** | Kabuqina 的 AI 助手人格。 |

---

## 4. Information Architecture

### 4.1 Left Rail

**职责：** 持久产品区域与历史。

**内容（自上而下）：**
- New Work / New Chat
- Recent Work / Sessions
- Reminders
- Capability
- Export（若保留为持久二级区域）

**设计约束：**
- 保持窄而可扫描（默认宽度 `14rem` / `224px`）。
- Capability 作为一级导航项，而非聊天内的瞬时控件。
- 折叠后：仅显示图标条或 reopen 控件。

### 4.2 Center Work Stream

**职责：** 主要实时对话表面。

**内容：**
- 当前工作标题（可编辑或自动推断的任务摘要）。
- 聊天消息流。
- 紧凑的 Action/Result Cards（当 Nana 创建提醒、使用文件、截图、导出时嵌入在 assistant message 中）。
- Agent 进度指示（工具运行期间）。
- Input Composer：文件附件、截图、语音、发送/停止控件。

**空状态策略：**
- 禁止 Center 变为视觉空洞或纯装饰。
- 空状态 Prompt 应强调「有用的工作起点」：添加文件、截图、整理桌面、创建提醒、让 Nana 起草内容。

### 4.3 Right Workspace Panel

**职责：** 回答「Nana 现在正在处理什么？」

**四大区域：**

| 区域 | 内容 |
|------|------|
| **Current Goal** | 单行可编辑或推断的任务摘要 + 下一步/等待状态。 |
| **Materials** | 附件文件、截图、选中文件夹、相关本地路径。 |
| **Outputs** | 已创建提醒、生成草稿、导出项、活跃工作的近期交付物。 |
| **Quick Actions** | 添加文件、截图、整理桌面、其他上下文感知操作。 |

**约束：**
- 不成为通用 Settings Drawer。
- 始终绑定活跃工作流。
- 默认宽度 `16rem` / `256px`。

### 4.4 Top Actions

- Settings 保留顶部位置（符合现有用户预期）。
- 移除 primary chat 表面的「Open console」动作。
- Console/Dashboard 访问若保留，应置于 Settings → Advanced Diagnostics 下，并解释离开 Shell 的原因。

---

## 5. Layout States Reference

| 状态 | 触发条件 | Left Rail | Center | Right Panel | 适用场景 |
|------|----------|-----------|--------|-------------|----------|
| **Default** | 首次进入 / 恢复上次状态 | 展开 | 正常 | 展开 | 常规多任务 |
| **Left Collapsed** | 用户点击折叠 Left Rail | 收起 | 拉伸 | 展开 | 需要更多横向空间 |
| **Right Collapsed** | 用户点击折叠 Right Panel | 展开 | 拉伸 | 收起 | 专注对话 |
| **Focus Mode** | 用户触发 Focus Mode | 收起 | 最大化 | 收起 | 沉浸式写作或长对话 |
| **Narrow Window** | 窗口宽度 `< 768px` | 图标化或 Drawer | 主导 | Drawer 或隐藏 | 小屏/分屏 |

### 5.1 各状态详细行为

#### Empty Workbench
- **Center：** 邀请用户开始工作（提示添加文件、截图、常见任务、创建提醒）。
- **Right Panel：** 显示空状态的上下文 affordances（添加上述快捷入口）。
- **Left Rail：** 保持历史可用，不与活跃工作竞争注意力。

#### Active Work
- **Center：** 显示聊天与进度。
- **Right Panel：** 汇总 Goal、Materials、Outputs、Next Step。
- **Left Rail：** 历史可用但不干扰。

#### Running Agent
- **Center：** 进度在 Work Stream 中可见（现有 `AgentProgress` 组件）。
- **Right Panel：** 高亮当前步骤或正在使用的材料。
- **Composer：** Stop 按钮保持易达。

#### Focused Chat
- **Center & Composer：** 视觉上主导。
- **Side Panels：** 完全收起，但保留紧凑 affordance 以 reopen Capability / Workspace。
- **Controls：** 运行进度、Stop、附件、截图、语音、发送控件全部保留。

#### Narrow Window (`< 768px`)
- **Right Panel：** 折叠至 Workspace 按钮或 Drawer。
- **Left Rail：** 缩减为图标或紧凑导航表面。
- **Focus Mode：** 仍可用，作为「Chat First」布局一键切换。

---

## 6. Onboarding Direction

本阶段以 UI 与信心优化为主，不改动整体架构：

1. **更强的首屏：** 产品身份标识 + 安全提示（Credential Manager 等）。
2. **更清晰的 Provider/Key 表单：** 状态反馈更平静、不焦虑。
3. **Ready 屏幕引导至 Workbench**，而非 Dashboard。
4. **进度指示器更有实感**，避免抽象 Loading。

---

## 7. Error Handling & Recovery

| 场景 | 行为 | 优先级 |
|------|------|--------|
| 未保存 API Key | 路由至 Onboarding 或 Settings，语言清晰 | P0 |
| Local Helper 启动中 | 平静 Loading 状态，禁止展示空/破损工作台 | P0 |
| 附件/截图/语音/提醒/导出失败 | 在动作附近展示 Scoped Error，保留用户已输入内容 | P1 |
| Right Panel 无内容 | 展示建设性空状态，而非占位符 | P1 |
| 需访问 Hermes Dashboard 诊断 | 标记为 Advanced，解释为何离开 Shell | P2 |

---

## 8. Implementation Plan

### 8.1 Phase 1 — 基础布局（P0）

**目标：** 可运行的三列布局 + 两侧折叠 + Right Panel 四区域空状态。

| 文件/模块 | 改动 |
|-----------|------|
| `web/src/chat/ChatPage.tsx` | 引入三列布局状态管理；集成 Right Panel。 |
| `web/src/chat/ChatSidebar.tsx` | 演进为 Left Rail：添加 Capability 一级入口、折叠状态支持。 |
| `web/src/chat/ChatMessageList.tsx` | 微调空状态 Prompt，强调「有用起点」。 |
| `web/src/chat/ChatInput.tsx` | 保持核心行为，适配 Workbench 布局间距。 |
| **新建** `web/src/chat/WorkspacePanel.tsx` | Right Panel 容器：Goal / Materials / Outputs / Quick Actions。 |
| **新建** `web/src/chat/hooks/useWorkbenchLayout.ts` | 管理 `leftOpen`, `rightOpen`, `focusMode`, `narrowMode` 状态；持久化至 `localStorage`。 |

**状态管理建议：**

```typescript
// useWorkbenchLayout.ts 核心结构
interface WorkbenchLayout {
  leftOpen: boolean;
  rightOpen: boolean;
  focusMode: boolean;
  // 不持久化 narrowMode，由窗口 resize 实时计算
}
```

**默认尺寸：**
- Left Rail：`w-56` (`14rem`)
- Right Panel：`w-64` (`16rem`)
- Center：`flex-1 min-w-0`
- 过渡动画：`transition-all duration-200 ease-out`

### 8.2 Phase 2 — 精致化（P1）

| 功能 | 说明 |
|------|------|
| 可拖拽面板宽度 | 若固定宽度在实际使用中显得僵硬，添加拖拽调整。 |
| Focus Mode 动画 | 更流畅的收起/展开动画，保留 reopen affordance。 |
| Right Panel 实时数据 | Materials / Outputs 从现有 chat state 与附件系统中自动提取。 |
| Onboarding 精致度 | 首屏、Provider 表单、Ready 屏幕 UI Pass。 |

### 8.3 约束

- **不改动** `hermes_core/` 的 React UI。
- 现有路由 `/settings`, `/capabilities`, `/settings/cron`, `/export` 保持为 Shell 原生路由。
- 临时脑暴文件存放于 `.superpowers/`，不进入版本跟踪。

---

## 9. Cross-References

- **Companion Window:** Focus Mode 或 Narrow Window 状态下，Companion 的「Open Main Chat」应恢复主窗口至上次的 Workbench 布局状态（而非强制 Default）。详见 [Companion Window Design](./2026-05-14-kabuqina-companion-window-design.md)。

---

## 10. Testing & Verification

### 10.1 验收标准（Acceptance Criteria）

| # | 标准 | 验证方式 |
|---|------|----------|
| AC1 | 默认布局为三列，Left Rail + Center + Right Panel 同时可见 | 视觉检查 |
| AC2 | 点击 Left Rail 折叠按钮后，Left Rail 收起为图标条或完全隐藏，Center 自动拉伸 | 视觉检查 |
| AC3 | 点击 Right Panel 折叠按钮后，Right Panel 收起，Center 自动拉伸 | 视觉检查 |
| AC4 | Focus Mode 同时折叠两侧，Center 最大化；再次点击恢复之前状态 | 视觉检查 + 状态持久化验证 |
| AC5 | 窗口宽度 `< 768px` 时，Right Panel 自动进入 Drawer/隐藏，Left Rail 图标化 | 浏览器 DevTools 响应式测试 |
| AC6 | 空状态下 Center 显示「有用起点」Prompt，Right Panel 显示上下文快捷操作 | 视觉检查 |
| AC7 | Settings 与 Capability 导航在 Left Rail 中正常工作 | 点击测试 |
| AC8 | Agent 运行期间 Stop 按钮在 Composer 中保持易达 | 功能测试 |
| AC9 | 运行 `npm run lint` 与 `npm run build` 在 `web/` 中零错误 | 命令行 |
| AC10 | `.superpowers/` 下的临时文件未被 Git 跟踪 | `git status` |

### 10.2 回归测试

- 保持现有 chat UX 测试通过（`chatUx.test.mjs`）。
- 验证桌面端与窄窗口布局的交互一致性。
