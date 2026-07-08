// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

// Crafted prompts for the STUDY module's learning quick actions.
//
// Kept dependency-free (no imports) so the prompt contract stays unit-testable
// in isolation.
//
// Design contract (see docs/immersive-learning-redesign.md): these actions
// open a *guided conversation*, not a report generator. Every prompt is
// bounded the same way — ask at most ONE question per turn and wait; deliver
// in small steps the learner confirms; never fabricate unknown facts; label
// uncertain content 已确认 / 待确认 / 推断 where it matters; no emoji. The old
// fixed eight-section output formats are deliberately gone: a wall of
// structured output is the work-agent pattern this product moved away from.

export const LEARNING_PROFILE_PROMPT = [
  "请用对话的方式，和我一起构建一份“个性化学习画像”。不要替我编造未知信息，也不要一次抛出一张问卷。",
  "一次只问一个问题（最多附一个紧密相关的小问题），从最关键的开始：我的专业/课程和学习目标；之后再逐步了解当前基础、薄弱点、学习偏好和可投入时间。听到我的回答后，先用一句话复述确认你的理解，再问下一个。",
  "当信息足够、或我说“可以了”时，给出一份简短的画像小结：分“已确认”和“推断”两部分，推断要说明依据；不确定的就标为待确认，不要写成事实。",
  "然后用 learning learning_draft_create 把画像写成 kind=student_state 草稿：payload 含 dimensions 数组，固定 6 个维度(key/label)——foundation 知识基础、cognitive_style 认知风格、weak_points 易错点偏好、goal 学习目标、pace 学习节奏与进度、interest 兴趣方向；每个维度含 level(0-5，是随学更新、我可随时修改的当前状态快照，不是固定能力评价)与 summary。信息不足的维度 level 给 0、summary 标“待补充”。创建后只简短告诉我已生成、待我在“学习画像”里审核激活。最后问我哪里需要修正。",
  "请不要使用 emoji，保持清晰、克制、温和的导师风格。",
].join("\n\n");

export const LEARNING_PATH_PROMPT = [
  "请帮我规划个性化学习路径，但要一步步来，不要一次吐出完整的几周计划。优先使用我已有的学习画像、课程材料或聊天上下文；缺什么信息就问，一次只问一个问题，不要编造。",
  "先和我确认学习目标和可投入时间；然后给出一个粗略的阶段划分（三到五个阶段，每个一句话），请我确认或调整；确认后只细化最近的一个阶段：具体任务、预计耗时、完成标准。后面的阶段等我走到了再细化。",
  "基于推断的安排要说明依据，标注为推断。每完成一段规划，用一两句话总结建议写回学习上下文的要点（当前阶段、下一步）。",
  "请不要使用 emoji，保持清晰、克制、温和的导师风格。",
].join("\n\n");

export const COURSE_KNOWLEDGE_BASE_PROMPT = [
  "请和我一起为一门课程梳理知识库。不要编造我没有提供的教材、论文或课程内容；先问我手头有什么材料、课程的范围是什么，一次只问一个问题。",
  "梳理时每次只处理一个单元或章节：列出该单元的核心知识点、各自的前置知识和典型易错点，并注明来源（我的材料，还是你的推断）。完成一个单元后停下来，问我是否有要补充或修正的，再继续下一个。",
  "来源不明的内容标为待确认，放在待采集清单里，不要写成事实。",
  "请不要使用 emoji，保持清晰、克制、温和的导师风格。",
].join("\n\n");

export const LEARNING_RESOURCE_PACK_PROMPT = [
  "请围绕一个课程主题或知识点，帮我生成个性化学习资源。优先基于我已有的学习画像、学习路径和课程材料；不要编造材料里没有的内容。",
  "如果我没有说明主题，先确认主题和我的目标水平，一次只问一个问题。",
  "资源不要一次全部生成：每次只做一类（例如知识点讲解、分层练习、实操案例、复习卡片），做完交给我，问我用得怎么样、要不要调整或继续下一类。练习题请分基础、进阶、应用三档。",
  "每类资源交付时用一句话说明它针对我的哪个薄弱点或需求；无法从材料确认的内容标为推断或待确认。最后用一两句话总结建议写回学习上下文的要点。",
  "请不要使用 emoji，保持清晰、克制、温和的导师风格。",
].join("\n\n");

export const LEARNING_TUTOR_PROMPT = [
  "请做我的辅导老师，帮我搞懂当前的学习问题。先让我说说我卡在哪里；背景不清楚就问，一次只问一个问题，不要编造题目条件或教材结论。",
  "讲解时小步推进：一次只讲一个概念或一步推导，讲完用一个小问题检查我是否跟上，等我回应再继续。不要一次把完整解答全部倒出来。",
  "这是练习场景：我答错或卡住时，先给提示让我再试一次，而不是直接公布答案；但如果我明确要求直接给答案，就完整给出，然后指出这个答案涉及哪些知识点、我跳过了什么值得回头补。",
  "结论请区分：来自我的材料的（已确认）和你的推断（说明依据）；依据不足就说不确定。",
  "请不要使用 emoji，保持清晰、克制、温和的导师风格。",
].join("\n\n");

