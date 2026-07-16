# A-R3 freeze-and-close 复审材料

> **日期：** 2026-07-15
> **基线：** `dce4159a`
> **依据：** `docs/reviews/2026-07-15-a-r3-midterm-review.md`
> **状态：** MR-001 至 MR-005 已关闭；V7、V8 均已通过；实现已由 owner 提交。
> 两轮 CHANGES REQUESTED 的问题已在工作树修复并完成影响面回归；本轮 follow-up
> 的 commit / push 仍需 owner 明确执行。

## 1. MR 关闭说明

### MR-001 — 关闭

- `hermes_core/hermes_cli/__init__.py` 使用 import finder/loader，把
  `hermes_cli.<submodule>` 映射到既有 `kabuqina_cli.<submodule>` module object；
  legacy package 本身也指向 canonical package。
- `hermes_core/tests/kabuqina/test_compat_imports.py` 在两个独立子进程中覆盖
  legacy-first 与 canonical-first，并断言 `config`、`config_home`、`auth`、
  `PROVIDER_REGISTRY` 共享 canonical 状态。
- 新测试文件：`8 passed in 6.06s`。
- compatibility/config 组：`63 passed in 7.56s`，`HERMES_TEST_WORKERS=0`。

### MR-002 — 关闭

- `tauri/src/secrets.rs` 提取可注入的 read/migrate/clear 控制流，不接触真实
  Credential Manager。
- 单测覆盖 copy-forward 成功、copy-forward 写失败仍返回 legacy secret、
  clear-both，以及日志/错误不泄露 secret。
- 首次 cold Cargo 尝试超过五分钟后被终止，只登记为 `not obtained`；其启动的
  Cargo/Rust 进程已单独清理，未当作失败或通过。
- 独占重跑 `cargo test keyring_ -- --nocapture`：`7 passed; 0 failed`。

### MR-003 — 关闭

- 只规范化本次已变更且混合 CRLF/bare-LF 的文件；未格式化未触及仓库。
- `git diff --check HEAD` 与 `git diff --cached --check` 均为零输出、exit 0。
- 最终混合换行检查：`0` 个 changed file。
- 最终 changed Python AST：`601 files / 0 failures`。

### MR-004 — 关闭

- `hermes_core/SOUL.md` 已确认是运行产物并删除，未进入 index。
- V7 再次生成该文件；V7 后再次删除，最终 porcelain 中不含该文件。
- 其余十个中场 untracked 已逐项定性为 review guidance、兼容 shim/stub、测试
  fixture 或 audit tool，并进入目标 staged snapshot。

### MR-005 — 关闭

- 所有应交付文件进入 index 后重跑 tracked-only audit，零 defect；audit tool
  本身与独立 legacy runtime verifier 使用精确路径分类，没有扩大通用 allowlist。
- 独占 Rust targeted：
  - `cargo test keyring_ -- --nocapture`：`7 passed`；
  - `cargo test host_home_ -- --nocapture`：`2 passed`。
- 独占 Rust 全门：
  - `cargo test`：`89 passed; 0 failed`；
  - `cargo check`：exit 0。

## 2. 五个拟提交切片

当前 index 保留完整 staged snapshot，没有创建 commit。下列 ownership manifest
按顺序匹配，规则互斥；每条 staged path 只属于第一条命中的切片。文件数与增删量
来自同一份 `git diff --cached`。结果文档自身只加入切片 5，不改变实现切片。

### S1 — Canonical namespace foundation

暂存摘要（加入本结果文档前）：`113 files, +5340/-4857`。

文件清单规则：

- `hermes_core/kabuqina_cli/**`
- `hermes_core/kabuqina_core/**`
- `hermes_core/tests/kabuqina_cli/**`
- `hermes_core/tests/kabuqina_state/**`
- `hermes_core/hermes_cli/__init__.py`
- `hermes_core/{hermes,kabuqina}_{constants,logging,state,time}.py`
- `hermes_core/tests/kabuqina/test_compat_imports.py`
- `hermes_core/tests/test_kabuqina_{constants,logging,state,time}.py`（只计实际存在的
  staged path）

内容：canonical package/modules、旧 shim、stateful submodule identity 合同与
canonical CLI/state 测试。`pyproject.toml` 的 console/distribution hunk 归 S4。

### S2 — Core internal migration

暂存摘要：`488 files, +4255/-3893`。

