# STUDY「数学与代码」练习系统设计（ACADEMY→REPORT 重组）

**日期：** 2026-07-05

**状态：** 已确认方向。结构性搬迁进 v0.3.0（雏形）;练习系统分两级落在
v0.4.0 / v0.5.0。

**范围：** ACADEMY 标签改名 REPORT;数学能力族迁入 STUDY 成为
「数学与代码」;定义符合学习产品原则的练习系统（五级梯子）、练习数据
契约、沙箱判分器与发布排期。不改 graph_engine（soak 冻结中）、不改
Writer/PPT 管线、不动 `capability_registry` 的既有条目。

**前置阅读：**
[immersive-learning-redesign.md](../../immersive-learning-redesign.md)（产品
原则与四铁律）、
[四层学习管线设计](2026-07-01-study-four-layer-learning-pipeline-design.md)
（artifact/activity/审核契约）、
[D 类数学表达工程化能力规格](2026-06-06-math-expression-engineering-capabilities-design.md)
（`math-expression-engineering` 能力族,本文重新安置其产品角色）、
[learning-runtime-alignment.md](../../learning-runtime-alignment.md)（LG4
条件边将消费本文的 attempt 结果）。

## 0. 决策与背景

当前 WorkspacePanel 的 ACADEMY 标签混装了两类东西：

1. 报告/PPT 发射台（论文/课程/代码/沙盘→PPT + 视觉母版）——**任务型**
   工作,属 Writer 轨,做得越顺手越好;
2. 数学能力区（公式清洗、公式→代码、代码→公式,D 类三件套）——被
   包装成"转换服务",即"帮你算/帮你转",是学习原则要否定的
   「代替」范式。

决策（2026-07-05,owner）：

- **ACADEMY → REPORT**：报告/PPT 部分改名,名实相符,继续作为任务型
  发射台,不受学习节奏契约约束（铁律一的任务豁免区）。
- **数学入 STUDY**,成为「数学与代码」区;其功能按本文的练习系统
  重塑。
- **v0.3.0 完成结构性搬迁**（改名 + 迁移 + prompt 对话化,纯前端/文案,
  soak 期安全）,作为后续两版的雏形;练习契约与判分器落 v0.4.0,
  完整梯子与交互大升级落 v0.5.0。

## 1. 组织原则：技能不是"记住"的,是"做 + 反馈"练出来的

闪卡/测验服务**陈述性知识**;数学与代码是**程序性技能**。技能模块的
组织原则：

```text
学习者产出 → 确定性验证 → 她只在卡住处搭脚手架
```

这个原则对数学与代码格外有利：两个领域的反馈**天然是确定性的、
近乎免费的**——代码判分 = 在打包 CPython 里跑测试;数学判分 = 数值/
符号等价检查。这是 "good quality, nearly free" 第一次应用于**判分**
而不只是生成：确定性判对错（免费）,模型只解释"为什么错"（付费,
且只在需要时）。

反面锚点：一个只输出解答的数学 solver 就是作业工厂。但铁律一不动摇
——直接索取照给,而且**每个直接给出的答案都是练习的种子**（见 §3）。

## 2. 五级梯子（责任渐释）

整体框架是一架梯子,I do → we do → you do → you teach：

| 级 | 学习者做什么 | 她做什么 | 校验方式 | 成本 |
|----|------------|---------|---------|------|
| ① 示范 | 看、问 | worked example,小步展示,每步 kq-kp 标注 | 无 | 模型（conduct 层现成） |
| ② 临摹 | 代码:逐行重打;数学:抄推导并**补每步"为什么成立"** | 给原文,收成果 | 代码:规范化文本/AST 匹配;数学:步骤理由由模型轻量点评 | 近零 |
| ③ 变式 | 解同结构换表面的题（换数字/变量名/边界） | 生成变式（模板变异优先,模型兜底） | 跑测试 / 数值等价 | 低 |
| ④ 独立 | 解新题,可请求 hint | hint 阶梯（练习场景,hint-first 合规） | 跑测试 / 数值等价 | 中 |
| ⑤ 讲解 | 把代码/推导讲回来（费曼） | 追问漏洞,产出 weak-point 证据 | 模型评估 → evaluation 草稿 | 模型 |

- 用户此前设想的「代码临摹」= 第②级,不是孤立功能,是梯子的一环。
- ②③可以完全确定性地跑起来,是 v0.4.0 的先行两级;④⑤依赖 hint
  阶梯与评估语义,归 v0.5.0（并与 tutor loop / LG4 汇合:advance/
  remediate 条件边的输入正是 attempt 结果）。