export const LEARNING_EVALUATION_PROMPT = [
  "请帮我做一次学习效果小评估。优先基于我已有的学习画像、学习路径和练习记录；不要编造测试成绩或学习行为。",
  "评估用对话完成：出三到五个小问题或小题目，一次只出一题，等我回答后先给简短反馈（对在哪、错在哪），再出下一题。题目围绕我最近学的内容和记录的薄弱点。",
  "全部答完后，给一份简短小结：哪些点掌握了、哪些还薄弱（附证据，即我刚才的回答）、下一步建议保留什么、补什么。缺少客观数据的判断标为推断。",
  "最后用一两句话总结建议写回学习上下文的要点（薄弱点变化、下一轮调整）。",
  "请不要使用 emoji，保持清晰、克制、温和的导师风格。",
].join("\n\n");

export const CONTENT_SAFETY_REVIEW_PROMPT = [
  "请作为质量审核助手，对我提供的学习内容（知识库、学习路径、资源、辅导答案或评估结果）做防幻觉与内容安全审核。如果我还没有提供待审核内容，先请我粘贴或上传，不要自行假设审核对象。",
  "不要编造审核结论、来源或风险；无法确认的标为待确认，并说明需要补充什么证据。",
  "审核覆盖：事实来源与可核验性、未核验推断、学术准确性、敏感或违规内容、版权与许可标注、学习适配性。逐条列出发现的问题，每条标注严重级别（阻塞 / 需修改 / 建议优化）和证据状态（已确认 / 待确认 / 推断），并给出改写建议。",
  "如果发现可能的幻觉、来源缺失、过度承诺、声称生成了实际不存在的文件、版权不清或敏感违规风险，请明确指出。问题较多时先给最严重的几条，问我是否继续看其余的。",
  "请不要使用 emoji，保持清晰、克制、温和的导师风格。",
].join("\n\n");

export const STUDY_PROMPTS = {
  learningProfile: LEARNING_PROFILE_PROMPT,
  learningPath: LEARNING_PATH_PROMPT,
  courseKnowledgeBase: COURSE_KNOWLEDGE_BASE_PROMPT,
  learningResources: LEARNING_RESOURCE_PACK_PROMPT,
  learningTutor: LEARNING_TUTOR_PROMPT,
  learningEvaluation: LEARNING_EVALUATION_PROMPT,
  contentSafetyReview: CONTENT_SAFETY_REVIEW_PROMPT,
} as const;

export type StudyActionId = keyof typeof STUDY_PROMPTS;

// Generation prompt for the spaced-repetition flashcard module. M2 stores the
// deck as a typed learning draft via the learning toolset, so the student no
// longer copies JSON back into the UI.
export const FLASHCARD_GENERATION_PROMPT = [
  "请基于我已提供的学习材料、课程知识库或学习上下文，帮我生成一组用于间隔重复记忆的抽认卡片。不要编造材料里没有的事实、定义或数据；如果材料不足，请先追问 3 到 5 个关键问题，暂不输出卡片。",
  "请使用 STUDY learning 工具完成：先确认或创建当前课程空间，调用 learning_index_build 读取当前 Learning Index，然后用 learning_draft_create 创建 kind=flashcard_deck 的草稿。不要把卡片 JSON 直接贴给我让我复制导入。",
  "优先覆盖核心概念、易混淆点、公式/定义、关键步骤和我已记录的薄弱点。每张卡片只考察一个知识点，正面是一个明确问题或提示，背面是简洁、可自检的答案。",
  "生成 10 到 20 张卡片（材料不足时可少于 10 张）。payload 必须是 {\"cards\": [{\"front\": \"问题\", \"back\": \"答案\", \"hint\": \"可选提示\", \"tags\": [\"标签\"]}]}，字段值必须是纯文本字符串，不要包含未在材料中确认的内容。",
  "创建草稿后只用简短文字告诉我已生成并等待审核；如果某个知识点无法从材料中确认，请列为“待确认”。请不要使用 emoji。",
].join("\n\n");

// Generation prompt for the self-test quiz module. M3 stores quizzes as typed
// learning drafts; trusted UI/API activation and deterministic backend grading
// own the practice path, so the student no longer pastes JSON into the panel.
export const QUIZ_GENERATION_PROMPT = [
  "请基于我已提供的学习材料、课程知识库或学习上下文，帮我出一套用于自测的小测验，用来检验我的掌握程度。不要编造材料里没有的事实或数据；如果材料不足，请先追问 3 到 5 个关键问题，暂不出题。",
  "请使用 STUDY learning 工具完成：先确认或创建当前课程空间，调用 learning_index_build 读取当前 Learning Index，然后用 learning_draft_create 创建 kind=quiz 的草稿。不要把测验 JSON 直接贴给我让我复制导入。",
  "题目要覆盖核心概念、易错点和我记录的薄弱点，难度由易到难。共出 5 到 10 题，混合选择、判断和简答三种题型。每题只考察一个明确知识点，并尽量附一句简短解析（explanation）和 1 到 2 个知识点标签（tags）。",
  "payload 必须是 {\"questions\": [...]}。选择题 type 为 \"choice\"，必须给出至少 2 个 options，正确答案用 answer 表示选项下标（从 0 开始）；单选 answer 是整数，多选 answer 是整数数组。判断题 type 为 \"true_false\"，answer 是 true 或 false。简答题 type 为 \"short_answer\"，用 answer 或 accepted 给出可接受答案，供确定性判分。",
  "创建草稿后只用简短文字告诉我已生成并等待审核；如果某个知识点无法从材料中确认，请列为“待确认”。请不要使用 emoji。",
].join("\n\n");