文件清单规则：完成 S5、S4、S1、S3 优先匹配后，其余 staged path 全部归 S2；
当前均位于 `hermes_core/**` 或非 audit 的 `scripts/**`。这是 600+ core 机械引用、
类/函数名和对应测试迁移的精确余集，不包含 desktop、distribution 或 guidance。

### S3 — Desktop persistence and credentials

暂存摘要（加入本结果文档前）：`62 files, +831/-324`。

文件清单规则：S4 精确文件排除后，所有 `python/**`、`tauri/**`、`web/**` staged
path。具体分布：Python `42`、Rust `14`、Web `6`。

内容：desktop home resolver/目录迁移、keyring migration、Python child/overlay
路径、对应 Python/Rust 测试，以及必要的 Web 用户提示同步。

### S4 — Distribution and embedded runtime

暂存摘要：`12 files, +1498/-632`。

精确文件清单：

- `hermes_core/pyproject.toml`
- `hermes_core/uv.lock`
- `hermes_core/scripts/install.ps1`
- `hermes_core/scripts/install.sh`
- `python/build_bundle.ps1`
- `python/tests/test_runtime_import_verifier.py`
- `python/tests/test_runtime_pruned_verifier.py`
- `python/tools/verify_bundle_site_packages.py`
- `python/tools/verify_legacy_runtime_imports.py`
- `python/tools/verify_runtime_imports.py`
- `python/tools/verify_runtime_pruned.py`
- `scripts/sync-runtime-sources.ps1`

### S5 — Guidance, audit, and close evidence

加入本结果文档后的暂存摘要：`50 files, +2211/-1229`。

文件清单规则：

- `AGENTS.md`、`DECISIONS.md`
- `docs/**`
- `hermes_core/AGENTS.md`、`hermes_core/CONTRIBUTING.md`、
  `hermes_core/README.md`
- `hermes_core/skills/**`
- `scripts/audit_a_r3_legacy_names.py`

内容：active guidance、skills 指引、两份 plan、中场 review、audit 与本收口证据。

## 3. V0–V6 证据

### V0 — 通过

实际命令：

```powershell
python .\scripts\audit_a_r3_legacy_names.py
git diff --check HEAD
git diff --cached --check
# 对 git diff --cached --diff-filter=ACMR 的 *.py 做 ast.parse
# 对同一 changed-file 集检查 CRLF/bare-LF 混合
```

结果：audit `15,783 tracked hits / 0 defects`；两个 diff check exit 0；
`601` 个 Python 文件 AST 解析零失败；mixed-EOL `0`。

### V1 — 通过

```powershell
$env:HERMES_TEST_WORKERS='0'
.\scripts\run_tests.ps1 tests/kabuqina/test_compat_imports.py `
  tests/kabuqina_cli/test_config.py -q
.\scripts\run_tests.ps1 tests/test_kabuqina_constants.py `
  tests/test_kabuqina_state.py `
  tests/kabuqina_state/test_resolve_resume_session_id.py `
  tests/test_subprocess_home_isolation.py -q
python -m unittest tests.test_bootstrap_modes tests.test_desktop_timezone -v
```

结果：`63 passed`；core home/state `234 passed`；desktop migration/timezone
`22 tests OK`。后者有一条测试模式下无法 import `kabuqina_cli` 的预期日志，但测试
合同通过。Keyring/host-home 的 Rust 聚焦证据列在 V4。

### V2 — 通过

```powershell
$env:HERMES_TEST_WORKERS='2'
.\scripts\run_tests.ps1 tests/test_ipv4_preference.py `
  tests/agent/test_curator_reports.py tests/test_kabuqina_constants.py -q
