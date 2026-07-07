"""Role definitions for 小娜的智能体编队 (study team).

Pure data + prompt builders — no runtime imports. Each role becomes a child
``AIAgent`` at execution time (see ``tools/team_tool.py``); the specialization
here rides in the child's ephemeral system prompt, while the canonical teaching
conduct layer is inherited automatically from the parent (小娜).

The ``kind`` strings mirror ``learning.learning_contract.KINDS`` but are kept as
plain literals so this module has zero dependency on the learning package (keeps
the core unit-testable). ``KNOWN_KINDS`` is validated against the real contract
at runtime by ``tools/team_tool.py`` (best-effort, non-fatal).
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Callable, Dict, List, Mapping, Optional, Sequence, Tuple

# Mirror of learning_contract.KINDS (validated at runtime, see team_tool.py).
KNOWN_KINDS: frozenset = frozenset(
    {
        "student_state",
        "knowledge_base",
        "learning_plan",
        "resource_pack",
        "flashcard_deck",
        "quiz",
        "tutoring_note",
        "evaluation",
    }
)


@dataclass(frozen=True)
class RoleResult:
    """Outcome of one role's run. Produced by the injected ``run_role``."""

    role_id: str
    status: str  # working|produced|passed|flagged|failed|skipped
    summary: str = ""
    produced: Tuple[dict, ...] = ()  # [{artifact_id, kind, title}, ...]
    error: Optional[str] = None

    def with_produced(self, produced: Sequence[dict]) -> "RoleResult":
        return replace(self, produced=tuple(produced))


# A prompt builder maps (goal, upstream results) -> the child's role prompt.
PromptBuilder = Callable[[str, Mapping[str, RoleResult]], str]


@dataclass(frozen=True)
class RoleSpec:
    """Immutable declaration of one team role (planner_spec-style)."""

    role_id: str
    display: str  # student-facing label, always "小娜·…"
    blurb: str  # short description for the panel
    toolsets: Tuple[str, ...]
    allowed_kinds: frozenset
    depends_on: Tuple[str, ...] = ()
    model_tier: str = "main"  # "fast" | "main"
    is_gate: bool = False  # guardian / review node — emits no artifacts
    prompt_builder: Optional[PromptBuilder] = None

    def allows_kind(self, kind: str) -> bool:
        return kind in self.allowed_kinds

    def build_prompt(self, goal: str, upstream: Mapping[str, RoleResult]) -> str:
        if self.prompt_builder is not None:
            return self.prompt_builder(goal, upstream)
        return _default_prompt(self, goal, upstream)


def _upstream_digest(upstream: Mapping[str, RoleResult]) -> str:
    if not upstream:
        return ""
    lines = []
    for rid, res in upstream.items():
        if res and res.summary:
            lines.append(f"- 来自「{rid}」的结论：{res.summary}")
    return ("\n上游智能体已完成的工作：\n" + "\n".join(lines)) if lines else ""


def _default_prompt(spec: RoleSpec, goal: str, upstream: Mapping[str, RoleResult]) -> str:
    return (
        f"你现在作为小娜的「{spec.display}」子智能体工作。职责：{spec.blurb}\n"
        f"总目标：{goal}\n"
        f"{_upstream_digest(upstream)}\n"
        "只做属于你这一角色的部分，产出通过学习工具写入草稿箱（draft）。"
    )


# --------------------------------------------------------------------------- #
# Role-specific prompt builders (Chinese, concise — conduct layer is inherited)
# --------------------------------------------------------------------------- #

def _profiler_prompt(goal: str, up: Mapping[str, RoleResult]) -> str:
    return (
        "你是小娜的「画像师」。从对话历史与学习行为中，梳理/更新学生的学习画像，"
        "覆盖不少于 6 个维度（知识基础、认知风格、易错点偏好、学习目标、学习节奏、兴趣方向），"
        "以 student_state 草稿写入。画像必须是动态、可改、非评判的，绝不给学生贴固定能力标签。\n"
        f"总目标：{goal}"
    )


