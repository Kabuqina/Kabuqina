# Kabuqina — 开发指南

> **仅 Windows** 的 Tauri 2 桌面应用，包装 [Hermes Agent](https://github.com/NousResearch/hermes-agent)。
> `hermes_core/` 为**自有 agent core**（源自上游快照）：**不自动同步**上游、不是 submodule、不再维护 patch 文件；**可以且将会**在仓库内长期独立演进，改 core 须谨慎、见下文「Core 与 overlay 分工」。
> Core 内部模块说明见 `hermes_core/AGENTS.md`。

**路线记录：** 本仓库已从“patched submodule”迁移为自有 monorepo，并使用 policy-layer 架构。完整迁移记录见 `docs/depatching-plan.md`。

## 架构

```
Tauri 2 shell (Rust)
 ├─ Web shell (React/Vite, `web/`)        ← onboarding, /chat, settings
 ├─ Python child: desktop_entrypoint.py   ← desk_server on loopback
 └─ Python child: gateway.run (optional)  ← messaging adapters
```

- **Web shell**（`web/src/`）不是 Hermes React UI。它负责 onboarding/settings/chat；桌面端不再打包或跳转上游 Hermes dashboard。
- **两个独立 Python 进程**：web child 跑 `desktop_entrypoint.py`；gateway child 跑 `python -m gateway.run`。它们不共享内存。`strip_shims.py` 防止 web child 意外变成 gateway entrypoint。
- Tauri ↔ Python 的通信全部走 **loopback-only HTTP/WS**，每次启动随机端口。
- LLM API key 存在 **Windows Credential Manager**（通过 `keyring`/DPAPI），永不落盘。

## 构建流程（顺序重要）

**前置要求：** Rust 1.80+、Node 20+、PowerShell 7+

```powershell
# 1. Python bundle（下载 standalone CPython 3.11，并安装依赖）
.\python\build_bundle.ps1

# 2. Web shell
cd web; npm ci; npm run build; cd ..

# 3. Dev（组合三层）
.\scripts\dev.ps1

# 或手动 Tauri dev:
cd tauri; cargo tauri dev
```

- `web/` 下的 `npm run build` 使用 `tsc --noEmit`（不是 `tsc -b`），避免 Windows 上 `tsconfig.tsbuildinfo` 文件锁问题。
- `build_bundle.ps1` 只打包桌面 Python runtime；不再构建或复制上游 Hermes React SPA / `hermes_cli/web_dist`。

## Policy layer（`python/src/`）

核心逻辑已经从 monkey-patch overlay 中抽取为可注入的 policy 对象。
每个 policy 都有对应的 overlay wrapper（标记 `# DEPRECATED`）：

| Policy | Overlay Wrapper | 职责 |
|--------|----------------|------|
| `path_policy.py` | `workspace_jail.py`, `path_guard.py` | 将文件 I/O 限制在 workspace + 额外目录内 |
| `secret_store.py` | （内联在 `overlays/__init__.py`） | 从 Tauri bridge 获取 API key（DPAPI） |
| `network_policy.py` | `network_allowlist.py` | 阻止访问 allowlist 外的网络 host |
| `approval_backend.py` | `approval_bridge.py` | 将 shell 命令审批转给 Tauri dialog |
| `tool_policy.py` | `default_toolset.py` | 将工具限制为安全 keep-list（或 power-user list） |
| `gateway_policy.py` | `strip_shims.py` | 平台 feature flags + gateway adapter 默认策略 |

## Overlays（`python/overlays/`）

Python entrypoint 会在导入任何 agent core 模块前调用 `overlays.apply_all()`。七个 overlay 按固定顺序安装：

| 顺序 | Overlay | 效果 |
|------|---------|------|
| 1 | `strip_shims` | 在 web child 中 stub gateway imports |
| 2 | `desktop_llm_config` | 桌面端专用 LLM routing |
| 3 | `workspace_jail` | 将文件 I/O 限制到 workspace + temp + data dir |
| 4 | `network_allowlist` | 阻止访问 allowlist 外的网络 host |
| 5 | `default_toolset` | 将工具限制为安全 keep-list（或 power-user list） |
| 6 | `builtin_helpers` | L1 QuickActions dispatch |
| 7 | `approval_bridge` | 将 shell 命令审批转给 Tauri dialog |

默认情况下 overlay 失败即 fatal。设置 `HERMESDESK_OVERLAY_LENIENT=1` 可让失败非 fatal（仅用于 dev/smoke）。

`windows_safety` 和 `secret_loader` overlay 已在 Phase 4 移除（分别是 no-op 和轻量 wrapper）。`python/src/` 下的 policy 文件是目标替代方案；每个 policy wiring 稳定后，对应 overlay 会逐步删除。

## 超级用户模式

由 `HERMESDESK_POWER_USER=1` 控制（Rust 在启动 Python child 前设置）。在 Settings 中切换会 **重启 Python child**，并通过 `default_toolset.py` 重写整个 toolset config。

非超级用户默认工具：`web, file, vision, image_gen, tts, skills, clock, todo, browser, cronjob, messaging`。
超级用户额外增加：`terminal, code_execution, moa`。

## 上游 intake 策略

- `hermes_core/` 是上游 Hermes Agent 的 **冻结快照**。不自动同步。
- 过去 patch 过的行为现在都是本仓库自有代码，直接提交。
- **上游 cherry-pick**（安全公告、CVE 修复、provider API breaking changes）：
  - 手动 `git cherry-pick <commit>` 到 `hermes_core/`
  - commit message: `chore: cherry-pick <hash> <subject>`
  - 记录到 `DECISIONS.md`
- 不做 batch merge。不更新 submodule。不维护 patch files。
- **不计划**整包替换 `hermes_core/`；产品能力以在 core 内小步提交为主，overlay 只承载桌面壳与策略注入。

## Core 与 overlay 分工（`hermes_core`）

Kabuqina 是 monorepo：**agent / gateway / cron / tools 的语义与实现**归 `hermes_core/`；**Windows 桌面壳、凭据、沙箱、投递桥**归 `python/` + `tauri/` + `web/`。不要为「将来能拔掉 core」而把本属于 core 的逻辑塞进 overlay——overlay 是**集成层**，不是第二套 agent。

### 放哪里

| 层 | 路径 | 职责（放这里） | 不要放这里 |
|----|------|----------------|------------|
| **Agent core** | `hermes_core/` | 对话循环、`run_agent`、工具与 toolset、cron 调度语义（如 `mode: notify`）、gateway 平台适配、provider、session、skills | Tauri/DPAPI、loopback HMAC、`KABUQINA_HOME` 重定向、Windows toast |
| **Policy（目标形态）** | `python/src/*_policy.py` | 可测试、可注入的策略对象（路径、网络、工具集、审批后端） | 大块 monkey-patch；长期应减少 overlay 包装 |
| **Overlays（集成胶水）** | `python/overlays/` | 启动顺序、`strip_shims`、从 Tauri 拉密钥、桌面 LLM 种子、**cron → 桌面通知桥**、审批 UI 桥、gateway 平台插件裁剪 | 与上游等价的 cron「是否跑 LLM」分支（应在 `cron/scheduler.py`） |
| **桌面 Python 服务** | `python/src/`（`desk_server/`、`desktop_entrypoint.py` 等） | loopback API、时区引导、`gateway_env_loader`、bundle 入口 | 复制一份 scheduler |
| **Rust shell** | `tauri/src/` | 子进程监督、凭据库、gateway 多 profile 启动、`USER_PREFS` → profile 的 `_host_prefs.md` | Python 业务逻辑 |
| **Web shell** | `web/src/` | Onboarding、/chat、设置 UI；**不是** Hermes React dashboard | Agent 工具实现 |

### 决策规则（改 core 还是 overlay？）

1. **web child 与 gateway child 都应一致的行为** → 优先改 **`hermes_core`**（单处实现，避免 web 装了 overlay、gateway 漏装）。
2. **仅 Kabuqina 桌面存在**（toast、Tauri 审批、`desktop_delivery` POST）→ **`python/overlays/` 或 `python/src/`**。
3. **能写成 policy 注入、且不必改上游函数体** → 先 **`python/src/` policy**；稳定后删对应 `# DEPRECATED` overlay。
4. **必须 wrap 已导入的 core 函数且短期无法下沉** → overlay，但 issue/注释里写**迁往 core 或 policy 的条件**。

### 谨慎修改 `hermes_core` 的 checklist

- **默认兼容**：新字段有默认值；旧 job / 旧 config 不迁移也能跑（例：`mode` 缺省 = `agent`）。
- **小 diff**：优先在函数**入口早返回**（如 `cron.scheduler.run_job`），避免牵动 `AIAgent` 主路径。
- **不改契约除非必要**：`tick()` → `_deliver_result` 这类稳定管道尽量复用；新能力尽量只换「产出正文的步骤」。
- **测试落在 `hermes_core/tests/`**：行为契约用单元测试钉住；Kabuqina 集成测放 `python/tests/`。
- **可观测**：一条 INFO 日志说明走了哪条分支（如 `mode=notify, skipping agent`）。
- **记录**：非琐碎语义变更写入 `DECISIONS.md`（字段名、与相近功能的区别）。
- **上游 cherry-pick**：仅安全/CVE/provider breaking；`chore: cherry-pick <hash>`，不 batch merge。

### 示例：定时「固定文案提醒」（`mode: notify`）

| 部分 | 位置 |
|------|------|
| `mode: notify`、不调用 `AIAgent`、`message` 字段 | `hermes_core/cron/scheduler.py`、`cron/jobs.py`、`tools/cronjob_tools.py` |
| `deliver=desktop` → Windows 通知 + /chat | `python/overlays/cron_desktop_delivery.py` |
| 更短 tick、时区 | `python/src/cron_scheduler_runner.py`、`desktop_timezone.py` |

## 常用命令

```powershell
# Dev loop（bundle 缺失时构建、安装 web deps、启动 Tauri dev）
.\scripts\dev.ps1
.\scripts\dev.ps1 -Rebuild     # 强制重建 bundle

# 构建 release
.\python\build_bundle.ps1 -Verify
cd web; npm ci; npm run build; cd ..
cd tauri; cargo tauri build

# Python tests（需要 hermes_core/，仓库内已有）
cd python; python -m unittest discover -s tests -p "test_*.py" -v; cd ..

# Lint web/
cd web; npm run lint

# 重新生成 Tauri icons（source PNG: web/public/kabuqina_na_256.png）
cd tauri; cargo tauri icon ..\web\public\kabuqina_na_256.png
```

## Windows 特有注意事项

1. **代理抢 loopback：** Clash、V2Ray、公司 MITM 等系统代理可能把 `127.0.0.1` 路由到代理，导致 Tauri↔Python 通信失败。Rust supervisor 会剥离代理环境变量，并强制 `NO_PROXY=127.0.0.1,localhost,::1`。`secret_store.py` 使用显式空 `ProxyHandler({})`。见 `docs/troubleshooting.md` §1。

2. **Release build 的 MSVC wheel 环境**（如 `pydantic-core`）。构建 release 时使用 **Developer PowerShell for VS**，或使用已设置 VC vars 的 **cmd.exe**。见 `docs/embedded-python-bundled.md`。

3. **需要 PowerShell 7+**。Windows PowerShell 5.1 不支持这些 build scripts。

4. **Secrets 永不落盘**：明文 API key 只在 Python 启动时从 loopback HMAC URL 获取一次，并写入 `os.environ`。

5. **Gateway 与 web child 是两个进程**。不要假设二者共享状态。web child 中的 `strip_shims.py` 会把 `gateway.run` 替换为 no-op stub。

## 运行时路径

| Path | 用途 |
|------|------|
| `python/dist/runtime/` | Bundled Python + hermes_core + overlays + site-packages |
| `%LOCALAPPDATA%\com.kabuqina.app\` | 用户级 app data（logs、KABUQINA_HOME、workspace state） |
| `%LOCALAPPDATA%\com.kabuqina.app\kabuqina-home\` | Kabuqina config root（旧 `hermes-home` 会在首启安全迁移） |
| `%USERPROFILE%\Documents\KabuqinaWork\` | 默认 workspace（可配置） |
| `tauri/target/release/bundle/msi/` | MSI installer 输出 |

## 参考

- **冻结 agent core：** `hermes_core/AGENTS.md`
- **De-patching 迁移计划：** `docs/depatching-plan.md`
- **架构：** `docs/architecture.md`
- **安全模型：** `docs/safety.md`
- **排障：** `docs/troubleshooting.md`
- **产品决策：** `DECISIONS.md`
- **构建细节：** `docs/embedded-python-bundled.md`

---

# Kabuqina — Development Guide (English)

> **Windows-only** Tauri 2 desktop app wrapping [Hermes Agent](https://github.com/NousResearch/hermes-agent).
> `hermes_core/` is our **owned agent core** (forked from an upstream snapshot): no automatic upstream sync, no submodule, no patch files — **we evolve it in-tree**; change core carefully; see **Core vs overlay boundaries** below.
> Module-level notes: `hermes_core/AGENTS.md`.

**Roadmap:** This repo has migrated from a patched submodule model to an owned monorepo with policy-layer architecture. See `docs/depatching-plan.md` for the full migration record.

## Architecture

```
Tauri 2 shell (Rust)
 ├─ Web shell (React/Vite, `web/`)        ← onboarding, /chat, settings
 ├─ Python child: desktop_entrypoint.py   ← desk_server on loopback
 └─ Python child: gateway.run (optional)  ← messaging adapters
```

- The **web shell** (`web/src/`) is NOT the Hermes React UI. It handles onboarding/settings/chat; the desktop product no longer bundles or redirects to the upstream Hermes dashboard.
- **Two separate Python processes** — the web child runs `desktop_entrypoint.py`; the gateway child runs `python -m gateway.run`. They don't share memory. `strip_shims.py` prevents the web child from accidentally becoming the gateway entrypoint.
- All comms between Tauri ↔ Python use **loopback-only HTTP/WS on random ports** per launch.
- LLM API keys live in **Windows Credential Manager** (DPAPI via `keyring`), never on disk.

## Build pipeline (order matters)

**Prerequisites:** Rust 1.80+, Node 20+, PowerShell 7+

```powershell
# 1. Python bundle (downloads standalone CPython 3.11, installs deps)
.\python\build_bundle.ps1

# 2. Web shell
cd web; npm ci; npm run build; cd ..

# 3. Dev (combines all three layers)
.\scripts\dev.ps1

# Or manual Tauri dev:
cd tauri; cargo tauri dev
```

- `npm run build` in `web/` uses `tsc --noEmit` (not `tsc -b`) to avoid `tsconfig.tsbuildinfo` locking on Windows.
- `build_bundle.ps1` only packages the desktop Python runtime; it no longer builds or copies the upstream Hermes React SPA / `hermes_cli/web_dist`.

## Policy layer (`python/src/`)

Core logic extracted from monkey-patch overlays into injected policy objects.
Each policy has a corresponding overlay wrapper (tagged `# DEPRECATED`):

| Policy | Overlay Wrapper | Responsibility |
|--------|----------------|----------------|
| `path_policy.py` | `workspace_jail.py`, `path_guard.py` | Confine file I/O to workspace + extra dirs |
| `secret_store.py` | (inlined in `overlays/__init__.py`) | Fetch API key from Tauri bridge (DPAPI) |
| `network_policy.py` | `network_allowlist.py` | Block egress to non-allowlisted hosts |
| `approval_backend.py` | `approval_bridge.py` | Route shell commands through Tauri approval dialog |
| `tool_policy.py` | `default_toolset.py` | Restrict tools to safe keep-list (or power-user list) |
| `gateway_policy.py` | `strip_shims.py` | Platform feature flags + gateway adapter defaults |

## Overlays (`python/overlays/`)

The Python entrypoint calls `overlays.apply_all()` **before importing any Hermes modules**. Seven overlays install in strict order:

| Order | Overlay | Effect |
|-------|---------|--------|
| 1 | `strip_shims` | Stub-out gateway imports in the web child |
| 2 | `desktop_llm_config` | Desktop-specific LLM routing |
| 3 | `workspace_jail` | Confine file I/O to workspace + temp + data dir |
| 4 | `network_allowlist` | Block egress to non-allowlisted hosts |
| 5 | `default_toolset` | Restrict tools to safe keep-list (or power-user list) |
| 6 | `builtin_helpers` | L1 QuickActions dispatch |
| 7 | `approval_bridge` | Route shell commands through Tauri approval dialog |

Failure is fatal by default. Set `HERMESDESK_OVERLAY_LENIENT=1` to make failures non-fatal (dev/smoke only).

Overlays `windows_safety` and `secret_loader` were removed in Phase 4 (no‑op and trivial wrapper respectively). The policy files under `python/src/` are the target replacement; overlays will be deleted per-policy once their wiring is stable.

## Power user mode

Controlled by `HERMESDESK_POWER_USER=1` (Rust sets it before spawning the Python child). Toggling it in Settings **restarts the Python child** — the entire toolset config is rewritten via `default_toolset.py`.

Without power user: `web, file, vision, image_gen, tts, skills, clock, todo, browser, cronjob, messaging` toolsets.
With power user: adds `terminal, code_execution, moa`.

## Upstream intake policy

- `hermes_core/` is a **frozen snapshot** of the upstream Hermes Agent. No automatic sync.
- All previously-patched behaviors are owned code, committed directly.
- **Upstream cherry-picks** (security advisories, CVE fixes, provider API breaking changes):
  - Manually `git cherry-pick <commit>` against `hermes_core/`
  - Commit message: `chore: cherry-pick <hash> <subject>`
  - Log in `DECISIONS.md`
- No batch merges. No submodule updates. No patch files.
- We do **not** plan to replace `hermes_core/` wholesale; ship product behavior via small, reviewed core commits; overlays stay integration-only.

## Core vs overlay boundaries (`hermes_core`)

Kabuqina is a monorepo: **agent / gateway / cron / tools semantics** live in `hermes_core/`; **Windows shell, secrets, sandbox, delivery bridges** live in `python/` + `tauri/` + `web/`. Do not park core-worthy logic in overlays “just in case” we swap the core — overlays are the **integration layer**, not a second agent.

### Where code belongs

| Layer | Path | Put here | Do not put here |
|-------|------|----------|-----------------|
| **Agent core** | `hermes_core/` | Conversation loop, `run_agent`, tools/toolsets, cron semantics (e.g. `mode: notify`), gateway adapters, providers, sessions, skills | Tauri/DPAPI, loopback HMAC, `KABUQINA_HOME` redirect, Windows toasts |
| **Policy (target shape)** | `python/src/*_policy.py` | Testable injectable policies (paths, network, toolsets, approval backend) | Large monkey-patches; shrink overlays over time |
| **Overlays (glue)** | `python/overlays/` | Boot order, `strip_shims`, Tauri secret fetch, desktop LLM seed, **cron → desktop notify bridge**, approval UI bridge, gateway plugin trimming | Upstream-equivalent “skip LLM” cron branches (belong in `cron/scheduler.py`) |
| **Desktop Python** | `python/src/` (`desk_server/`, `desktop_entrypoint.py`, …) | Loopback API, timezone bootstrap, `gateway_env_loader`, bundle entrypoints | A second scheduler copy |
| **Rust shell** | `tauri/src/` | Child supervision, credential vault, multi-profile gateway, `USER_PREFS` → profile `_host_prefs.md` | Python business logic |
| **Web shell** | `web/src/` | Onboarding, /chat, settings — **not** the Hermes React dashboard | Agent tool implementations |

### Decision rules (core vs overlay?)

1. **Same behavior in web child and gateway child** → prefer **`hermes_core`** (one implementation; avoids overlay only on web).
2. **Desktop-only** (toast, Tauri approval, `desktop_delivery` POST) → **`python/overlays/` or `python/src/`**.
3. **Injectable policy without editing core function bodies** → **`python/src/` policy** first; delete matching `# DEPRECATED` overlay when stable.
4. **Must monkey-patch an imported symbol short-term** → overlay, with a note on **when to move to core or policy**.

### Checklist for low-risk `hermes_core` changes

- **Backward compatible**: new fields default safely; old jobs/config need no migration (`mode` defaults to `agent`).
- **Small diffs**: early return at function entry (e.g. `cron.scheduler.run_job`); avoid touching the `AIAgent` hot path.
- **Reuse pipelines**: keep `tick()` → `_deliver_result` stable; swap only how job output is produced.
- **Tests in `hermes_core/tests/`** for contracts; Kabuqina integration tests in `python/tests/`.
- **Observable**: one INFO log per branch (e.g. `mode=notify, skipping agent`).
- **Document**: non-trivial semantics in `DECISIONS.md`.
- **Upstream cherry-picks**: security/CVE/provider breaks only; `chore: cherry-pick <hash>`; no batch merges.

### Example: scheduled fixed-text notify (`mode: notify`)

| Piece | Location |
|-------|----------|
| `mode: notify`, skip `AIAgent`, `message` field | `hermes_core/cron/scheduler.py`, `cron/jobs.py`, `tools/cronjob_tools.py` |
| `deliver=desktop` → toast + /chat | `python/overlays/cron_desktop_delivery.py` |
| Faster tick, timezone | `python/src/cron_scheduler_runner.py`, `desktop_timezone.py` |

## Key commands

```powershell
# Dev loop (build bundle if missing, web deps, Tauri dev)
.\scripts\dev.ps1
.\scripts\dev.ps1 -Rebuild     # force rebuild bundle

# Build everything for release
.\python\build_bundle.ps1 -Verify
cd web; npm ci; npm run build; cd ..
cd tauri; cargo tauri build

# Python tests (needs hermes_core/ directory — already in tree)
cd python; python -m unittest discover -s tests -p "test_*.py" -v; cd ..

# Lint web/
cd web; npm run lint

# Regenerate Tauri icons (source PNG: web/public/kabuqina_na_256.png)
cd tauri; cargo tauri icon ..\web\public\kabuqina_na_256.png
```

## Windows-specific gotchas

1. **Proxy strangling loopback:** System-wide proxies (Clash, V2Ray, corporate MITM) route `127.0.0.1` to the proxy, breaking Tauri↔Python comms. The Rust supervisor strips all proxy env vars and forces `NO_PROXY=127.0.0.1,localhost,::1`. `secret_store.py` uses an explicit empty `ProxyHandler({})`. See `docs/troubleshooting.md` §1.

2. **MSVC env for wheels on release builds** (`pydantic-core` etc.). Use **Developer PowerShell for VS** or **cmd.exe** with VC vars set when building release. See `docs/embedded-python-bundled.md`.

3. **PowerShell 7+ required** for build scripts. Windows PowerShell 5.1 won't work.

4. **Secrets never touch disk** — the plaintext API key is fetched once from a loopback HMAC URL at Python startup and set into `os.environ`.

5. **Gateway and web child are separate processes.** Don't assume they share state. `strip_shims.py` in the web child replaces `gateway.run` with a no-op stub.

## Where things live (runtime)

| Path | Purpose |
|------|---------|
| `python/dist/runtime/` | Bundled Python + hermes_core + overlays + site-packages |
| `%LOCALAPPDATA%\com.kabuqina.app\` | Per-user app data (logs, KABUQINA_HOME, workspace state) |
| `%LOCALAPPDATA%\com.kabuqina.app\kabuqina-home\` | Kabuqina config root (legacy `hermes-home` is migrated safely on first launch) |
| `%USERPROFILE%\Documents\KabuqinaWork\` | Default workspace (configurable) |
| `tauri/target/release/bundle/msi/` | MSI installer output |

## References

- **Frozen agent core:** `hermes_core/AGENTS.md`
- **De-patching migration plan:** `docs/depatching-plan.md`
- **Architecture:** `docs/architecture.md`
- **Safety model:** `docs/safety.md`
- **Troubleshooting:** `docs/troubleshooting.md`
- **Product decisions:** `DECISIONS.md`
- **Build details:** `docs/embedded-python-bundled.md`
