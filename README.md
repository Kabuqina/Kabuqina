<div align="center">

# 卡布奇娜 · Kabuqina

**陪你在纸上真正学会的 Windows 自学伙伴**

开一本学习本，回到纸上动手；卡住时拍下这一步，小娜只帮你迈过下一步。

[![Windows](https://img.shields.io/badge/platform-Windows-0078D4.svg)](#安装与体验)
[![Tauri 2](https://img.shields.io/badge/Tauri-2.x-24C8DB.svg)](https://tauri.app/)
[![React](https://img.shields.io/badge/React-19-61DAFB.svg)](https://react.dev/)
[![Python](https://img.shields.io/badge/Python-3.11-3776AB.svg)](https://www.python.org/)

</div>

> [!IMPORTANT]
> 卡布奇娜正在收敛到 **v0.5.0 Study MVP**。本 README 描述最新产品方向；三面学习空间、拍照求助、纸上作业讲评与外部错题入盒仍在开发和验证中，不应被理解为已经发布。当前配置中的应用版本仍为 0.4.0。

## 这是什么

卡布奇娜是一款面向学生的 Windows 自学应用。她不试图替你完成学习，也不把一切搬进屏幕：教材可以是纸书，推导和演算留在草稿纸上，产品只在真正能增加价值的地方出现。

我们希望一个手上只有纸质教材和草稿纸的学生，也能走完一次真实的学习：知道自己学到哪、卡住时得到恰好够用的提示、做完后获得对照讲评，并让错题在合适的时候回来。

```text
开本 → 知道下一步 → 回纸上做 → 卡住时拍一张 → 做完后拍一张 → 进入卡片盒复习
                         ↑ 产品故意不打断纸上学习 ↓
```

这不是一个通用交付物 agent，也不是自动写作业或自动判整页手写答案的工具。Studio、Report、PPT / 文档制作和代码学习已经退出产品范围；保留在仓库中的相关底层代码只是未启用的工程基础。

## 产品原则

1. **学习者动手，小娜引导。** 一次只推进一个知识核、一个下一步。练习卡住时先给方向，不抢走思考过程。
2. **永不扣留答案，永远附上代价。** 你明确索要答案时，她会完整回答，同时说明答案建立在哪些知识点上、你跳过了什么。
3. **证据比标签重要。** 阅读过、计划过不等于学会；答题、复习、纠错才形成学习证据。产品不生成固定能力标签、连续打卡或学生报告。
4. **AI 不能批准自己。** AI 生成的学习内容先成为草稿，经过校验并由你确认后才生效；拍照讲评也必须由你确认“确实做错 / 其实做对 / 看不清”。
5. **来源必须说清楚。** 导入材料、内置材料、拍摄书页和小娜的通识讲解有不同来源标记；看不清时应承认看不清，而不是猜一个合理答案。

衡量功能的尺度只有一个：**它是在加深你的学习，还是在绕过你的学习？**

## 一次完整的学习

1. **开一本本子。** 输入课程名、学习范围和目标即可开始，不要求先把纸质教材变成文件。
2. **看清这一步。** 摊开的本子只呈现当前知识核和下一步，不把整套课程压成仪表盘。
3. **回到纸上做。** 这是产品有意缺席的一段：你的书写、尝试和停顿都属于你。
4. **卡住就拍一张。** 使用相机或上传图片，裁出停笔的位置；小娜默认只告诉你下一步往哪想，全程不要求重新打一遍题目。
5. **做完再拍一张。** 小娜按步骤对照讲评，不冒充自动判分器。只有你确认的错题才进入错题本。
6. **到期再回来。** 纸上错题与应用内练习进入同一个卡片盒，和到期闪卡一起复习、重做。

视觉识别只负责一次结构化转写；后续追问回到文本模型，避免每轮重复上传图片。无法辨认的区域会显式标出，并提供重拍或确认入口。

## 最新界面设计

产品以一张可以长期使用的学习书桌为隐喻，而不是后台管理系统：

| 界面 | 承载什么 |
| --- | --- |
| **摊开的本子** | 当前知识核、下一步、拍照求助和对照讲评 |
| **卡片盒** | 今天到期的闪卡与需要重做的错题 |
| **扉页与材料** | 这本学习本的目标、范围、纸书锚点和已导入材料 |
| **对话** | 开本、提问和需要展开说明的交流；可以准确回到原学习位置 |

桌面、纸张、书立、卡片盒和小娜杯不是装饰性的第二套状态，而是同一份本地学习数据的空间化呈现。整体视觉采用木色书桌、纸张层级和体素物件；台灯同时是明暗主题开关。

v0.5.0 虽然首先发布为 Windows 窗口应用，但交互按触屏优先设计：主要动作靠近下沿，命中区不小于 44 × 44 px，窄布局是主布局，不依赖 hover 或右键。

## 范围与进度

| 能力 | 当前状态 |
| --- | --- |
| 本地学习库、课程空间、材料来源、学习计划、知识核、草稿确认 | 已有底座，持续收敛 |
| 摊开的本子 / 卡片盒 / 扉页与材料三面信息架构 | v0.5.0 实现中 |
| 拍照或上传图片 → 裁剪 → 结构化转写 → 一步提示 | v0.5.0 核心链路，供应商与真实手写样本验证中 |
| 纸上作业对照讲评、用户确认、外部错题入盒 | v0.5.0 实现中 |
| SM-2 到期闪卡与错题重做合流 | 已有闪卡底座，队列合流实现中 |
| 整页手写自动判分、代码练习、学生能力报告 | 明确不做 |
| Studio、Report、PPT / 文档交付物入口 | 已退出产品范围 |

## 学习数据与隐私

- 学习本、计划、卡片、错题、练习记录和学习证据保存在本机的 `learning.db`，按用户与课程空间隔离。
- API Key 存入 Windows Credential Manager，通过一次性 loopback 通道交给 Python 进程，不写入普通配置文件。
- Tauri 与 Python 仅通过随机端口的 `127.0.0.1` HTTP / WebSocket 通信。
- 文件工具默认只能访问你选择的工作区；终端和代码执行等高风险工具只有在显式开启超级用户模式后才注册，并仍需逐次批准。
- 本地保存不等于模型离线运行。对话、明确附加到对话的文件，以及需要视觉讲评的图片，会把完成请求所需的内容发送给你配置的模型服务商。请按材料敏感度选择服务商或自托管端点。
- v0.5.0 的照片合同要求：未确认图片只作临时文件；确认进入错题本后才保存到受管媒体目录，并纳入学习数据导出与彻底删除。

## 适合谁

卡布奇娜适合仍然愿意在纸上读、写、推导和订正，但希望有人帮自己保持方向的学生，尤其是需要理解教材、准备考试、补基础和反复处理错题的人。

如果你的主要目标是让 AI 代写作业、批量生成 PPT / 文档、全自动完成任务，或者把纸笔彻底替换成无纸化答题平台，这不是当前产品要解决的问题。

## 安装与体验

卡布奇娜只支持 Windows 10 / 11。已发布版本可从 [GitHub Releases](https://github.com/Kabuqina/Kabuqina/releases) 下载；请注意，v0.5.0 Study MVP 尚未发布，现有安装包可能仍呈现上一阶段的界面与能力。

首次启动会引导你：

1. 选择或确认工作区。
2. 配置模型服务商和 API Key。
3. 打开一本学习本，之后再按需要添加材料。

项目采用自带 API Key（BYO API Key）模式。实际可用的服务商和模型以应用内设置及当前网络策略为准。

## 开发与构建

前置要求：Windows 10 / 11、Rust 1.80+、Node.js 20+、PowerShell 7+。

```powershell
# 1. 构建嵌入式 Python 3.11 runtime
.\python\build_bundle.ps1

# 2. 构建 Web shell
cd web; npm ci; npm run build; cd ..

# 3. 启动 Tauri、Web shell 与 Python 服务
.\scripts\dev.ps1
```

Release 构建：

```powershell
.\python\build_bundle.ps1 -Verify
cd web; npm ci; npm run build; cd ..
cd tauri; cargo tauri build
```

NSIS 安装包输出在 `tauri/target/release/bundle/nsis/`。

常用检查：

```powershell
# 桌面 Python 服务与集成测试
cd python; python -m unittest discover -s tests -p "test_*.py" -v; cd ..

# Agent core 学习行为契约
cd hermes_core
python -m pytest tests/learning tests/agent -o "addopts=" -p no:cacheprovider -q
cd ..

# Web 组件、静态检查与生产构建
cd web
npm run test:components; npm run lint; npm run build
cd ..
```

## 技术结构

```text
Tauri 2 shell (Rust)
 ├─ Web shell (React 19 / Vite, web/)      onboarding、学习、对话、设置
 ├─ Python child: desktop_entrypoint.py    本地 agent 与学习服务（loopback）
 └─ Python child: gateway.run              可选消息适配器；独立进程
```

| 路径 | 作用 |
| --- | --- |
| `web/` | 桌面 Web shell、学习书桌、对话、onboarding 与设置 |
| `python/src/` | 桌面服务、Study API 与可注入 policy layer |
| `python/overlays/` | Tauri 凭据、审批、桌面投递等集成胶水 |
| `hermes_core/` | 自有 agent core：图引擎、学习语义、工具、cron 与 gateway |
| `tauri/` | Windows 桌面壳、进程监督、凭据库与系统集成 |
| `docs/` | 产品决策、需求、架构、安全与设计记录 |

`hermes_core/` 源自 Nous Research 的 [Hermes Agent](https://github.com/NousResearch/hermes-agent) 快照，现作为仓库内自有 core 独立演进，不是 submodule，也不自动同步上游。通用的 agent / Study / tool 语义放在 core；Windows 凭据、loopback 桥、审批和通知等桌面能力放在 `python/` 与 `tauri/`。

进一步阅读：

- [v0.5.0 Study MVP 需求](docs/superpowers/plans/2026-08-20-v0.5.0-study-mvp-requirements.md) — 最新主回路、范围与出货判据（评审中）
- [自学平板低保真原型](docs/superpowers/prototypes/2026-08-22-v0.5.0-selfstudy-tablet-lofi.html) — 书桌隐喻与纸笔优先的交互基线
- [产品决策](DECISIONS.md) — 已锁定的范围与架构决定
- [架构](docs/architecture.md) · [安全模型](docs/safety.md) · [排障](docs/troubleshooting.md)
- [贡献指南](CONTRIBUTING.md)

## English

Kabuqina is a Windows self-study companion for students who still learn with physical books and scratch paper. Open a notebook, see one next step, work on paper, and take a photo only when you are stuck or ready for feedback. Kabuqina defaults to a small hint, never withholds a directly requested answer, and turns user-confirmed mistakes into future review instead of pretending that reading or planning proves mastery.

The v0.5.0 Study MVP is currently in development. Its target experience is organized around an open notebook, a card box for due reviews and mistakes, and a bookend for goals and sources. Studio, Report, document/PPT production, code learning, automatic full-page handwriting grading, student reports, streaks, and fixed ability labels are outside the product scope.

Learning records stay in a local database and API keys live in Windows Credential Manager. Model-backed chat and vision requests still send the necessary content to the provider configured by the user; Kabuqina does not claim that those requests are offline. The desktop app uses Tauri 2, React 19/Vite, embedded Python 3.11, and an owned graph-based Hermes Agent core.

## License

双许可：**代码 Apache-2.0**（[LICENSE](LICENSE)），**品牌与视觉资产专有**
（[assets/brand/LICENSE](assets/brand/LICENSE)，含小娜形象、Logo、字标与场景美术——
无论它们以独立文件还是内联代码形式存在）。美术母版保存在私有仓库中；
本仓库默认自带中性无品牌占位资产（Apache-2.0），从源码构建即为无品牌版，
官方发行版在构建时注入真实品牌资产。拆分细则见 [BRAND.md](BRAND.md)。
Apache-2.0 不授予商标权：fork 不得使用 Kabuqina / 卡布奇娜名称与咖啡杯形象
作为产品标识。内置 Hermes Agent core 沿用上游 MIT 许可
（[hermes_core/LICENSE](hermes_core/LICENSE)）。
