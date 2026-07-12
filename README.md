<div align="center">

# 卡布奇娜 · Kabuqina

**陪你学习的 Windows 桌面 AI——帮你学，而不是替你学**

一个学习 agent：引导理解、陪伴练习、记住你学到哪；也能在你需要交付时，把材料变成可继续编辑的报告和 PPT。

[![Windows](https://img.shields.io/badge/platform-Windows-0078D4.svg)](#安装)
[![Tauri 2](https://img.shields.io/badge/Tauri-2.x-24C8DB.svg)](https://tauri.app/)
[![React](https://img.shields.io/badge/React-19-61DAFB.svg)](https://react.dev/)
[![Python](https://img.shields.io/badge/Python-3.11-3776AB.svg)](https://www.python.org/)

</div>

---

## 这是什么

大多数 AI agent 的目标是**代替**人工作：你下单，它交付。但**学习这件事无法被代替**——就像没有人能替你进食。

卡布奇娜（小娜）是围绕这个判断构建的**学习 agent**。她的成功标准不是产出了多少内容，而是**你身上发生了多少变化**：懂了多少、记住了多少、离开她还能做多少。

四条产品铁律：

1. **永不扣留，永远附注。** 你直接要答案，她完整给出，绝不为了"逼你学"而故意难用；但答案后面会标出它建立在哪些知识点上、你跳过了什么值得回头补。每条讲解涉及的知识点会变成可点击的卡片，一键进入你的复习队列。
2. **学习者动手，她引导。** 讲解小步推进，一次一个概念，说完把话语权交回给你；练习时先给提示让你再试一次，而不是直接公布答案。
3. **该快的时候快。** 生成 PPT、整理文档这类任务型工作不受学习节奏约束——高效交付本来就是产品的另一半价值。
4. **记住你学到哪。** 课程空间、知识点、闪卡、测验成绩和薄弱点都持久保存在本机的学习库里，跨会话累积，透明可查、随时可改。

衡量每个功能的唯一一把尺：**它是在加深你的学习，还是在绕过你的学习？**

## 三个入口

| 入口 | 定位 | 你能做什么 |
| --- | --- | --- |
| **对话** | 导师式交流 | 提问、讲解、答疑。讲解带节奏（小步 + 检查理解），回复尾部的知识点卡片一键加入复习队列 |
| **STUDY** | 学习的主场 | 学习画像与路径规划、课程知识库梳理、辅导、间隔重复闪卡、自测测验（确定性判分）、学习效果评估、数学与代码（公式↔代码互转 + 语义校验） |
| **REPORT** | 任务型发射台 | 论文 / 课程 / 代码项目 / 经营沙盘 → PPT，可选视觉母版；产物是可继续编辑的文件 |

## 学习数据如何被对待

- 学习数据存在本机独立的学习库（`learning.db`），按**课程空间**组织，跨会话、跨聊天累积。
- **AI 生成的学习内容一律先进草稿箱**，经过校验、由你审核激活后才进入学习上下文；你的真实行为（答题、评分、复习）直接记录，不需要审批。
- 模型无权激活自己生成的内容，也无权替你确认任何学习状态——这些是只属于你（和受信界面）的操作。
- 她记录你的薄弱点是为了帮你补，**绝不给你贴固定的能力标签**。

## 主要能力

| 能力 | 说明 | 状态 |
| --- | --- | --- |
| 文档读取 | PDF、DOCX、PPTX、XLSX、Markdown、HTML、CSV、图片、文本 | 已接入 |
| 学习管线 | 课程空间、知识库、学习路径、闪卡（SM-2 间隔重复）、测验（本地确定性判分）、知识点捕获 | 主线能力 |
| 报告生成 | 材料索引 → 提纲审阅 → PPTX / Markdown / LaTeX / 报告草稿 | 主线能力 |
| 数学与代码 | 公式 ↔ Python/JS/MATLAB/C++ 互转，SymPy 规范化 + 数值自检 + 语义契约 | 主线能力 |
| 公式识别 | 从公式密集的 PDF / 图片中提取 LaTeX | 需要能力包 |
| 本地语音识别 | 课堂录音、口述笔记转文本 | 需要能力包 |
| 消息入口 | 飞书、QQ、微信、企微、Email 等适配器，用于提醒和投递 | 已接入 |

较大的本地能力（公式识别、语音等）通过 Settings 里的能力包按需下载，基础安装保持轻量。

## 适合谁

经常需要理解难材料、准备考试、补基础、又要按时交作业和报告的学生。

她会诚实地帮你完成交付，但交付之后会提醒你欠了什么。最终判断、引用核对、实验真实性和提交责任仍然属于你自己——请不要用她绕过课程、学校、期刊或团队的学术诚信要求。

## 安装

卡布奇娜目前只支持 Windows 10/11。

从 GitHub Releases 下载最新的 `Kabuqina_..._x64-setup.exe`，双击安装。首次启动进入 Quick Start：

1. 选择或确认工作区。
2. 配置 LLM Provider 和 API Key。
3. 按需进入 Settings 启用能力包或消息平台。

卡布奇娜采用 BYO API Key 模式，支持 OpenAI、OpenRouter、Anthropic、DeepSeek、Groq、Mistral 等 provider。

## 隐私与安全

重要数据默认留在本机：

- API Key 存入 Windows Credential Manager，不写普通配置文件。
- 学习库（`learning.db`）、会话和日志都在本地（`%LOCALAPPDATA%\com.kabuqina.app\`），不上传。
- 桌面壳和 Python 子进程只通过 `127.0.0.1` loopback 通信。
- 文件工具默认限制在你选择的工作区内；终端等高风险能力需要显式开启超级用户模式。
- 消息平台按发送者隔离学习数据，群里其他人看不到你的空间和草稿。

## 能力边界

她基于你提供的材料工作，但不会自动保证引用准确、推导正确、数据真实，也不保证生成内容可以不经审阅直接提交。AI 生成的学习内容会标注"已确认 / 待确认 / 推断"，推断不冒充事实——但正式提交前，请自己检查来源、公式、代码和课程要求。

## 开发与构建

前置要求：Windows 10/11、Rust 1.80+、Node.js 20+、PowerShell 7+。

```powershell
# 1. 构建 Python runtime（下载 standalone CPython 3.11 并装依赖）
.\python\build_bundle.ps1

# 2. 构建 Web shell
cd web; npm ci; npm run build; cd ..

# 3. 启动开发环境（同步 Python 源码到 runtime 并起三层）
.\scripts\dev.ps1
```

Release 构建：

```powershell
.\python\build_bundle.ps1 -Verify
cd web; npm ci; npm run build; cd ..
cd tauri; cargo tauri build
```

NSIS 安装包输出在 `tauri/target/release/bundle/nsis/`。

常用测试：

```powershell
# Agent core（学习管线、行为契约、双引擎回归）
cd hermes_core
python -m pytest tests/learning tests/agent -o "addopts=" -p no:cacheprovider -q

# 桌面服务层
cd python
python -m pytest tests -o "addopts=" -p no:cacheprovider -q

# Web
cd web
npm run test:chat-ux; npm run lint; npm run build
```

## 技术结构

```text
Tauri 2 shell (Rust)
 ├─ Web shell (React 19 / Vite, web/)      onboarding, chat, STUDY, settings
 ├─ Python child: desktop_entrypoint.py    本地 agent 服务（loopback）
 └─ Python child: gateway.run              可选消息平台适配器
```

- Agent core（`hermes_core/`）源自 [Hermes Agent](https://github.com/NousResearch/hermes-agent)（Nous Research，MIT），作为**自有 core** 在仓库内独立演进；对话运行时仅使用图引擎，教学行为契约（节奏、answer-then-teach、知识点协议）注入在系统提示的规范层，用户自定义人设也无法剥离。
- 学习产物遵循统一契约：AI 内容 → 类型化草稿 → 确定性校验（+按类型的语义审核）→ 用户激活；owner 与课程空间双重隔离。

| 路径 | 作用 |
| --- | --- |
| `web/` | 桌面 Web shell、onboarding、chat、STUDY、settings |
| `python/src/` | 桌面服务、STUDY desk API、policy layer、owner 注入 |
| `hermes_core/` | 自有 agent core：图引擎、学习管线（`learning/`）、工具、cron、gateway |
| `tauri/` | Windows 桌面壳、子进程监督、凭据与系统集成 |
| `docs/` | 架构、安全、排障、发布与设计记录 |

深入阅读：

- [docs/architecture.md](docs/architecture.md) — 整体架构
- [docs/immersive-learning-redesign.md](docs/immersive-learning-redesign.md) — 学习产品原则与路线
- [docs/superpowers/specs/2026-07-01-study-four-layer-learning-pipeline-design.md](docs/superpowers/specs/2026-07-01-study-four-layer-learning-pipeline-design.md) — 学习数据管线契约
- [docs/learning-runtime-alignment.md](docs/learning-runtime-alignment.md) — 运行时与图引擎的演进方向

## 排障

- Python 行为陈旧：重新运行 `.\python\build_bundle.ps1`（应用运行的是拷贝出的 runtime，不是源码）。
- 系统代理影响本地连接：确认 Clash、V2Ray、公司代理不代理 `127.0.0.1` / `localhost`。
- Release 构建遇到 MSVC wheel 问题：使用 Developer PowerShell for VS。
- 更多见 [docs/troubleshooting.md](docs/troubleshooting.md)。

## English

Kabuqina is a Windows desktop **learning agent** for students. Most AI agents are built to do work *instead of* you; learning cannot be delegated, so Kabuqina is built to make *you* change — understand more, retain more, do more without her.

Her operating rules: never withhold an answer, but always annotate what it rests on (knowledge points become one-click review flashcards); teach in small steps and hand the turn back; move fast on plain deliverable tasks (papers/slides → editable PPTX, Markdown, LaTeX); and remember where you are — course spaces, spaced-repetition cards, quiz results, and weak points persist locally in `learning.db`, where AI-generated study content always lands as a reviewable draft that only you can activate.

Built with Tauri 2, React 19/Vite, an embedded Python runtime, and an owned Hermes Agent core (graph-based engine). API keys live in Windows Credential Manager; all data stays local. For build instructions see above; for design docs see `docs/`.

## License

双许可：**代码 Apache-2.0**（[LICENSE](LICENSE)），**品牌与视觉资产专有**
（[assets/brand/LICENSE](assets/brand/LICENSE)，含小娜形象、logo、场景美术——
无论它们以独立文件还是内联代码形式存在）。美术母版保存在私有仓库中；
本仓库默认自带中性无品牌占位资产（Apache-2.0），从源码构建即为无品牌版，
官方发行版在构建时注入真实品牌资产。拆分细则见 [BRAND.md](BRAND.md)。
Apache-2.0 不授予商标权：fork 不得使用 Kabuqina / 卡布奇娜名称与咖啡杯形象
作为产品标识。内置的 Hermes Agent core 为上游 MIT 许可
（[hermes_core/LICENSE](hermes_core/LICENSE)）。
