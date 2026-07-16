# A-R3 恢复与收口计划

> **性质：** 本文不是动工前实施设计，而是 A-R3 已经展开后的恢复、审计与
> 收口计划。原始目标和兼容契约仍以
> `2026-07-14-a-r3-core-persistence-rename-plan.md` 为准；本文负责把当前大型
> 未提交工作树安全地变成可审查、可验证、可回退的提交和验收证据。

## 1. 为什么现在补计划

A-R3 在专门实施计划获确认前已经开始，随后才补写了目标、兼容面和 Task
1–6。当前问题已经不只是“还要改哪些名字”，而是：

1. 如何证明 721 个工作树条目没有把兼容迁移变成机械误改；
2. 如何把暂存、未暂存和未跟踪文件恢复成完整的逻辑提交；
3. 如何避免为同一个问题反复跑全量测试；
4. 如何证明旧 home、数据库和 Credential Manager 内容不会丢失；
5. 如何让复审者能够按切片判断，而不是面对一个不可解释的大提交。

因此，从本文生效起，A-R3 进入 **freeze-and-close**：除修复审计或验证发现的
明确缺陷外，不再扩大命名范围，不引入新功能，不顺手清理与 A-R3 无关的旧
代码。

## 2. 恢复基线（2026-07-14）

### 2.1 Git 状态

- 分支：`main`
- 基线提交：`8f80f96b`，与 `origin/main` 一致
- 工作树条目：721
  - 603 个未暂存修改
  - 103 个“已暂存 rename、rename 后内容仍有未暂存修改”
  - 4 个已暂存纯 rename
  - 11 个未跟踪文件
- 目录分布：
  - `hermes_core/`：639
  - `python/`：47
  - `tauri/`：14
  - `docs/`：9
  - `web/`：6
  - `scripts/`：4
  - 根目录：`AGENTS.md`、`DECISIONS.md`
- 当前暂存区只表达 107 个纯 rename，**不代表完整可提交切片**；不得直接提交。

11 个未跟踪文件必须逐个定性，不能被 `git add -A` 模糊带过：

- A-R3 两份计划文件；
- `SOUL.md`；
- `hermes_cli` 和四个 `hermes_*` 一周期兼容 shim；
- Google Workspace `_hermes_home.py` 兼容 shim；
- 两个 gateway xdist 测试 stub；
- legacy-name 审计脚本。

### 2.2 已有验证证据

- 最近一次 core 全量：
  `1 failed, 15039 passed, 268 skipped, 13766 warnings in 1720.33s`。
- 唯一失败为 canonical module reload 后仍要求旧函数对象保持 `is` identity 的
  测试契约；契约已改为验证旧 API 可调用且行为与 canonical API 一致。
- 修复后单文件：`17 passed, 17 warnings`。
- 修复后 reload 顺序组合（单进程）：`31 passed, 31 warnings`。
- 修复后同一组合（xdist，显式 `-n 2`）：
  `31 passed, 31 warnings in 40.22s`。
- 当前 legacy-name 审计对 **tracked 文件**分类 15,602 个命中，零 defect；
  但未跟踪文件未被 `git grep` 纳入，所以这不是最终证据。

这些结果可以作为定位和回归证据，但不能代替工作树冻结后的最终门。

### 2.3 机器稳定性约束

仓库 `pyproject.toml` 默认 `pytest -n auto`。本轮曾在并行测试期间发生 Windows
`IRQL_NOT_LESS_OR_EQUAL (0xA)` 蓝屏；pytest 负载可能是触发条件，即使内核崩溃
根因仍需由转储分析确认。

从现在起：

- 禁止使用隐式 `-n auto`；所有 pytest 命令必须显式写 `-n 0` 或 `-n 2`；
- 聚焦测试默认 `-n 0`，只有需要证明 xdist 契约时使用 `-n 2`；
- core 全量只在代码冻结后运行一次，使用显式受控 worker；
- 不并行运行 core 全量、bundle 构建、Rust 编译或 Web build；
- 机器再次出现系统级异常时立即停止验证，不把强行重跑视为收口进展。

### 2.4 中场复审增量（2026-07-15）

中场复审结论与给 A 轨 agent 的完整指令见
`docs/reviews/2026-07-15-a-r3-midterm-review.md`。当前 HEAD 为
`dce4159a`，两份 plan 已提交；实现仍全部位于工作树。中场审查开始时的
porcelain 快照仍为 721 条，构成为：

- `604` 个 ` M`；
- `103` 个 `RM`；
- `4` 个 `R `；
- `10` 个 `??`。

本次 handoff 随后新增 1 个 review 文档并修改这 2 个 plan；因此交给 A 轨 agent
时的预期状态为 `606 M / 103 RM / 4 R / 11 ??`，合计 724 条。新增 3 条均属于
guidance/review 切片，不是新增运行时实现。

