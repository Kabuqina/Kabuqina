// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

// Crafted prompts for the STUDY module's learning quick actions.
//
// Kept dependency-free (no imports) so the prompt contract stays unit-testable
// in isolation. The prompts are deliberately bounded for an academic assistant:
// ask 3–5 clarifying questions first, never fabricate unknown facts, label each
// item 已确认 / 待确认 / 推断, emit a fixed output structure, and use no emoji.
// Each later step builds on the earlier one (profile -> path -> resource pack).

export const LEARNING_PROFILE_PROMPT = [
  "请用对话式方式帮我构建一份“个性化学习画像”。这是一个学习规划前置步骤，不要替我编造未知信息。",
  "如果我还没有提供足够信息，请先追问 3 到 5 个最关键的问题；问题要覆盖专业/课程、学习目标、当前基础、薄弱点、学习偏好和可投入时间。",
  "当信息足够后，请输出结构化画像，至少包含 6 个维度：专业与课程背景、当前知识基础、学习目标、认知风格/学习偏好、易错点与知识短板、可投入时间与学习节奏、资源偏好、实践/代码基础。",
  "输出格式请固定为：1. 学习画像摘要；2. 画像维度表；3. 当前不确定信息；4. 下一步推荐资源类型；5. 后续可更新字段。",
  "请把每个维度标注为“已确认 / 待确认 / 推断”，推断内容必须说明依据；如果依据不足，放到“当前不确定信息”里，不要写成事实。",
  "请不要使用 emoji，保持清晰、克制、学术助手风格。",
].join("\n\n");

export const LEARNING_PATH_PROMPT = [
  "请帮我制定一份个性化学习路径规划。优先基于我已有的学习画像、课程材料或聊天上下文；如果信息不足，请先追问 3 到 5 个关键问题，不要直接编造学习路径。",
  "如果我已经提供学习画像，请先提取其中的学习目标、当前基础、薄弱点、学习偏好、可投入时间和资源偏好，再规划路径；如果没有画像，请先收集这些信息。",
  "当信息足够后，请输出结构化学习路径，至少包含：目标拆解、阶段安排、每日/每周任务、推荐资源类型、练习与项目安排、检查点/评估方式、根据薄弱点的补强任务。",
  "请把每个任务标注预计耗时、前置条件、完成标准和风险提示；如果某项安排基于推断，请明确写出推断依据。",
  "输出格式请固定为：1. 路径摘要；2. 阶段路线表；3. 每日/每周任务清单；4. 资源推荐与使用方式；5. 评估检查点；6. 动态调整建议。",
  "请不要使用 emoji，保持清晰、克制、学术助手风格。",
].join("\n\n");

export const LEARNING_RESOURCE_PACK_PROMPT = [
  "请帮我生成一份个性化学习资源包。优先基于我已有的学习画像、学习路径、课程材料或聊天上下文；如果信息不足，请先追问 3 到 5 个关键问题，不要直接编造课程内容或资源。",
  "资源包需要围绕一个明确课程主题或知识点展开。如果我没有说明主题，请先确认主题、目标水平、学习时长、薄弱点和希望的资源形式。",
  "当信息足够后，请生成至少 5 类学习资源：知识点讲解文档、知识点思维导图大纲、分层练习题、拓展阅读材料、代码/实验实操案例。可以按需要额外加入复习卡片、答疑卡片或小测评。",
  "每类资源都要说明：适合的画像维度或学习需求、使用方式、预计耗时、产出格式、完成标准和需要人工确认的事实。",
  "练习题请分基础、进阶、应用三档；代码/实验案例请包含目标、数据或输入、关键步骤、预期输出和检查点。",
  "输出格式请固定为：1. 资源包摘要；2. 资源清单总览；3. 各类资源正文；4. 使用顺序建议；5. 质量检查与不确定信息；6. 后续可扩展资源。",
  "请不要使用 emoji，保持清晰、克制、学术助手风格。",
].join("\n\n");

export const STUDY_PROMPTS = {
  learningProfile: LEARNING_PROFILE_PROMPT,
  learningPath: LEARNING_PATH_PROMPT,
  learningResources: LEARNING_RESOURCE_PACK_PROMPT,
} as const;

export type StudyActionId = keyof typeof STUDY_PROMPTS;