- 梯子不强制线性:学习者可从任一级进入,她按 attempt 证据建议升降级。

## 3. D 类三件套的重新安置

| 能力 | 旧角色 | 新角色 |
|------|-------|--------|
| `math-expression-cleanup` | 转换服务 | **READ 层输入服务**:清洗 OCR/文档公式,喂课程知识库(知识点携带规范 LaTeX);不算教学功能 |
| `math-formula-to-code` | 转换服务 | **桥练习生成器** + 按需服务:"实现这个公式"是③④级的王牌题型 |
| `code-to-math-formula` | 转换服务 | **桥练习生成器** + 按需服务:"读这段代码,写出公式" |

公式↔代码双向转换是数学与代码合并成一个模块的产品理由:**同一知识点
的两种表征**。能力族 id `math-expression-engineering` 与三个 capability
id 保持不变（registry 不动,candidate 状态不变——D 类规格的升级规则
本文照旧:有可执行 pipeline + 验收测试才升 available,而 §5 的判分器
恰好将提供这个 pipeline,预计随 v0.4.0 达成升级条件）。

**answer-then-teach 的转化机制：** 用户直接要求"把这个公式转成代码"
时,完整给出（铁律一）,随后附 kq-kp 知识点,并提供一个动作:
"要不要来道变式?"——由刚解出的内容确定性地生成②/③级练习。直接
答案从终点变成练习入口,这是本模块与作业工厂的分界线。

## 4. 练习数据契约（v0.4.0,落 `learning_contract.py`）

**原则:不发明新 kind,扩展 `quiz` 的判别联合**——继承 M3 的全部
语义:题目是 artifact（draft→active 审核）、作答是 activity
（`quiz.attempt`）、重出题不覆盖历史成绩、owner/space 隔离。

新增两个题型（per-kind schema 演进,版本化）：

```json
{
  "type": "code",
  "prompt": "实现 sigmoid 函数",
  "language": "python",
  "mode": "solve | transcribe | variant",
  "starter": "def sigmoid(x):\n    ...",
  "target_code": "（mode=transcribe 时:要临摹的原文）",
  "test_code": "assert abs(sigmoid(0) - 0.5) < 1e-9\n...",
  "reference": "参考实现（不下发前端,判分与讲解用）",
  "variant_of": "可选:源题/源答案的 item 引用",
  "tags": ["激活函数"]
}
```

```json
{
  "type": "derivation",
  "prompt": "从定义推出方差的展开式",
  "steps": [
    {"expr": "\\operatorname{Var}(X)=E[(X-E[X])^2]", "justification": "定义"},
    {"expr": "=E[X^2]-E[X]^2", "justification": "展开并用线性性"}
  ],
  "check": "numeric-equivalence",
  "cloze": [1],
  "tags": ["方差"]
}
```

- `mode` 区分梯级:`transcribe`（②,判分=规范化匹配）、`variant`（③,
  记录 `variant_of` 保持谱系,喂 Learning Index 的薄弱点归因）、
  `solve`（③④通用）。
- `derivation.cloze` 指定哪些步骤挖空让学习者补;`justification` 挖空
  即"临摹补理由"形态。
- 判分结果进 `quiz.attempt` activity,附 `detail={"mode": ..., "passed":
  ..., "failures": [...]}`;M4 的 weak_points 投影无需改动即可消费。
- 尺寸上限沿用 contract 常量;`test_code`/`reference` 计入
  `MAX_ENVELOPE_BYTES`。

## 5. 沙箱判分器（v0.4.0 唯一的新 core 能力,需单独安全评审）

代码判分 = 在**打包 CPython** 里执行 `starter+学习者代码+test_code`。
被执行代码的作者是学习者本人或我们的模型（经 draft 审核）,但判分在
无人审批下自动运行,必须有独立于信任假设的边界：

- 子进程 + `python -I`（隔离模式:不继承 env/site/当前目录）;
- 临时工作目录,判分后整目录删除;不授予 workspace 路径;
- 硬超时（默认 5s,contract 可调上限 30s）、stdout/stderr 截断
  （64KB）、进程树强杀;
- 禁止网络:v1 记录为**已知残余风险**（Windows 无进程级断网原语;
  Job Object 限不了网络）。缓解路径按序评估:出站防火墙规则（随
  安装器）、受限执行环境（wasm/pyodide）——先记录,不阻塞 v1;
