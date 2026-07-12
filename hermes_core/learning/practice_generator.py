"""Deterministic B-3 practice draft generation.

This trusted service turns an *active* question into a draft practice quiz.
It deliberately does not call a model: safe templates run first, while callers
receive ``model_draft_required`` when a question needs model-authored variation.
The existing model-facing OutputWriter path remains the sole model fallback.
"""

from __future__ import annotations

import ast
import io
import re
import tokenize
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
            target_steps = []
            for step in steps:
                if not isinstance(step, dict) or not _text(step.get("expr")):
                    return None
                copied = {"expr": _text(step.get("expr"))}
                justification = _text(step.get("justification"), 1200)
                if justification:
                    copied["justification"] = justification
                    copied["accepted"] = [justification]
                copied_steps.append(copied)
                target_steps.append(
                    {"expr": copied["expr"], "justification": justification}
                )
            return (
                _title("Transcribe", question.get("prompt")),
                {
                    "type": "derivation",
                    "prompt": f"Transcribe: {_text(question.get('prompt'), 900)}",
                    "mode": "transcribe",
                    "steps": copied_steps,
                    "target_steps": target_steps,
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
        starter_source = _text(question.get("starter"))
        name = self._target_function_name(reference, starter_source, test_code)
        if not name:
            return None
        replacement = self._unused_variant_name(name, reference, test_code)
        transformed_reference = self._rename_identifier(reference, name, replacement)
        transformed_test = self._rename_identifier(test_code, name, replacement)
        checked = run_python_grading(transformed_reference, transformed_test)
        if not checked["passed"]:
            return None
        starter = self._rename_identifier(starter_source, name, replacement)
        payload = {
            "type": "code",
            "prompt": f"Variant: implement `{replacement}` (renamed from `{name}`). {_text(question.get('prompt'), 700)}",
            "language": "python",
            "mode": "variant",
            "test_code": transformed_test,
            "reference": transformed_reference,
            "variant_of": question["item_id"],
            "tags": list(question.get("tags") or []),
            "points": question.get("points", 1),
        }
        if starter:
            payload["starter"] = starter
        return (
            _title("Variant", question.get("prompt")),
            payload,
            True,
        )

    @staticmethod
    def _top_level_function_names(source: str) -> set[str]:
        try:
            module = ast.parse(source)
        except SyntaxError:
            return set()
        return {node.name for node in module.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}

    @classmethod
    def _target_function_name(cls, reference: str, starter: str, test_code: str) -> str:
        available = cls._top_level_function_names(reference)
        starter_names = cls._top_level_function_names(starter) & available
        if len(starter_names) == 1:
            return next(iter(starter_names))
        try:
            test_tree = ast.parse(test_code)
        except SyntaxError:
            return ""
        called = {
            node.func.id for node in ast.walk(test_tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        } & available
        return next(iter(called)) if len(called) == 1 else ""

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
        """Rename NAME tokens only; comments and string/docstring values stay literal."""
        if not source:
            return ""
        try:
            tokens = tokenize.generate_tokens(io.StringIO(source).readline)
            rewritten = [
                token._replace(string=new)
                if token.type == tokenize.NAME and token.string == old
                else token
                for token in tokens
            ]
            return tokenize.untokenize(rewritten)
        except (tokenize.TokenError, IndentationError):
            return ""
