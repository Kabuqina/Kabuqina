# D 类数学表达工程化产品能力规格

## Summary

本规格定义学生主场景下的 `math-expression-engineering` 能力族。目标不是通用解题、证明或完整 CAS，而是把数学表达、代码表达、报告表达之间的转换做成可开发、可验收、可挂接 pipeline 的产品能力。

本轮只产出规格，不实现代码，不写入 `capability_registry.py`。这些能力先作为 candidate capability 进入产品规划；只有后续具备可执行 tool/pipeline、可观测状态和验收测试后，才升级为 available capability。

## Capability Family

Capability family: `math-expression-engineering`

用户承诺：

- 把公式、LaTeX、文档公式转成可读代码或竞赛代码。
- 把 Python、NumPy、C++17 代码转成数学公式、LaTeX 和报告。
- 把 OCR、文档、代码里混乱的数学表达整理成规范表达。

学生场景优先于通用办公场景。第一版服务于课程作业、实验报告、竞赛题面理解、算法说明、论文/报告公式整理等任务。

## Scope

第一批产品能力：

| Capability | Product Role | Status |
| --- | --- | --- |
| `math-expression-cleanup` | 混乱公式/OCR/代码表达式 -> 规范数学表达 | candidate |
| `math-formula-to-code` | 公式/LaTeX/文档公式 -> Python/NumPy/C++17 代码 | candidate |
| `code-to-math-formula` | 代码 -> 数学公式/LaTeX/Markdown/HTML/PDF 报告 | candidate |

暂不做：

- `math-code-roundtrip-check`
- 解题生成
- 证明生成
- 完整 CAS 等价变换
- 以 LaTeX/Typst 作为第一版 PDF 主链路

## Relationship With `document-math`

`document-math` 保持为上游 Reader 能力，职责是从 PDF、PPT、DOCX、图片等输入中提取公式、符号、上下文和位置线索。

`math-expression-engineering` 是下游表达工程能力，职责是规范化、转换、生成代码或报告。

区别：

| Capability | Layer | Responsibility |
| --- | --- | --- |
| `document-math` | Reader | 提取文档里的数学内容。重点是找到、识别、保留来源。 |
| `math-expression-cleanup` | Writer-oriented transform | 规范化混乱公式。重点是清理 LaTeX、补齐变量表、报告歧义。 |
| `math-formula-to-code` | Planner + Writer | 把公式语义映射到目标语言代码。 |
| `code-to-math-formula` | Reader + Planner + Writer | 把代码结构映射回公式、解释和报告。 |

因此，PDF 读取不是这些新能力的边界。PDF、PPT、图片、Markdown 都可以通过 Reader 进入同一套数学表达工程 pipeline。

## Language Target Policy

目标语言固定为第一版三类：

| Target | Policy |
| --- | --- |
| Python | 标量/函数式代码，优先可读性。可使用标准库 `math`。 |
| NumPy | 数组、矩阵、向量化表达。必须能表达向量/矩阵输入，不退化成只有标量代码。 |
| C++17 | 面向竞赛可用性，只依赖 C++17 标准库，不依赖 Eigen、Boost 或其他第三方库。 |

语言选择默认面向大学生：课程和实验报告优先 Python/NumPy，算法竞赛和笔试场景优先 C++17。

## Capability: `math-expression-cleanup`

Product promise: 将 OCR、文档提取或代码片段中的混乱数学表达整理成可读、可引用、可继续转换的规范数学表达。

Inputs:

- OCR 公式文本
- 混乱或不完整 LaTeX
- `document-math` 输出
- 文档公式片段
- 代码表达式

Pipeline:

```text
reader -> material_index -> writer
```

Stage contract:

| Stage | Role |
| --- | --- |
| reader | 接收文本、文档提取结果、图片/OCR 结果或代码表达式。 |
| material_index | 建立公式片段、变量、来源位置、上下文句子的索引。 |
| writer | 输出规范 LaTeX、Markdown 说明、变量表和歧义警告。 |

Outputs:

```json
{
  "clean_latex": "string",
  "markdown": "string",
  "variable_table": [],
  "warnings": []
}
```

Quality rules:

- 不伪装成证明正确性校验。
- 遇到变量含义不明、上下标歧义、函数/变量冲突时输出 `warnings`。
- 可作为 `document-math` 下游能力，也可独立出现在能力页。

## Capability: `math-formula-to-code`

Product promise: 将公式、LaTeX 或文档中提取出的数学表达转成学生可直接理解和改写的 Python、NumPy 或 C++17 代码。

Inputs:

- LaTeX
- Markdown 公式
- `document-math` 输出
- 图片/文档中提取出的公式

Pipeline:

```text
reader -> material_index -> planner -> writer
```

Stage contract:

| Stage | Role |
| --- | --- |
| reader | 接收公式文本、文档公式提取结果或图片/OCR 提取结果。 |
| material_index | 建立公式、变量、常量、维度、上下文说明的索引。 |
| planner | 判断目标语言、数据形态、变量类型、标量/向量/矩阵语义和必要假设。 |
| writer | 生成目标语言代码、变量表、假设和示例输入。 |