复审登记五项：

1. `A-R3-MR-001`（P1）：顶层 `hermes_cli` alias 不会自动统一
   `hermes_cli.<submodule>`；已复现 `auth` / `config` 双模块和双 registry/cache；
2. `A-R3-MR-002`（P2）：keyring copy-forward 成功/失败与 clear-both 缺少控制流
   单测；
3. `A-R3-MR-003`（P2）：`git diff --check` 因
   `docs/troubleshooting.md` 的 36 个换行/空白问题失败；
4. `A-R3-MR-004`（P2）：`hermes_core/SOUL.md` 已确认为 2026-07-14 生成的运行
   产物，不得提交；
5. `A-R3-MR-005`（Gate）：tracked-only audit 与 Rust targeted 都还不是最终证据。

中场新增证据：compatibility/config `61 passed`；core home/state `25 passed`；
desktop migration/timezone `22 passed`；599 个变更 Python 文件 AST parse 零失败；
tracked-only audit `15,628 hits / 0 defects`。Rust filter test 本轮未取得结果，必须
登记为 `not obtained`，不得写成 passed。

## 3. 收口原则

1. **数据安全优先于改名完整度。** 新名不能以删除旧目录、覆盖旧库或清空旧
   凭据为代价。
2. **新值按 key 是否存在优先。** 不能用 truthiness 判断是否回退到旧值。
3. **canonical 路径必须独立成立。** bundle 和正常运行不得依赖旧 shim 才能
   导入。
4. **兼容只留在明确接缝。** 旧 import、命令、env、目录和 keyring service
   保留一个发布周期；内部新代码不得继续新增旧入口依赖。
5. **不机械消灭所有 Hermes 字样。** Nous Hermes 模型、协议/parser、上游和
   法律历史、`hermes_core/` 源码边界必须保留并分类。
6. **不操作真实用户数据做自动化测试。** home 和数据库迁移使用临时目录与
   人工构造的 populated samples；keyring 使用 mock 或专用测试条目。
7. **一次门只证明一个层次。** 聚焦门失败先局部修复，不立即重启全量。

## 4. 执行阶段

### Phase 0 — 冻结和恢复清单

- [x] 记录 `git status --porcelain=v1`、已暂存 diff、未暂存 diff 和未跟踪清单。
- [x] 逐个确认 11 个未跟踪文件的来源、用途和目标提交；删除或忽略任何临时
      运行产物前必须先确认不是实现文件。
- [x] `hermes_core/SOUL.md` 已由中场复审确认为运行产物；从交付清单中排除，
      不得被后续 `git add -A` 纳入切片。
- [x] 确认 `python/dist/`、`tauri/target/`、测试缓存、日志和 dump 不进入提交。
- [x] 最终 index 同时包含 rename 和 rename 后的实际内容；owner 选择以一个
      consolidated implementation commit 落地，未保留原计划的五提交切片。
- [x] 生成“变更所有权表”：core namespace、persistence/keyring、bundle、
      guidance/audit、测试辅助五类；交叉文件标记主要职责。

**出口：** 暂存区不再是半成品 rename；每个文件都有目标切片，未跟踪文件为
零或全部有明确去向。

### Phase 1 — 四个高风险面语义审计

#### 1A. Home 与数据库

- [x] `KABUQINA_HOME` 按 key presence 优先，包括显式空值的约定。
- [x] 缺少新 key 时才读取 `HERMES_HOME`。
- [x] standalone：新目录优先；仅旧目录存在时读旧目录，不复制、不删除。
- [x] desktop：old-only 原子 rename；rename 失败继续使用旧目录；both-exist
      新目录优先且不触碰旧目录。
- [x] `state.db`、`learning.db` 名称和 schema 不变；populated sample 迁移后可读。
- [x] web child、gateway child、cron runner 和 Rust shell 使用同一 Rust-selected
      host root；第二轮 follow-up 通过 `SpawnConfig` / child env 显式传播，Python
      entrypoint 与 QR worker 不再独立迁移。

#### 1B. Credential Manager

- [x] service `Kabuqina` 首选；只有明确 miss 才读 `HermesDesk`。
- [x] 旧值恢复后 copy-forward；复制失败不丢失本次读到的旧值。
- [x] 显式 clear 同时清理新旧 service；follow-up 修复聚合非 `NoEntry` 删除错误，
      失败时保留 provider 配置供重试。
- [x] 新值为 false/空等合法值时不得错误回退。
- [x] 日志仅记录迁移事件，不包含明文 secret。
- [x] 使用可注入 seam 或等价纯 helper 单测 copy-forward 成功、写入失败仍返回
      legacy secret、clear 对两个 service 均发出删除；不得触碰用户真实凭据。

#### 1C. Python namespace 与命令

