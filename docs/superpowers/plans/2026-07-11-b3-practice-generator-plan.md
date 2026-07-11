# B-3 临摹与变式生成实施计划

**目标：** 为已激活的 `quiz` 题目提供确定性的临摹/变式草稿生成；生成物仍
保持 `draft`，必须由学习者激活后才可练习或执行。

## 边界

- 实现放在 `hermes_core/learning/`，由 desk route 调用；不向模型授予判分或
  激活权限。
- 临摹模板可从 code 的 `reference`/`target_code` 和 derivation 步骤生成；
  code 变式只支持具有可运行 Python `reference` + `test_code` 的函数题。
- 变式使用函数名 alpha-renaming 模板，并以 sandbox 运行变换后的
  `reference + test_code` 自检。自检失败绝不落库。
- 不能安全套模板时返回 `generated: false, fallback: model_draft_required`；
  模型兜底沿用现有 `learning_draft_create`，不由 trusted route 直接调用模型。
- 生成物写为 `draft` quiz，并使用 `variant_of` 或最小 source ref 保留谱系。

## 验收

1. 非 active 源题不能生成；code/derivation 临摹题可激活并由现有
   `QuizService` 判分。
2. Python 函数变式在落库前通过 sandbox 自检，且 `variant_of` 指回源 item。
3. 缺失参考实现、非 Python 或不支持的模板返回固定 fallback，不产生草稿。
4. desk route 只透传 trusted service 结果；core + route tests 通过。
