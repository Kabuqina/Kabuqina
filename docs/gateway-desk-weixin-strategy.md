# Kabuqina：消息网关接入说明（路线对比 · 个微深度 · 当前落地）

本文档说明：为什么 Desk 选用 **路线 C**（本地 Python worker + Tauri IPC）、**个人微信（Weixin / iLink）** 在自有 Core 中的位置，以及 **当前 Kabuqina 已交付** 的保留消息渠道实现。前半为设计对照，后半为与代码一致的产品/工程事实。

---

## 1. 背景：网关能力在哪里

- **运行时**：`hermes_core/gateway/` — 各平台适配器（`platforms/*.py`）、进程入口 `run.py` 等。
- **交互式配置（含扫码）**：`python/src/weixin_qr_worker.py`、`python/src/qqbot_qr_worker.py` 复用 Core 协议逻辑，Tauri command 管理短时 worker，Web shell 展示二维码和绑定状态。
- **个人微信（个微）**：
  - 协议与扫码：`hermes_core/gateway/platforms/weixin.py` — `qr_login()`（腾讯 iLink：`get_bot_qrcode` / `get_qrcode_status`）。
  - Desk 向导：`python/src/weixin_qr_worker.py` 调用 `qr_login(...)`，成功后写入 `WEIXIN_ACCOUNT_ID`、`WEIXIN_TOKEN` 等。

Desk API **没有**提供用于「启动微信/QQ 扫码 / 轮询绑定状态」的 HTTP 接口。这些流程在 **短时 Python worker + Tauri IPC** 中完成，凭据落到 **`{数据目录}/kabuqina-home/.env`**。Desk 因此走了 **路线 C**（见下文），而不是仅靠 WebView 调 HTTP。

---

## 2. 在 Desk 侧接入网关的三条路线（设计对照）

| 路线 | 做法 | 优点 | 缺点 / 风险 |
| --- | --- | --- | --- |
| **A. 嵌 WebView，只调已有 HTTP** | 只使用 Desk API | 无新 HTTP 面 | **无法**完成微信/QQ 扫码绑定；手填密钥体验差 |
| **B. 在 `desk_server` 增薄 HTTP** | 包装 `qr_login`、QQ `create_bind_task`+`poll` 等 | Web 内体验统一 | 新端点需鉴权、审计与生命周期管理 |
| **C. Desk 调本地进程（bundle 内 Python）** | Tauri 起子进程，`import` 自有 Core `gateway.platforms.*`，复用协议逻辑 | **少动** `desk_server`；Core/壳边界清晰 | 需 JSON/IPC；二维码接到壳 UI；打包路径固定 |

**维护角度**：路线 **C** 与「不扩大 Desk 本机 HTTP 表面积」一致；路线 **B** 仅在产品明确需要浏览器内绑定时再评估。

---

## 3. Kabuqina 当前结论（与实现对齐）

以下为 **已实现** 的聚合结论，取代早期分阶段排期表述。

1. **路线选型**：Desk 采用 **路线 C**。扫码类渠道由 **短时 Python worker**（`weixin_qr_worker.py`、`qqbot_qr_worker.py`）+ **Tauri command** 驱动；**不改**本地 `web_server` 增加扫码 REST。
2. **长期网关进程**：由 **`tauri/src/gateway_supervisor.rs`** spawn **第二个**嵌入式 Python 子进程（`python -m gateway.run`）。主进程里的 Desk API 仍通过 **`strip_shims`** 避免把 `gateway.run.main` 当入口执行；**磁盘上的 owned Core `gateway/` 完整存在**，仅进程边界不同 — 详见 **`docs/architecture.md`**。
3. **已交付的消息渠道（壳内引导 + 设置）**：
   - **微信（个微）**：Route C / iLink QR；`tauri/src/weixin_qr.rs`，`web/src/components/WeixinQrRouteCBlock.tsx`。
   - **QQ 机器人**：扫码绑定 OpenAPI v2；`tauri/src/qqbot_qr.rs`，`web/src/components/QqbotQrRouteBlock.tsx`。
   - **Telegram**：onboarding 写入 `@BotFather` token；`tauri/src/telegram_env.rs`、`web/src/onboarding/setupCatalog/optionData.ts`。Settings 详情页仍由后续 readiness Gate 负责。
4. **LLM Key**：网关进程与 Desk child 共用 **Credential Manager / `secret_loader`** 注入的供应商凭据，无需为各机器再配一套 Key UI。
5. **全浏览器绑定**：若未来希望 **仅** 在 WebView 内完成扫码，仍可评估路线 **B**；与当前 Desk 实现 **并行** 的是产品决策，而非本文件前提。

---

## 4. 个人微信：技术切片（已实现，可供审计）

下列条目在早期用于排期；**当前代码已覆盖**，保留为检查清单：