- [x] `kabuqina_cli` 和四个 `kabuqina_*` 模块是实现主体。
- [x] `hermes_cli.<submodule>` 与四个旧模块通过薄 shim 保持一周期兼容。
- [x] legacy-first 与 canonical-first 两种正常 import 顺序下，代表性 stateful
      子模块（至少 `config` / `config_home` / `auth`）不得被加载为两份模块或
      产生两套 registry/cache；使用独立子进程测试，避免收集顺序遮蔽缺陷。
- [x] canonical 与旧入口的行为一致；测试不要求 reload 后函数对象永久保持
      identity。
- [x] distribution 为 `kabuqina-agent`；canonical console scripts 存在；旧命令
      只是 alias。
- [x] 内部产品代码不再通过旧 shim 访问 canonical 实现。

#### 1D. Bundle 与运行时

- [x] build/sync 脚本复制 canonical package、模块和必要兼容 shim。
- [x] `.pth`、manifest、prune verifier 和 smoke import 使用 canonical 名称。
- [x] embedded runtime 在临时隔离环境中直接 import canonical 模块。
- [x] 旧 import smoke 单独证明兼容且共享 canonical runtime state，不得只证明
      “能 import”，也不得成为 canonical smoke 的前置条件。

**出口：** 每一项都有实现位置、测试位置和结果；发现的问题只做最小修复。

### Phase 2 — Legacy-name 最终分类

- [x] 先把应提交的 shim、计划和审计脚本纳入 Git，再运行审计。
- [x] 审计覆盖 tracked 文件且零 `defect` / `packaging-defect`。
- [x] 中场预扫 `15,628 hits / 0 defects` 只算定位证据；11 个当前 untracked 完成
      定性、应交付文件进入 Git、运行产物排除后必须重新生成最终计数。
- [x] 随机抽查每个大类，防止通过不断扩大 allowlist 隐藏真实缺陷。
- [x] 对 active docs、skills、安装命令、环境变量和 bundle 路径做额外人工抽查。
- [x] 保留的命中必须属于：兼容接缝、上游/法律/历史、模型/协议、测试 fixture
      或 `hermes_core/` 源码边界。

**出口：** 最终命中数量、分类数量和零 defect 结果写入验收证据。

### Phase 3 — 可审查提交切片

进入本阶段前必须关闭中场 review 的 `A-R3-MR-001` 至 `A-R3-MR-005`；不得用
“先提交再补证据”绕过该入口门。

建议切片如下；若依赖关系迫使合并或调序，必须在计划结果区说明原因，不能
静默变成一个大提交。

1. **Canonical namespace foundation**
   - canonical package/modules、旧 shim、console aliases、最小 import 测试；
   - 确保新旧入口均可导入。
2. **Core internal migration**
   - core 内部 imports、类/函数命名、测试目录和大规模机械引用迁移；
   - 将 600+ core 文件的机械改动与持久化语义隔离审查。
3. **Desktop persistence and credentials**
   - Python/Rust home resolver、目录迁移、keyring 迁移及对应测试；
   - Web 只包含确有必要的用户可见路径/提示同步。
4. **Distribution and embedded runtime**
   - pyproject/package metadata、bundle/sync/prune/import verifier。
5. **Guidance, audit, and close evidence**
   - active docs、AGENTS、DECISIONS、审计脚本、两份计划及最终结果。

实际落地为 owner 选择的单个 consolidated implementation commit `5abea97c`；以下
检查按该最终 index 执行，未倒填成不存在的五个 commit：

- [x] ownership manifest 覆盖五类变更，最终 consolidated index 无运行产物；
- [x] `git diff --cached --check` 通过；
- [x] 运行各 ownership 类别对应的聚焦测试与 V0–V7；
- [x] commit message 描述迁移与凭据清理语义，而非只写“rename”。

### Phase 4 — 验证矩阵

按成本从低到高执行；前一层失败时不启动后一层。

| 门 | 内容 | 并发约束 | 证据 |
|---|---|---|---|
| V0 | `git diff --check`、最终 legacy scan | 单进程 | 命令与分类摘要 |
| V1 | canonical/legacy import（含双顺序 stateful submodule）、home、DB、keyring 聚焦测试 | pytest `-n 0` | 每组 passed/failed |
| V2 | xdist reload/identity 组合 | pytest `-n 2`，只跑已定义组合 | 已有 `31 passed`，冻结后确认一次 |
| V3 | Python desktop unittest | 单进程 | 汇总与失败明细 |
| V4 | Rust targeted tests、`cargo test`、`cargo check` | 不与其他构建并行 | 汇总 |
| V5 | Web tests/lint/build | 不与 Rust/bundle 并行 | 汇总 |
| V6 | bundle `-Verify`、canonical runtime smoke、legacy smoke | 单独运行 | manifest/import 结果 |
| V7 | core 最终全量 | 显式受控 worker，禁止 `-n auto` | 完整汇总 |
| V8 | owner 手工升级轮 | 测试目录/备份数据，不直接冒险操作唯一真实副本 | checklist/截图 |

