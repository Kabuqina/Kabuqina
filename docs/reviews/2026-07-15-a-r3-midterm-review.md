# A-R3 中场 Review 与 A 轨收口指令

> **日期：** 2026-07-15
> **审查对象：** A-R3 core identifiers and persistence migration
> **实施计划：** `docs/superpowers/plans/2026-07-14-a-r3-core-persistence-rename-plan.md`
> **恢复计划：** `docs/superpowers/plans/2026-07-14-a-r3-recovery-and-close-plan.md`
> **审查基线：** `dce4159a` (`docs: add A-R3 implementation and recovery plans`)

## 1. 中场结论

**GO 仅限继续执行 freeze-and-close；NO-GO 于提交实现切片、合并、推送或宣布
A-R3 完成。**

恢复与收口计划的方向正确，也准确承认了“先展开实现、后补实施计划”的事实。
当前风险不在计划数量，而在 721 个工作树条目仍未形成可审查切片，并且存在一个
明确的运行时兼容缺陷、一个凭据迁移证据缺口和若干 V0 hygiene 阻塞项。

中场审查开始时的 A-R3 实现快照为：

- `604` 个纯未暂存修改（` M`）；
- `103` 个已暂存 rename、rename 后仍有未暂存修改（`RM`）；
- `4` 个已暂存纯 rename（`R `）；
- `10` 个未跟踪文件；
- 合计 `721` 个 porcelain 条目。

本 handoff 随后新增 1 个 review 文档并修改 2 个已提交 plan，因此交付给 A 轨
agent 时的预期状态为 `606 M / 103 RM / 4 R / 11 ??`，合计 `724` 条。新增的
3 条均为本次 guidance/review 文档变更，不是额外运行时实现。

在以下 MR 项全部关闭前，不得开始 Phase 3 提交切片。

## 2. 阻塞项

### A-R3-MR-001 — `hermes_cli.<submodule>` 会产生 canonical 双实例（P1）

**位置：** `hermes_core/hermes_cli/__init__.py`

当前 shim 只执行：

```python
import kabuqina_cli as _canonical
sys.modules[__name__] = _canonical
```

它只统一顶层 package，没有统一子模块。已复现：

```text
hermes_cli is kabuqina_cli                         -> True
hermes_cli.config is kabuqina_cli.config           -> False
hermes_cli.auth is kabuqina_cli.auth               -> False
legacy.PROVIDER_REGISTRY is canonical registry     -> False
```

`config_home` 的结果还会受导入顺序影响：canonical-first 恰好共享对象，
legacy-first 会加载第二份模块。这样旧插件和 canonical runtime 可能持有两套 cache、
registry、monkeypatch 与模块级单例。

**修复边界：**

1. 旧入口仍只保留一发布周期，不复制 canonical 实现；
2. 正常进程内从任一顺序导入 `hermes_cli.<submodule>` 与
   `kabuqina_cli.<submodule>`，不得执行同一实现文件两次或产生两套状态；
3. 不要求模块经过人为 `reload()` 后永久保持函数对象 identity；本项针对正常
   import 语义与共享运行时状态；
4. 至少覆盖 `config` / `config_home` / `auth` 三个代表性 stateful 子模块；
5. 测试必须用独立子进程覆盖 legacy-first 与 canonical-first，避免测试收集顺序
   把缺陷遮住。

**验收：** 新增测试在 `-n 0` 下通过，并明确断言代表性模块及其 registry/cache
来自同一 canonical 状态；现有 compatibility/config 聚焦组继续通过。

### A-R3-MR-002 — Keyring copy-forward / clear-both 缺少控制流测试（P2）

**位置：** `tauri/src/secrets.rs`

现有测试证明了：

- `Kabuqina` service 先于 `HermesDesk`；
- 只有 canonical 明确 miss 才读 legacy；
- canonical read error 不会被 legacy 值掩盖。

但还没有自动化证明：

1. legacy-only secret 被成功写入 canonical service；
2. copy-forward 写失败时，本次调用仍返回已读到的 legacy secret；
3. explicit clear 对 canonical 与 legacy 两个 service 都发出删除；
4. 日志和错误路径不包含 secret 明文。

**修复边界：** 提取最小可注入读/写/删除 seam 或等价纯控制流 helper；不得在
自动化测试中操作用户真实 Credential Manager 条目。

**验收：** 上述四条有 Rust 单测；owner 的专用测试 credential 手工轮仍保留在
Phase 5，不被单测替代。

### A-R3-MR-003 — V0 diff hygiene 未通过（P2）

`git diff --check HEAD` 当前失败，`docs/troubleshooting.md` 有 36 个换行/尾随
空白报告。抽查还发现 77 个变更文件同时含 CRLF 与 bare LF。

**修复边界：**

- 先修 `git diff --check` 明确报告的文件；
- 统一本次实际触及文件的换行，避免借机格式化未改动仓库；
- 每个提交切片使用 `git diff --cached --check`，最终使用
  `git diff --check <A-R3-base>..HEAD` 或等价范围门。

**验收：** 工作树门与每个 staged slice 的 diff check 均为零输出、exit 0。

