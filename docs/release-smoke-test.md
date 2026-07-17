# Kabuqina Release Smoke Test

这份清单用于 **NSIS 安装包生成后、正式发布前** 的人工冒烟测试。

目标不是评估生成质量，而是确认核心功能链路可用：

> 能安装，能初始化，能聊天，能读取真实材料，能生成真实文件，失败时应用不崩。

建议每个 Release 至少跑一遍。若时间紧，优先完成标记为 **必测** 的项目。

---

## 0. 测试准备

- [ ] 使用本次 Release 产物：
  `tauri/target/release/bundle/nsis/Kabuqina_0.4.0_x64-setup.exe`
- [ ] 准备一个可用的 LLM Provider API Key。
- [ ] 准备一个测试工作区，例如：
  `%USERPROFILE%\Documents\KabuqinaReleaseSmoke`
- [ ] 准备 3-5 个小型测试材料：
  - [ ] 一个 1-3 页 PDF。
  - [ ] 一个 DOCX 或 PPTX。
  - [ ] 一个 Markdown 或 `.py` / `.js` / `.cpp` 代码文件。
  - [ ] 一个用于 PPT 生成的小材料文件。
- [ ] 如需强制走首次启动流程，先关闭 Kabuqina，并清理：
  - [ ] `%LOCALAPPDATA%\com.kabuqina.app\`
  - [ ] Windows Credential Manager 中服务名为 `Kabuqina` 的凭据。

---

## 1. NSIS 安装与启动（必测）

- [ ] 双击 `Kabuqina_0.4.0_x64-setup.exe`。
- [ ] 安装流程能完成，无 NSIS 报错。
- [ ] 开始菜单或桌面入口能启动 Kabuqina。
- [ ] Windows「应用和功能」中能看到 Kabuqina。
- [ ] 首次启动没有白屏、闪退或长时间无响应。

通过标准：

- 应用能正常启动到 Quick Start、Splash 或 `/chat`。
- 若启动失败，错误信息可理解，并且日志可在 `%LOCALAPPDATA%\com.kabuqina.app\` 找到。

---

## 2. 初始化与最小聊天（必测）

- [ ] Quick Start 能打开。
- [ ] 能选择或确认 workspace。
- [ ] 能保存 LLM Provider 和 API Key。
- [ ] 保存后能进入 `/chat`。
- [ ] 发送一条简单消息，例如：
  `你好，请用一句话介绍你能帮我做什么。`
- [ ] 能收到模型回复。
- [ ] Python child 没有启动失败、反复重启或 fatal overlay error。

通过标准：

- 用户可以从首次启动走到可用聊天状态。
- Provider 配置错误时应显示可理解错误，而不是白屏或崩溃。

---

## 3. 文档读取（必测）

### 3.1 PDF

- [ ] 把一个小 PDF 放进 workspace。
- [ ] 在聊天中要求读取并总结，例如：
  `请读取 workspace 里的 <文件名>.pdf，列出 3 个要点。`
- [ ] 能读取正文并给出内容相关回答。

### 3.2 DOCX 或 PPTX

- [ ] 把一个 DOCX 或 PPTX 放进 workspace。
- [ ] 要求总结文档或课件内容。
- [ ] 能识别文件，并返回与文件内容相关的总结。

### 3.3 Markdown 或代码文件

- [ ] 把一个 Markdown 或代码文件放进 workspace。
- [ ] 要求解释文件结构或某段代码。
- [ ] 回复能引用或概括文件内容。

通过标准：

- 至少 PDF + DOCX/PPTX + Markdown/代码 三类材料中各有一个能被读取。
- 读取失败时应用不崩，错误信息能指向文件不存在、格式不支持或解析失败。

---

## 4. 文件生成（必测）

### 4.1 Markdown 报告草稿

- [ ] 发起请求：
  `请在 workspace 里生成一个 release_smoke_report.md，内容是一份 5 段以内的课程报告草稿。`
- [ ] 文件实际出现在 workspace。
- [ ] 文件能用文本编辑器打开。
- [ ] 内容不是空文件。

### 4.2 PPTX

- [ ] 发起请求：
  `请在 workspace 里生成一个 release_smoke_slides.pptx，做 3 页简单汇报 PPT。`
- [ ] 文件实际出现在 workspace。
- [ ] 文件能用 PowerPoint、WPS 或其它 PPT 软件打开。
- [ ] 打开时没有文件损坏提示。

通过标准：

- 至少 Markdown 和 PPTX 两类输出能真实落盘并可打开。
- 不要求版式或文案质量达标，只要求文件生成链路可用。

---

## 5. 读后生成闭环（必测）

- [ ] 选择一个小材料文件，例如 PDF、Markdown 或 PPTX。
- [ ] 发起请求：
  `请基于 <文件名> 生成一个 3 页汇报 PPT，文件名为 material_based_smoke.pptx。先提炼材料要点，再写入 PPT。`
- [ ] Agent 能先读取材料。
- [ ] Agent 能生成 PPTX 文件。
- [ ] `material_based_smoke.pptx` 能打开，且不是空文件。

通过标准：

- 读材料和写文件在同一任务里能串起来。
- 若质量一般可以接受；若文件损坏、没落盘、应用崩溃，则视为 Release 阻断问题。

---

## 6. 设置页与能力页（建议测）

- [ ] Settings 能打开。
- [ ] Load packages / 能力包页面能打开。
- [ ] 能看到本地语音、公式或 OCR 相关能力状态。
- [ ] 不下载大模型也可以，但状态展示和下载入口不能崩。
- [ ] Power user 开关能显示，切换前后有明确提示。
- [ ] 消息平台入口能打开配置界面，不要求实际配对所有平台。

通过标准：

- 设置类页面没有白屏。
- 入口点击不会导致前端崩溃或 Python child 崩溃。

---

## 7. 错误边界（建议测）

- [ ] 请求读取不存在的文件：
  `请读取 workspace 里的 no_such_file.pdf。`
- [ ] 应返回可理解错误，不应白屏或崩溃。
- [ ] 请求读取一个明显不支持的文件类型。
- [ ] 应返回可理解错误。
- [ ] 重复生成同名文件，例如再次生成 `release_smoke_report.md`。
- [ ] 应能覆盖、改名或明确说明处理方式，应用不应卡死。

通过标准：

- 常见失败路径不会让应用不可用。
- 错误信息能帮助用户调整输入。

---

## 8. 卸载与重装（建议测）

- [ ] 通过 Windows「应用和功能」卸载 Kabuqina。
- [ ] 卸载流程完成，无 NSIS 报错。
- [ ] 再次运行本次安装包。
- [ ] 重装后应用能启动。
- [ ] 若保留用户数据，已有 workspace / key 状态表现符合预期；若已清理数据，应重新进入 Quick Start。

### 8.1 v0.4 updater 信任链切换（必测）

- [ ] 在一份安装过 v0.2/v0.3 且含可识别测试数据的环境上，手工运行 v0.4 NSIS 覆盖安装。
- [ ] 安装后版本显示为 v0.4.0，旧 workspace、设置、会话和 Study 数据按迁移契约保留。
- [ ] 应用 updater endpoint 指向 `latest-v2.json`；旧 `latest.json` 不被新 key 产物覆盖。
- [ ] Release Note 明确旧用户必须手工安装 v0.4 一次。
- [ ] 不把“v0.3 自动升级到 v0.4”列为通过条件；旧私钥不可恢复，因此该链路不可能成立。
- [ ] 将 v0.4 自动升级到一个更高的受控版本作为新信任链的独立验收，最迟在 v0.5 正式发布前完成。

---

## 9. Release 判定

### 可以发布

满足以下条件即可发布：

- [ ] NSIS 安装包能安装并启动。
- [ ] 首次初始化能走通。
- [ ] 最小聊天能收到回复。
- [ ] 至少一个 PDF 或 Office 文档能读取。
- [ ] Markdown 文件能生成并打开。
- [ ] PPTX 文件能生成并打开。
- [ ] 读材料后生成 PPTX 的闭环能走通。
- [ ] v0.2/v0.3 → v0.4 手工覆盖安装后，用户数据保留且应用能启动。
- [ ] 没有白屏、闪退、Python child fatal crash、文件损坏等阻断问题。

### 暂缓发布

出现以下任一情况建议暂缓：

- [ ] 安装包无法安装或启动。
- [ ] Quick Start 无法完成。
- [ ] 配置 API Key 后无法进入聊天。
- [ ] 文档读取主路径全部失败。
- [ ] 文件生成不能落盘。
- [ ] PPTX 生成文件损坏，无法打开。
- [ ] 读后生成闭环卡死或崩溃。
- [ ] 普通错误输入导致应用不可恢复。

---

## 10. 记录模板

```text
版本：
安装包：
测试时间：
测试机器：
Windows 版本：

结果：通过 / 暂缓

阻断问题：
- 无

非阻断问题：
- 无

备注：
- 无
```