Writer targets:

- `python`
- `numpy`
- `cpp17`

Outputs:

```json
{
  "code": "string",
  "language": "python | numpy | cpp17",
  "variable_table": [],
  "assumptions": [],
  "example_inputs": []
}
```

Quality rules:

- Python 输出优先可读性，默认函数式组织。
- NumPy 输出必须能表达数组、矩阵、广播或向量化语义。
- C++17 输出必须只依赖标准库。
- 对无法从公式判断的数据类型、单位、维度时，必须写入 `assumptions`。

Example acceptance anchor:

公式 `E = mc^2` 至少应能定义为：

- Python 标量函数。
- NumPy 可接受数组或标量输入的表达。
- C++17 标准库函数或简单表达式。

## Capability: `code-to-math-formula`

Product promise: 将 Python、NumPy 或 C++17 代码片段转换成数学公式、LaTeX、Markdown 解释报告，并可从同一份 HTML 报告导出 PDF。

Inputs:

- Python 代码片段或文件
- NumPy 代码片段或文件
- C++17 代码片段或文件

Pipeline:

```text
reader -> material_index -> planner -> writer
```

Stage contract:

| Stage | Role |
| --- | --- |
| reader | 读取代码片段或文件，识别语言、函数、变量、循环、数组表达。 |
| material_index | 建立代码符号、表达式、控制流片段、变量来源和注释索引。 |
| planner | 判断哪些代码结构可映射为公式，哪些应保留为算法说明或警告。 |
| writer | 生成公式、LaTeX、Markdown、HTML 报告，并由 HTML 导出 PDF。 |

Outputs:

```json
{
  "formulas": [],
  "latex": "string",
  "markdown": "string",
  "html_path": "string",
  "pdf_path": "string",
  "variable_table": []
}
```

PDF decision:

- HTML 是主报告中间产物。
- PDF 是 Writer 导出目标，不单独定义为产品能力。
- `pdf_path` 必须来自同一份 `html_path` 的渲染导出。
- 第一版不引入 LaTeX 或 Typst 作为主链路；后续可以作为可选 Writer backend 评估。

Quality rules:

- Python/NumPy/C++17 代码都必须能定义为转换到 LaTeX + Markdown 解释报告。
- 代码中的副作用、I/O、随机数、复杂状态更新不应被强行伪装成闭式公式。
- NumPy 数组表达要保留向量/矩阵语义。
- C++ 循环可在必要时表达为求和、递推或算法步骤，但不能承诺数学等价证明。

## Candidate To Available Rule

这些 capability 在规格阶段状态为 candidate。

升级为 available 必须满足：

1. 至少有一个可执行 pipeline。
2. Pipeline 明确覆盖 Reader / Material Index / Planner / Writer 中声明的阶段。
3. Runtime 能解释状态：available、partial、missing_package、disabled_toolset 或 unsupported_input。
4. Agent prompt 能给出具体 pipeline 调用方式，而不只是泛泛提示。
5. 有面向验收场景的自动化测试或 smoke test。

在满足以上条件之前，不应写入用户可见的 available capability，也不应在前端快捷入口中承诺完整可用。

## Frontend Shortcut Notes

后续具体能力实现时，可以考虑前端快捷方式，但本规格不实现 UI。

候选入口：

| Capability | Shortcut Candidate |
| --- | --- |
| `math-expression-cleanup` | 附件/选中文档公式后的清理按钮；能力页独立入口。 |
| `math-formula-to-code` | 选中公式后出现“转代码”快捷操作。 |
| `code-to-math-formula` | 选中代码块或代码文件后出现“转公式/报告”快捷操作。 |

快捷入口必须绑定具体 pipeline，不能只绑定 capability family。

## Implementation Order

后续开发优先顺序：

1. `math-expression-cleanup`
2. `math-formula-to-code`
3. `code-to-math-formula`
4. HTML -> PDF 导出

理由：先把公式规范化做好，才能让代码转换和报告生成有稳定输入；PDF 应作为 HTML 报告链路稳定后的 Writer 导出目标。

## Test And Acceptance Criteria

规格和后续实现应覆盖：

- 公式 `E = mc^2` 可被定义为 Python、NumPy、C++17 三种目标输出。
- NumPy 目标能表达向量/矩阵输入，而不是只生成标量代码。
- C++17 目标不依赖第三方库。
- Python、NumPy、C++17 代码片段能被定义为转换到 LaTeX + Markdown 解释报告。
- `code-to-math-formula` 的 PDF 输出必须来自同一份 HTML 报告。
- `math-expression-cleanup` 能说明它与 `document-math` 的区别：提取 vs 规范化。
- Candidate capability 不会在缺少可执行 pipeline 时被标记为 available。

## Assumptions

- 学生场景优先于通用办公场景。
- 第一版不追求完整 CAS 能力。
- 第一版不承诺证明转换正确性。
- C++ 第一版面向竞赛可用性，默认 C++17 标准库。
- PDF 第一版走 HTML -> PDF，不引入 LaTeX/Typst 作为主链路。
