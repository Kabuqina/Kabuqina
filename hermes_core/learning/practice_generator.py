"""Deterministic B-3 practice draft generation.

This trusted service turns an *active* question into a draft practice quiz.
It deliberately does not call a model: safe templates run first, while callers
receive ``model_draft_required`` when a question needs model-authored variation.
The existing model-facing OutputWriter path remains the sole model fallback.
"""

from __future__ import annotations

import ast
import re
from typing import Any, Dict, Optional

from learning.code_grader import run_python_grading
from learning.learning_context import LearningExecutionContext
from learning.output_writer import OutputWriter
from learning.quizzes import QuizService


MODEL_DRAFT_REQUIRED = "model_draft_required"
PRACTICE_SOURCE_ORIGIN = "practice_template"


def _text(value: Any, limit: int = 20_000) -> str:
    return value.strip()[:limit] if isinstance(value, str) else ""


def _title(prefix: str, prompt: str) -> str:
    return f"{prefix}: {_text(prompt, 240) or 'practice'}"


class PracticeGenerator:
    """Create reviewable template-derived practice drafts for one active item."""

    def __init__(self, context: LearningExecutionContext):
        self._ctx = context

    def generate(
        self,
        *,
        artifact_id: str,
        item_id: str,
        practice_kind: str,
    ) -> Dict[str, Any]:
        question = self._active_question(artifact_id, item_id)
        if practice_kind == "transcribe":
            candidate = self._transcription(question)
        elif practice_kind == "variant":
            candidate = self._variant(question)
        else:
            raise ValueError("practice_kind must be 'transcribe' or 'variant'")
        if candidate is None:
            return {
                "generated": False,
                "fallback": MODEL_DRAFT_REQUIRED,
                "reason": "no_safe_template",
                "source_item_id": item_id,
            }

        title, question_payload, self_checked = candidate
        written = OutputWriter(self._ctx).write_artifact(
            kind="quiz",
            title=title,
            payload={"questions": [question_payload]},
            source_refs=[{"origin": PRACTICE_SOURCE_ORIGIN, "item_id": item_id}],
        )
        return {
            "generated": True,
            "artifact_id": written["artifact_id"],
            "status": "draft",
            "practice_kind": practice_kind,
            "source_item_id": item_id,
            "self_checked": self_checked,
        }

    def _active_question(self, artifact_id: str, item_id: str) -> Dict[str, Any]:
        artifact = self._ctx.get_artifact(artifact_id)
        if not artifact:
            raise KeyError(f"artifact {artifact_id!r} not found")
        if artifact.get("kind") != "quiz":
            raise ValueError("artifact is not a quiz")
        if artifact.get("status") != "active":
            raise ValueError("practice source quiz is not active")
        for question in QuizService(self._ctx).list_questions(
            artifact_id=artifact_id, include_answers=True
        ):
            if question.get("item_id") == item_id:
                return question
        raise KeyError(f"question {item_id!r} not found")

    def _transcription(
        self, question: Dict[str, Any]
    ) -> Optional[tuple[str, Dict[str, Any], bool]]:
        qtype = question.get("type")
        if qtype == "code":
            target = _text(question.get("reference")) or _text(question.get("target_code"))
            language = _text(question.get("language"), 40).casefold()
            if not target or not language:
                return None
            return (
                _title("Transcribe", question.get("prompt")),
                {
                    "type": "code",
                    "prompt": f"Transcribe: {_text(question.get('prompt'), 900)}",
                    "language": language,
                    "mode": "transcribe",
                    "target_code": target,
                    "variant_of": question["item_id"],
                    "tags": list(question.get("tags") or []),
                    "points": question.get("points", 1),
                },
                True,
            )
        if qtype == "derivation":
            steps = question.get("steps")
            if not isinstance(steps, list) or not steps:
                return None
            copied_steps = []
            for step in steps:
                if not isinstance(step, dict) or not _text(step.get("expr")):
                    return None
                copied = {"expr": _text(step.get("expr"))}
                justification = _text(step.get("justification"), 1200)
                if justification:
                    copied["justification"] = justification
                    copied["accepted"] = [justification]
                copied_steps.append(copied)
            return (
                _title("Transcribe", question.get("prompt")),
                {
                    "type": "derivation",
                    "prompt": f"Transcribe: {_text(question.get('prompt'), 900)}",
                    "steps": copied_steps,
                    "check": "normalized-match",
                    "cloze": list(range(len(copied_steps))),
                    "tags": list(question.get("tags") or []),
                    "points": question.get("points", 1),
                },
                True,
            )
        return None

    def _variant(
        self, question: Dict[str, Any]
    ) -> Optional[tuple[str, Dict[str, Any], bool]]:
        if (
            question.get("type") != "code"
            or _text(question.get("language"), 40).casefold() != "python"
        ):
            return None
        reference = _text(question.get("reference"))
        test_code = _text(question.get("test_code"))
        if not reference or not test_code:
            return None
        name = self._top_level_function_name(reference)
        if not name:
            return None
        replacement = self._unused_variant_name(name, reference, test_code)
        transformed_reference = self._rename_identifier(reference, name, replacement)
        transformed_test = self._rename_identifier(test_code, name, replacement)
        checked = run_python_grading(transformed_reference, transformed_test)
        if not checked["passed"]:
            return None
        starter = self._rename_identifier(_text(question.get("starter")), name, replacement)
        return (
            _title("Variant", question.get("prompt")),
            {
                "type": "code",
                "prompt": f"Variant: {_text(question.get('prompt'), 900)}",
                "language": "python",
                "mode": "variant",
                "starter": starter,
                "test_code": transformed_test,
                "reference": transformed_reference,
                "variant_of": question["item_id"],
                "tags": list(question.get("tags") or []),
                "points": question.get("points", 1),
            },
            True,
        )

    @staticmethod
    def _top_level_function_name(source: str) -> str:
        try:
            module = ast.parse(source)
        except SyntaxError:
            return ""
        for node in module.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                return node.name
        return ""

    @staticmethod
    def _unused_variant_name(name: str, *sources: str) -> str:
        candidate = f"{name}_variant"
        suffix = 2
        combined = "\n".join(sources)
        while re.search(rf"\b{re.escape(candidate)}\b", combined):
            candidate = f"{name}_variant_{suffix}"
            suffix += 1
        return candidate

    @staticmethod
    def _rename_identifier(source: str, old: str, new: str) -> str:
        if not source:
            return ""
        return re.sub(rf"\b{re.escape(old)}\b", new, source)
