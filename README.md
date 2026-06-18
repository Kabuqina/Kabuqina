<div align="center">

# 卡布奇娜 · Kabuqina

**面向学生的 Windows 桌面 AI 学术助手**

把论文、课件、代码、公式、录音和笔记整理成可继续修改的报告、PPT、提纲、Markdown、LaTeX 或代码说明。

[![Windows](https://img.shields.io/badge/platform-Windows-0078D4.svg)](#安装)
[![Tauri 2](https://img.shields.io/badge/Tauri-2.x-24C8DB.svg)](https://tauri.app/)
[![React](https://img.shields.io/badge/React-18-61DAFB.svg)](https://react.dev/)
[![Python](https://img.shields.io/badge/Python-3.11-3776AB.svg)](https://www.python.org/)

</div>

---

## 这是什么

卡布奇娜是一个 Windows 桌面应用，包装了 Hermes Agent，并针对学生常见的学习和交付场景做了整理。

它不是单纯的聊天窗口。它更像一个学习协作者：先读你的材料，再整理证据和结构，最后帮你起草可以继续编辑的文件。

典型流程是：

```mermaid
flowchart LR
  A[读入材料] --> B[整理索引]
  B --> C[审阅提纲]
  C --> D[生成文件]
```

你可以把它用于：

- 课程报告、实验报告、课程设计和作业材料整理
- 论文精读、文献汇报和课堂展示
- 从 PDF、PPT、Word、表格、代码、截图或录音中提取要点
- 生成 PPTX、Markdown、LaTeX、报告草稿和代码解释
- 整理公式、术语、证据、章节结构和待补充信息

## 适合谁

卡布奇娜适合经常面对“材料很多，但不知道怎么整理成可交付内容”的学生。

它可以帮你做准备工作、结构化材料、起草初稿和生成文件，但最终判断、引用核对、实验真实性和提交责任仍然属于你自己。

请不要用它绕过课程、学校、期刊或团队的学术诚信要求。

## 主要能力

| 能力 | 能帮你做什么 | 状态 |
| --- | --- | --- |
| 文档读取 | 读取 PDF、DOCX、PPTX、XLSX、Markdown、HTML、CSV、图片和文本 | 已接入 |
| 材料索引 | 把材料整理成事实、公式、表格、代码片段、论点和来源位置 | 主线能力 |
| 提纲规划 | 生成报告或 PPT 结构，并列出假设、缺口和待确认点 | 主线能力 |
| 文件写出 | 生成可继续编辑的 PPTX、Markdown、LaTeX、报告草稿或代码说明 | 主线能力 |
| 公式处理 | 从公式密集材料中提取和整理 LaTeX / Markdown 表达 | 需要能力包 |
| 本地语音识别 | 把课堂录音、口述笔记或讨论内容转成文本 | 需要能力包 |
| 消息入口 | 配置飞书、QQ、微信、企微、Email 等入口，用于后续提醒和投递 | 桌面入口已接入 |

较大的本地能力不会默认全部打进基础包里。公式识别、本地语音等能力通过 Settings 里的能力包按需启用，这样首次安装和普通使用更轻。

## 安装

卡布奇娜目前只支持 Windows 10/11。

普通用户请从 GitHub Releases 下载最新的 `Kabuqina_..._x64-setup.exe`，双击安装即可。

首次启动时会进入 Quick Start：

1. 选择或确认工作区。
2. 配置 LLM Provider 和 API Key。
3. 按需进入 Settings 启用能力包或消息平台。

卡布奇娜采用 BYO API Key 模式。你需要准备 OpenAI、OpenRouter、Anthropic、DeepSeek、Groq、Mistral 或其它已支持 provider 的 API Key。

## 隐私与安全

卡布奇娜默认把重要数据留在本机：

- API Key 存入 Windows Credential Manager，不写入普通配置文件。
- 桌面壳和 Python 子进程只通过 `127.0.0.1` loopback 通信。
- 文件工具默认限制在你选择的工作区和少量必要目录内。
- 普通模式只开放安全工具集；终端、代码执行等更高风险能力需要超级用户模式。
- 日志和应用数据位于 `%LOCALAPPDATA%\com.kabuqina.app\`。

建议把工作区放在你熟悉的位置，例如默认的 `Documents\KabuqinaWork\`。

## 能力边界

卡布奇娜会尽量基于你提供的材料工作，但它不会自动保证：

- 引用一定准确
- 推导一定正确
- 实验或数据一定真实
- 生成内容可以不经审阅直接提交

在正式提交前，请自己检查来源、事实、公式、代码和课程要求。

## 开发与构建

前置要求：

- Windows 10/11
- Rust 1.80+
- Node.js 20+
- PowerShell 7+

从源码运行：

```powershell
# 1. 构建 Python runtime
.\python\build_bundle.ps1

# 2. 构建 Web shell
cd web
npm ci
npm run build
cd ..

# 3. 启动开发环境
.\scripts\dev.ps1
```

Release 构建：

```powershell
.\python\build_bundle.ps1 -Verify
cd web
npm ci
npm run build
cd ..
cd tauri
cargo tauri build
```

NSIS 安装包通常输出到：

```text
tauri/target/release/bundle/nsis/
```

常用检查命令：

```powershell
# Python tests
cd python
python -m unittest discover -s tests -p "test_*.py" -v
cd ..

# Web lint
cd web
npm run lint
cd ..
```

## 技术结构

```text
Tauri 2 shell (Rust)
 ├─ Web shell (React/Vite, web/)          onboarding, chat, settings
 ├─ Python child: desktop_entrypoint.py   local agent service
 └─ Python child: gateway.run             optional messaging adapters
```

重要目录：

| 路径 | 作用 |
| --- | --- |
| `web/` | 桌面 Web shell、onboarding、chat、settings |
| `python/src/` | 桌面服务、能力状态、policy layer、loopback API |
| `python/overlays/` | Hermes 集成胶水、工具策略、审批桥、桌面行为 |
| `hermes_core/` | 自有 agent core、工具、cron、gateway、provider |
| `tauri/` | Windows 桌面壳、子进程监督、凭据和系统集成 |
| `docs/` | 架构、安全、排障、发布和开发记录 |

更详细的架构说明见 [docs/architecture.md](docs/architecture.md)。

## 排障

- 构建或运行时发现 Python runtime 行为陈旧：先重新运行 `.\python\build_bundle.ps1`。
- 系统代理影响本地连接：确认 Clash、V2Ray、公司代理等不会代理 `127.0.0.1` / `localhost`。
- Release 构建遇到 MSVC wheel 问题：使用 Developer PowerShell for VS，或已配置 VC 环境的终端。
- 更多问题见 [docs/troubleshooting.md](docs/troubleshooting.md)。

## English

Kabuqina is a Windows desktop AI assistant for students. It helps turn papers, slides, documents, formulas, code, audio notes, and other study material into reviewable deliverables such as outlines, reports, PPTX files, Markdown, LaTeX, and code explanations.

It is built with Tauri 2, React/Vite, an embedded Python runtime, and an owned Hermes Agent core. API keys are stored in Windows Credential Manager, and local file operations are restricted to the configured workspace by default.

For development, follow the build commands above. For architecture and release details, see the documents under `docs/`.

## License

See [LICENSE](LICENSE).