1. **`KABUQINA_HOME`**：与 Desk 约定一致 → `{HERMESDESK_DATA_DIR}/kabuqina-home`。
2. **Tauri**：`cmd_weixin_qr_start` / `status` / `cancel`，`cmd_weixin_env_status`；worker 见 `python/src/weixin_qr_worker.py`。
3. **前端**：`WeixinQrRouteCBlock` — 二维码 URL、轮询、成功后 **重启嵌入式 Hermes** 并尽量 **拉起网关**（`lib.rs` 中 `ensure_gateway_after_hermes_respawn`）。
4. **落盘**：`WEIXIN_*` 写入 `kabuqina-home/.env`；配对策略（如 `WEIXIN_DM_POLICY`）遵循 Core 语义，壳内 Settings 含排障文案与 **配对**命令（`tauri/src/pairing.rs`）。
5. **安全**：本机触发；日志避免明文 token；超时/取消路径在 worker 与 Tauri 侧实现。

---

## 5. 上游代码索引（便于跳转）

| 主题 | 路径 |
| --- | --- |
| 微信个微与 `qr_login` | `hermes_core/gateway/platforms/weixin.py` |
| Desk 微信向导 | `python/src/weixin_qr_worker.py` |
| QQ 扫码绑定 | `hermes_core/gateway/platforms/qqbot/onboard.py`；Desk worker `python/src/qqbot_qr_worker.py` |
| Desk API | `python/src/desk_server/` |

---

## 6. 文档维护

架构与路线图请以 **`docs/architecture.md`**、**`docs/ROADMAP.md`**、根目录 **`README.md`** 为准；本文侧重 **网关路线取舍** 与 **个微/iLink** 细节。

网关 **exit code 1**、runtime 与自有 Core 不一致 → **`docs/troubleshooting.md` §12**、`python/build_bundle.ps1`。

**文档版本**：随仓库迭代；目录结构以自有 Core **`hermes_core/`** 为准。

---

## 7. 验证执行（路线 C / iLink）

见 **[gateway-route-c-weixin-validation.md](gateway-route-c-weixin-validation.md)**：`get_bot_qrcode` 字段、打包解释器探测命令、与 Desk 原型对应关系。

---

## 8. Kabuqina 实现一览：网关子进程 · 扫码/token · 设置页

### 8.1 长期网关进程

除 **短时扫码 worker** 外，Desk 按需维持 **消息网关** OS 子进程（与上游 `hermes gateway run` 等价，实现见 `gateway_supervisor.rs`）。

| 项 | 说明 |
| --- | --- |
| **启动** | `bundle_dir/python/python.exe -m gateway.run`；`PYTHONPATH` 指向 `site-packages` + bundle 内 Core 源码根；`KABUQINA_HOME` 指向 Desk 的 `kabuqina-home`（详见 `gateway_supervisor.rs`） |
| **`KABUQINA_HOME`** | `{HERMESDESK_DATA_DIR}/kabuqina-home`，与 Desk child、worker 写 `.env` 一致 |
| **凭据** | `kabuqina-home/.env` |
| **壳 UI** | **设置 → 消息网关**：启停、冷启动自动拉起开关、`gateway_state.json` / `gateway.log` 诊断；`cmd_gateway_status` |
| **bundle 新旧** | 探测 `gateway/run.py` 是否含「首轮连接失败仍保活」类逻辑；前端字段 **`embeddedGatewayStartupSurvival`** |
| **Desk child 重启后** | 若 `.env` 已有消息凭据，尝试 **`ensure_gateway_after_hermes_respawn`** 拉启网关 |

**排障**：Keys 已配仍秒退 → 优先 **stale runtime**（未重跑 **`python/build_bundle.ps1`**）。见 **troubleshooting §12**。

### 8.2 各渠道与主要源文件

| 渠道 | Desk 交互 | Worker / Rust / 前端（主要入口） |
| --- | --- | --- |
| **微信（个微）** | Route C 扫码 | `weixin_qr_worker.py`，`weixin_qr.rs`，`WeixinQrRouteCBlock.tsx`；配对 `pairing.rs` |
| **QQ 机器人** | 扫码绑定 | `qqbot_qr_worker.py`，`qqbot_qr.rs`，`QqbotQrRouteBlock.tsx` |
| **Telegram** | Onboarding Token 表单；Settings 详情待后续 readiness Gate | `telegram_env.rs`，`onboarding/setupCatalog/optionData.ts`，`main.tsx` |

**「已配置」语义（微信）**：`cmd_weixin_env_status` 仅表示 **`WEIXIN_ACCOUNT_ID` 与 `WEIXIN_TOKEN`** 同时在 **`kabuqina-home/.env`** 中非空；与 iLink 当下是否连通无关。缺一则 UI 提示凭据不完整。

**Telegram / QQ**：设置页对各变量集的检测逻辑见对应 **`telegram_env` / `qq_env`** 与组件文案；网关进程读取同一 `.env`。