```

冻结后确认：`31 passed in 11.44s`，固定 2 workers。

### V3 — 通过

```powershell
cd python
python -m unittest discover -s tests -p "test_*.py" -v
```

结果：`Ran 324 tests in 17.174s, OK`。

### V4 — 通过

```powershell
cd tauri
$env:CARGO_BUILD_JOBS='2'
cargo test keyring_ -- --nocapture
cargo test host_home_ -- --nocapture
cargo test
cargo check
```

结果：targeted `7 passed` + `2 passed`；全量 `89 passed; 0 failed`；
`cargo check` exit 0。全部独占运行，未与 Python/Web/bundle 并行。

### V5 — 通过

在 `web/` 依次运行 package.json 中十九个非 watch `test:*` script（包括
`test:components`），随后：

```powershell
npm run lint
npm run build
```

结果：十九个 test script 全通过；components `13 files / 62 tests passed`；lint
exit 0；build exit 0（2426 modules，16.33s）。只出现既有 dynamic-import 与
chunk-size warning。

### V6 — 通过（一次失败后最小修复并完整重跑）

```powershell
.\python\build_bundle.ps1 -Verify
.\scripts\sync-runtime-sources.ps1
python -m unittest tests.test_runtime_import_verifier -v
.\python\build_bundle.ps1 -Verify
```

首次完整 verify 在 smoke 阶段失败：`desk_server` 读取到了旧顶层副本，报
`kabuqina_cli.config` 缺少旧 `get_hermes_home` import。根因是 build script 未在
复制前删除既有 `runtime/desk_server`，形成嵌套目录并保留 stale 文件。最小修复
为 copy 前精确删除目标树，并新增合同测试与独立 legacy identity verifier。

聚焦合同：`6 tests OK`；快速同步的 pruning、canonical imports、两种 import
顺序 legacy identity 全通过。最终完整 verify：exit 0，`1644.5s`，bundle
`1411.4 MB`；pruning、canonical runtime imports、legacy-first、canonical-first、
STT binaries 均通过。

## 4. 最终 legacy audit 分类

包含本结果文档的最终 tracked snapshot：

| 分类 | 数量 |
|---|---:|
| audit-tool | 124 |
| compatibility-documentation | 31 |
| compatibility-implementation | 605 |
| compatibility-shim | 2 |
| compatibility-test-or-fixture | 3,352 |
| desktop-compatibility | 718 |
| history | 8,277 |
| model-or-protocol | 692 |
| retained-upstream-surface | 1,924 |
| source-tree-boundary | 51 |
| upstream-or-legal | 54 |
| **合计** | **15,830** |
| **defect / packaging-defect** | **0** |

## 5. V7 / V8 状态

### V7 — 修复后通过

```powershell
cd hermes_core
$env:HERMES_TEST_WORKERS='2'
.\scripts\run_tests.ps1 -q
```

首次冻结全量结果为：`20 failed, 15324 passed, 176 skipped, 211 warnings,
1 error in 2249.45s (0:37:29)`。没有使用 `-n auto`，没有并发其他构建。

失败分组：

- gateway API server：10 个（health/models/capabilities/session-id）；
- document tools：2 个（DOCX write、PDF precise fallback）；
- math expression tools：6 个；
- MCP OAuth manager：1 个；
- voice silence detection：1 个；
- OCR tools：collection ImportError 1 个。

修复归因与结果：

- 恢复 `hermes-agent`、`X-Hermes-Session-Id`、`owned_by=hermes` 的稳定外部 API
  协议，仅保留内部 canonical imports；
- 在 `dev` extra 与 lock 中补齐 Pillow、python-docx、pypdf、SymPy、NumPy，修复
  document/math/OCR 测试环境合同；
- MCP OAuth 测试断言改为 canonical `_kabuqina_server_name`；
- 两个 voice silence 测试不再依赖 50–60ms 临界 wall-clock sleep；
- process stdout drain 对无 `fileno()` 的 iterator handle 使用兼容 fallback，SSH
  thread warning 的聚焦组不再产生未处理线程异常。

2-worker 原失败集：`141 passed`。第二次全量清零原失败后暴露另一个 voice 临界
时序用例：`1 failed, 15353 passed, 170 skipped, 212 warnings`；该用例确定性修复后，
voice 全文件 `60 passed`，base/SSH/voice 组合 `92 passed, 11 skipped`。

最终受控全量：`15355 passed, 170 skipped, 199 warnings in 1975.99s
(0:32:55)`，exit 0，零 failed、零 error。全程固定 2 workers、独占运行。

### V8 — 通过（2026-07-16）

owner 使用备份、专用测试 data dir 和唯一测试 provider/account
`kabuqina-v8-owner-20260716` 完成安装态升级轮；测试 secret 为合成值，不是真实
API key。升级轮覆盖并通过：

- old-only `hermes-home` 迁移，`state.db` / `learning.db` 标记保持可读；
- both-exist 时 canonical `kabuqina-home` 胜出且 legacy 保持不变；
- rename 失败时回退到 legacy home；
- legacy credential 读取并 copy-forward 到 `Kabuqina` service；
- canonical runtime imports / commands；
- rebuilt NSIS 中 Settings > Model 的 clear-both 产品路径。

clear-both 最终证据：当前与兼容 service 的两项合成凭据均返回 `NONE`，provider row
已移除，Python child 从 PID `3908` 重启为 `15952`，日志中合成 secret 命中数为 `0`。
UI 显示“凭据已清除，本机助手正在重启。”，重启后应用保持响应。测试前不存在的
`settings.json` 已恢复为不存在，两项合成凭据均已清理。

V8 详细本地证据：`.test-output/a-r3-v8/V8-RESULT.md`。因此 A-R3 的运行时验收门
已解除，可进入最终 diff/index 复核与提交；本记录不授权自动 merge 或 push。

## 6. V8 前冻结时 index / porcelain 快照

最终 `git status --porcelain=v1` 为 `725` 条，全部在 index：

| XY | 数量 |
|---|---:|
| `A ` | 13 |
| `D ` | 1 |
| `M ` | 611 |
| `R ` | 100 |
| unstaged | 0 |
| untracked | 0 |

`git diff --cached --shortstat`：`725 files changed, 14135 insertions(+),
10935 deletions(-)`。`git diff --check HEAD`、`git diff --cached --check` 均 exit 0；
changed-file mixed-EOL 为 `0`；`hermes_core/SOUL.md` 不存在。

该冻结快照随后由 owner 落为 consolidated implementation commit `5abea97c`；V8
结果由 `4895a7b4` 记录。原计划的五提交切片未保留，实际提交形态已在 recovery
plan 中作为执行偏差记录。当前 `main` 相对 `origin/main` ahead 3；Codex 本轮没有
创建 commit、merge 或 push。

## 7. CHANGES REQUESTED follow-up（2026-07-16）

安装态 V8 通过后，独立复审发现 2 个 P1、1 个 P2 和 1 个文档 P3。本轮按最小
影响面修复：

- Rust 与 Python desktop home resolver 对每个 data dir 缓存首次选择；首次 rename
  失败后，即使条件恢复，本进程仍继续使用 legacy home，避免 child、cron、gateway
  分裂状态；两端均增加“失败后恢复仍固定”的回归测试。
- clear-both 始终尝试 current/legacy 两个 Credential Manager service；`NoEntry`
  视为成功，其余错误聚合返回。任一删除失败时 provider 配置保持不变，UI 可显示
  真实失败并允许重试。
- gateway proxy 与 API server 共享稳定 session-continuity header 常量；代理与服务
  端测试不再各自硬编码相反名称。
- 两份计划按 `5abea97c`、`4895a7b4` 和实际 consolidated commit 形态回填，不再
  保留“尚无实现 commit”的冻结前陈述。

影响面回归：Python desktop bootstrap `14 passed`；gateway proxy/API contract
`6 passed`；Rust home resolver `3 passed`；Rust secrets module `21 passed`。最终
当时的 legacy-name 审计快照为 `15,826` tracked hits，`0 defects`；第二轮
cross-process follow-up 后的最终数字见 Section 8。本 follow-up 尚未 commit / push。

## 8. Cross-process home follow-up（2026-07-16）

第二轮独立复审指出 Section 7 的 home 缓存只覆盖单个进程，P1 因而重新打开。
本轮进一步建立 Rust shell → Python children 的唯一启动合同：

- Rust bootstrap 在启动任何 child 前固定唯一 host home；`SpawnConfig` 从 process
  cache 取得同一路径，并把它作为 `kabuqina_home` 字段传给主 Python child；重启
  继续复用同一选择。
- 主 Python、gateway profile 以及 Feishu、QQ Bot、WeCom、Weixin 四个 QR worker
  全部经同一 Rust helper 注入 `KABUQINA_HOME` / `HERMES_HOME`，两个名称始终指向
  同一个 Rust-selected path。
- Python entrypoint、typed desktop config 和四个 QR worker 遇到显式 home 时直接
  使用，不再独立执行 rename；只有脱离 Tauri 直接运行且没有显式 home 时，才保留
  standalone migration fallback。
- 新增 fresh Python subprocess 测试，构造“Rust 已选择 legacy、rename 当前可成功”
  的条件，证明 child 仍使用 legacy 且不会创建 canonical 目录；Rust 单测钉住两个
  env 名称的同值注入合同。

影响面回归：Python desktop bootstrap `15 passed`；Rust child-home injection
`1 passed`。最终 legacy-name 审计：`15,830` tracked hits，
`0 defects`。该 P1 已重新关闭；follow-up 尚未 commit / push。