- 判分器只返回 pass/fail + 失败摘要,原始输出不直接进模型上下文
  （防 prompt injection from 输出）。

数学等价检查分两档：

1. **基线（v0.4.0,零新依赖）:数值采样等价**——两个表达式在随机
   采样点上求值比对(打包 CPython 即可,复用同一沙箱);
2. **升级（可选）:sympy 符号等价**——需先确认 sympy 是否已在
   bundle;不在则按 EasyOCR 先例做 load-package,不进 MSI。

## 6. 交互演进

### v0.3.0 —— 结构性搬迁（雏形,soak 期安全:纯前端 + prompt 层）

1. `WorkspacePanel.tsx`:标签 `academy` → `report`（mode id、
   `workspace.reportPpt` 保留原 sectionId 以免用户折叠偏好丢失;顶栏
   label 换 i18n 新 key）;PPT 发射台与视觉母版**原样保留**在 REPORT。
2. 数学能力区整体迁入 STUDY 标签,section 标题「数学与代码」
   （`chat.workspaceMathCode`）,目标语言选择器保留。
3. 三个数学 prompt 对话化改写,与七个 STUDY 动作同一契约（一次一问、
   小步交付、防编造、no-emoji）,并植入 §3 的转化钩子:转换完成后附
   知识点、提议变式练习（此时"变式"还只是对话行为,不落库——契约
   是 v0.4.0 的事,雏形先把**话术和位置**放对）。
4. locales 双语、`chatUx.test.mjs` / workspace 相关断言同步;
   DECISIONS.md 记录本决策。
5. 明确不做:不动 capability registry、不加任何后端路由、不改约
   Writer/PPT 管线。

### v0.4.0 —— 契约 + 判分器 + 梯子②③

- §4 题型进 contract + `QuizService` 判分扩展（code/derivation 分派到
  沙箱判分器）;
- 临摹/变式生成:变式优先确定性模板变异,模型兜底;
- UI 复用 QuizPanel 形态(最小改动),practice 入口挂在「数学与代码」区;
- D 类两个转换能力凭判分 pipeline + 验收测试升 available。

### v0.5.0 —— 梯子④⑤ + 交互大升级

- hint 阶梯、讲解/费曼评估(→ evaluation 草稿);
- 梯子成为 tutor loop 图的实例(LG4 条件边吃 attempt 结果,LG1/LG2
  语义此时应已随 soak 结束定型);
- B3 学习空间:编辑器/推导板占据主舞台,她退到旁注栏。

## 7. 里程碑与既有轨道的关系

| 版本 | 本文内容 | 依赖/约束 |
|------|---------|----------|
| v0.3.0 | §6.1 结构搬迁 | soak 冻结引擎——本部分纯前端/prompt,安全;随 H1/H6/H5 同一轮 review/test |
| v0.4.0 | §4 契约 + §5 判分器 + 梯②③ | M4（student_state/evaluation）预计同期或先行;判分器需安全评审 |
| v0.5.0 | 梯④⑤ + B3/tutor loop | soak 结束、G2 门开、LG1/LG2 契约定型 |

## 8. 明确不做

- 不承诺通用解题器、证明生成、完整 CAS（沿袭 D 类规格的暂不做清单;
  `math-code-roundtrip-check` 仍暂缓——§5 的等价检查是判分内部件,
  不作为用户能力暴露）。
- 不给模型工具判分豁免:判分器是受信 core 服务,模型不能给自己的
  草稿题判"通过"。
- 不在 v0.3.0 加任何后端;雏形只动位置和话术。
- 不把 REPORT 里的 PPT 流程学习化——任务型工作保持高效,是铁律一
  的豁免区,也是产品的另一半价值。

## 9. 风险

1. **沙箱是安全面**:残余网络风险要在 DECISIONS 显式记录,发布说明
   不得声称"完全隔离"。
2. **变式质量**:模板变异生成的题可能退化(换数字导致平凡解);
   生成器需带自检(变式必须仍能被 test_code/等价检查判分)。
3. **梯子变成流水线的诱惑**:五级是脚手架不是关卡,学习者可跳级;
   UI 不做强制线性闯关,否则违反"不喧宾夺主"。
4. **v0.3.0 搬迁的回归面**:WorkspacePanel 的 mode 持久化、折叠偏好、
   onboarding 引用 ACADEMY 文案的地方需全量 grep(含 locales 两语言)。