### A-R3-MR-004 — `hermes_core/SOUL.md` 是运行产物，不得提交（P2）

该未跟踪文件创建于 2026-07-14 17:07，是 home 未隔离时生成的默认 SOUL 运行
状态，不是 A-R3 实现或 fixture；内容还带有机械改名后的不正确 lineage 文案。

**验收：** 从 A-R3 交付清单中排除；删除前只需保留本 review 的来源记录，不得
通过 `git add -A` 纳入任何切片。

### A-R3-MR-005 — 最终 legacy audit 与 Rust 门仍未取得（Gate）

- 本次 tracked-only audit：`15,628 hits / 0 defects`；当前 11 个未跟踪文件仍未被
  `git grep` 纳入，不能作为最终 Phase 2 证据；
- 本次 Rust filter test 超过五分钟未返回结果，审查者已终止仅由本次审查启动的
  4 个 Cargo 进程；本轮 Rust 结果记为 **not obtained**，不是 passed，也不是
  functional failure。

**验收：** 应交付文件进入目标切片、运行产物排除后重跑 audit；Rust 在不与
Python 全量、Web build 或 bundle 并行的独占门中重新运行并保留结果。

## 3. 已确认可保留的实现方向

以下内容在中场审查中没有发现需要推翻设计的问题：

- core `KABUQINA_HOME` 按 key presence 优先，缺少新 key 才读 `HERMES_HOME`；
- standalone 新目录优先，old-only 时读取旧目录而不复制/删除；
- Python 与 Rust desktop resolver 均为 old-only 原子 rename、失败回退旧目录、
  both-exist 新目录优先且旧目录保持不动；
- `state.db` / `learning.db` 文件名和 schema 未改变；
- keyring 实现方向为 canonical-first、legacy miss fallback、copy-forward、
  clear-both，问题在测试证据不足而非要求重写设计；
- `kabuqina-agent` distribution、自引用 extras、console aliases、`uv.lock`、bundle
  canonical 目录和 `.pth` 方向一致；
- 未发现生产 Python 代码继续通过 `hermes_cli` 或四个旧顶层模块访问实现；
- 599 个本次变更 Python 文件完成 AST 解析，无语法失败。

中场聚焦证据：

| 门 | 结果 | 说明 |
|---|---:|---|
| compatibility + config | 61 passed | 现有测试未覆盖 MR-001 的 legacy-first 双实例 |
| core home + state | 25 passed | `-n 0`、hermetic wrapper |
| desktop migration + timezone | 22 passed | Python unittest，单进程 |
| tracked legacy-name audit | 15,628 hits / 0 defects | 非最终，未覆盖 untracked |
| changed Python AST parse | 599 files / 0 failures | 只证明语法可解析 |
| Rust targeted | not obtained | 不得登记为通过 |

昨天记录的 core 全量 `1 failed / 15039 passed / 268 skipped` 仍可用于定位，但因
之后修改了测试契约且工作树尚未冻结，不能作为 V7 最终证据。

## 4. 给 A 轨 agent 的执行顺序

严格按以下顺序执行，不扩大命名范围：

1. 关闭 **MR-001**，先跑独立子进程 import-order 测试，再跑现有
   compatibility/config 聚焦组；
2. 关闭 **MR-002**，只跑 Rust keyring targeted tests；
3. 关闭 **MR-003 / MR-004**，逐个定性其余 untracked，修复 index 半成品状态；
4. 按 recovery plan 五个切片组织 index，但此时仍先不提交；
5. 应交付 shim / stub / audit 文件进入各自切片后，重跑最终 legacy audit；
6. 依次执行 V1 → V4 targeted → V3 → V5 → V6；前门失败不启动后门；
7. 代码和测试冻结后只运行一次 V7 全量，显式受控 worker，禁止 `-n auto`；
8. owner 完成 V8 专用数据/credential 升级轮后，才进入最终 review 和提交/推送。

建议 PowerShell 聚焦命令：

```powershell
$env:HERMES_TEST_WORKERS = '0'
& .\hermes_core\scripts\run_tests.ps1 `
  tests/kabuqina/test_compat_imports.py `
  tests/kabuqina_cli/test_config.py -q
Remove-Item Env:HERMES_TEST_WORKERS -ErrorAction SilentlyContinue

cd tauri
cargo test keyring_ -- --nocapture
cargo test host_home_ -- --nocapture
cd ..

python .\scripts\audit_a_r3_legacy_names.py
git diff --check HEAD
```

如再次发生蓝屏、内核错误或 Cargo/构建进程异常滞留，立即停止验证并报告，不把
强行重跑记为收口进展。

## 5. 复审入口条件

A 轨再次请求 review 前，应提供：

- MR-001 至 MR-005 的逐项关闭说明；
- 五个拟提交切片各自的文件清单与 staged diff 摘要；
- V0–V6 实际命令、结果和未执行原因；
- 最终 audit 分类数量；
- 当前 `git status --porcelain=v1`；
- 明确声明 V7 / V8 是否已执行，未执行不得写成通过。

本中场 review 没有修改 A-R3 运行时代码、测试实现或暂存区。