def _lecturer_prompt(goal: str, up: Mapping[str, RoleResult]) -> str:
    return (
        "你是小娜的「讲解官」。基于课程材料，把目标知识点梳理为课程知识库（knowledge_base）"
        "与节奏化讲解文档（resource_pack），小步推进、一次一个概念，并标注来源。以草稿写入。\n"
        f"{_upstream_digest(up)}\n总目标：{goal}"
    )


def _quizmaster_prompt(goal: str, up: Mapping[str, RoleResult]) -> str:
    return (
        "你是小娜的「出题官」。围绕讲解官梳理的知识点，生成练习题库（quiz）与复习闪卡"
        "（flashcard_deck）草稿；题目要能确定性判分，并覆盖易错点。以草稿写入。\n"
        f"{_upstream_digest(up)}\n总目标：{goal}"
    )


def _guardian_prompt(goal: str, up: Mapping[str, RoleResult]) -> str:
    return (
        "你是小娜的「守门人」。审阅本次编队产出的各类草稿：核对是否有事实性错误、"
        "引用是否可溯源、题目判分是否自洽、有无越权或敏感内容。你不创建学习内容，"
        "也不激活任何草稿（激活只属于学生）。给出一份把关摘要：checked / passed / flagged。\n"
        f"{_upstream_digest(up)}\n总目标：{goal}"
    )


# --------------------------------------------------------------------------- #
# Registry (M0 编制：画像 → 讲解 → 出题 → 守门)
# --------------------------------------------------------------------------- #

_M0_ROLES: List[RoleSpec] = [
    RoleSpec(
        role_id="profiler",
        display="小娜·画像",
        blurb="构建/更新 6 维学习画像",
        toolsets=("learning",),
        allowed_kinds=frozenset({"student_state"}),
        depends_on=(),
        model_tier="fast",
        prompt_builder=_profiler_prompt,
    ),
    RoleSpec(
        role_id="lecturer",
        display="小娜·讲解",
        blurb="梳理知识库与节奏化讲解",
        toolsets=("file", "learning"),
        allowed_kinds=frozenset({"knowledge_base", "resource_pack"}),
        depends_on=("profiler",),
        model_tier="main",
        prompt_builder=_lecturer_prompt,
    ),
    RoleSpec(
        role_id="quizmaster",
        display="小娜·出题",
        blurb="生成练习题库与复习闪卡",
        toolsets=("learning",),
        allowed_kinds=frozenset({"quiz", "flashcard_deck"}),
        depends_on=("lecturer",),
        model_tier="main",
        prompt_builder=_quizmaster_prompt,
    ),
    RoleSpec(
        role_id="guardian",
        display="小娜·把关",
        blurb="防幻觉/内容安全/引用溯源门禁",
        toolsets=(),
        allowed_kinds=frozenset(),
        depends_on=("profiler", "lecturer", "quizmaster"),
        model_tier="fast",
        is_gate=True,
        prompt_builder=_guardian_prompt,
    ),
]

ROLE_REGISTRY: Dict[str, RoleSpec] = {r.role_id: r for r in _M0_ROLES}


def default_team() -> List[RoleSpec]:
    """The M0 team, in declaration order (DAG is derived from depends_on)."""
    return list(_M0_ROLES)


def get_roles(role_ids: Optional[Sequence[str]] = None) -> List[RoleSpec]:
    """Resolve a subset of roles by id (unknown ids raise KeyError).

    When ``role_ids`` is falsy, returns the full default team. Guardian is
    always appended (as a gate) unless already present, so any subset stays
    reviewable.
    """
    if not role_ids:
        return default_team()
    specs = [ROLE_REGISTRY[rid] for rid in role_ids]
    if "guardian" not in {s.role_id for s in specs} and "guardian" in ROLE_REGISTRY:
        specs.append(ROLE_REGISTRY["guardian"])
    return specs