V7 只能在所有实现和测试文件冻结后运行一次。若只修改结果文档，无需重跑；若
修改运行时代码或测试契约，按影响面先回退到对应聚焦门，再决定是否使 V7 失效。

### Phase 5 — 手工升级与发布边界

自动化不能单独证明 Windows 安装升级路径。最终手工轮由 owner 执行，Codex
准备步骤和核对表：

- [x] 使用备份或专用测试 data dir 构造 only-old `hermes-home`，其中包含可识别
      的 `state.db`、`learning.db` 和普通配置文件。
- [x] 安装/启动新版本后确认迁移到 `kabuqina-home`，数据库记录仍可读取。
- [x] both-exist 场景确认新目录获胜、旧目录未删除。
- [x] 模拟 rename 失败，确认应用回退旧目录而不是创建空白新家。
- [x] 使用专用测试 credential 验证 legacy read、copy-forward 和 clear-both。
- [x] 确认新安装路径只使用 canonical imports/commands。

真实用户 home 和真实 API key 在测试前必须备份；日志与截图不得包含 secret。

### Phase 6 — 记录、复审与完成

- [x] 回填原 A-R3 实施计划 Task 1–6 的真实状态，不倒填未发生的 TDD 过程。
- [x] 在本文末尾记录每个阶段的提交 hash、验证命令和结果。
- [x] 生成 A-R3 review 文档，突出 persistence/keyring/compatibility 三个高风险面。
- [x] 逐项关闭中场 review `A-R3-MR-001` 至 `A-R3-MR-005`，并在 review 文档或
      执行记录中写明提交、测试和证据。
- [x] 将本轮 CHANGES REQUESTED follow-up 形成 owner-approved commit `cbfbdceb`，并
      确认工作树干净。
- [x] 最终独立复审确认 **A-R3 PASS**，将 A-R3 本地 slice 标记完成。
- [ ] 推送 `main`（独立的仓库同步动作，仍待 owner 明确授权）。

## 5. 停止条件

出现以下任一情况，停止扩展修复并先报告：

1. 任何测试或手工轮可能删除、覆盖真实用户 home、数据库或 credential；
2. 新旧目录同时存在时出现自动合并或删除旧目录；
3. canonical runtime 只能依靠旧 shim 才能启动；
4. legacy scan 出现无法合理分类的 active-code 命中；
5. 聚焦修复扩散到与 A-R3 无关的业务语义；
6. 再次发生蓝屏、内核错误或明显系统不稳定；
7. 为让测试变绿而放宽数据安全或兼容契约。

## 6. 完成定义

A-R3 只有同时满足以下条件才算完成：

- canonical namespace、home、distribution、commands 和 keyring service 均为新名；
- 一发布周期的旧入口明确、薄且有测试，不被内部新代码依赖；
- old-only、both-exist、migration-failure、populated DB、new-value-wins 和
  clear-both 契约全部有证据；
- tracked legacy-name 扫描零 defect；
- Python、Rust、Web、bundle、core 全量和 owner 手工升级轮达到各自门槛；
- 变更被拆成可审查提交，原实施计划和本文均回填真实结果；
- 复审通过，工作树干净，随后才提交/推送最终收口。

## 7. 执行记录

> 本节只记录实际发生的结果；不得把计划项预先写成完成。

| 阶段 | 状态 | 提交/证据 | 备注 |
|---|---|---|---|
| Phase 0 冻结与清单 | complete | freeze snapshot：725 staged，0 unstaged，0 untracked | 运行产物排除；最终 index 完整 |
| Phase 1 高风险语义审计 | complete | freeze review MR-001–005；两轮 P1/P2 follow-up | home 跨进程显式传播；clear 错误可见；session header 统一 |
| Phase 2 legacy 分类 | complete | `15,830` tracked hits，0 defects | 最终分类以本轮审计为准 |
| Phase 3 提交落地 | complete with deviation | `5abea97c` | owner 选择 consolidated commit，未保留计划的五提交切片 |
| Phase 4 自动验证 | complete | V0–V7；follow-up Python 15、gateway 6、Rust home 3、Rust secrets 21、Rust child env 1 passed | V7 全量 15,355 passed；运行时代码 follow-up 已按影响面聚焦回归 |
| Phase 5 owner 手工轮 | complete | V8：`.test-output/a-r3-v8/V8-RESULT.md` | NSIS 安装态、home、credential、clear-both 均通过 |
| Phase 6 复审与完成 | complete (local) | `4895a7b4` + `cbfbdceb` + owner A-R3 PASS | 本地 slice 已关闭、工作树干净；仅剩 owner 授权后 push `main` |
