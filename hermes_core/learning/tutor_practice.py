# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Trusted Practice source and deterministic grader adapter for Tutor L-3.

The adapter is owner/space scoped through ``LearningExecutionContext``.  It
pins only activated quiz-item truth, performs no provider or network call, and
uses the side-effect-free QuizService single-question grader.  Durable Tutor
state receives provenance and fingerprints, never expected answers or raw
learner responses.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from typing import Any, Callable, Literal, Mapping

from agent.graph_engine.tutor_branch_policy import (
    DeterministicEvaluationResultV1,
    PinnedTutorSourceRefV1,
    SourceStatus,
    TutorCheckSpecV1,
)
from learning.learning_context import LearningExecutionContext
from learning.practice_contract import (
    PRACTICE_GRADER_POLICY_VERSION,
    PracticeContractError,
    build_grader_provenance,
    validate_grader_provenance,
)
from learning.quizzes import QUIZ_QUESTION_ITEM_TYPE, QuizService
from learning.tutor_contract import (
    LearningActivityKeyV1,
    TutorContractError,
    canonical_json_bytes,
)


TUTOR_PRACTICE_ADAPTER_VERSION = "tutor-practice-v1"

_GRADER_SHAPES: dict[str, tuple[str, str]] = {
    "choice_exact": ("choice", "choice-v1"),
    "boolean_exact": ("choice", "boolean-v1"),
    "short_answer_exact": ("free_text", "short-answer-v1"),
    "code_transcribe": ("free_text", "code-v1"),
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class ResolvedTutorPracticeCheckV1:
    """Host-owned check spec plus learner-visible, truth-free prompt."""

    check_spec: TutorCheckSpecV1
    prompt: dict[str, Any]
    schema_version: int = 1

    def __post_init__(self) -> None:
        if self.schema_version != 1 or not isinstance(
            self.check_spec, TutorCheckSpecV1
        ):
            raise TutorContractError("resolved Practice check is invalid")
        if not isinstance(self.prompt, dict) or set(self.prompt) != {
            "schema_version",
            "template",
            "message",
            "options",
        }:
            raise TutorContractError("resolved Practice prompt is invalid")
        if (
            self.prompt.get("schema_version") != 1
            or self.prompt.get("template") != "practice-v1"
            or not isinstance(self.prompt.get("message"), str)
            or not self.prompt["message"]
            or not isinstance(self.prompt.get("options"), list)
        ):
            raise TutorContractError("resolved Practice prompt is invalid")


class TutorPracticeAdapter:
    """Resolve, verify and grade activated Practice items for one owner/space."""

    def __init__(
        self,
        context: LearningExecutionContext,
        *,
        now: Callable[[], str] = _utc_now,
    ) -> None:
        self._ctx = context
        self._quiz = QuizService(context)
        self._now = now

    def _question_by_source_id(
        self, source_id: str
    ) -> tuple[str, dict[str, Any]] | None:
        rows = [
            row
            for row in self._ctx.list_items(item_type=QUIZ_QUESTION_ITEM_TYPE)
            if row.get("item_id") == source_id
        ]
        if len(rows) != 1:
            return None
        artifact_id = rows[0].get("artifact_id")
        if not isinstance(artifact_id, str) or not artifact_id:
            return None
        try:
            question = self._quiz.get_active_question(
                artifact_id,
                source_id,
                include_answers=True,
            )
        except (KeyError, ValueError):
            return None
        return artifact_id, question

    @staticmethod
    def _trusted_provenance(
        question: Mapping[str, Any],
        *,
        artifact_id: str,
    ) -> dict[str, Any]:
        try:
            stored = validate_grader_provenance(question.get("grader_provenance"))
            rebuilt = build_grader_provenance(
                question,
                artifact_id=artifact_id,
                artifact_version=int(question.get("artifact_version") or 0),
                item_id=str(question.get("item_id") or ""),
            )
        except (PracticeContractError, TypeError, ValueError) as exc:
            raise TutorContractError(
                "Practice item has no trusted deterministic provenance",
                reason_code="source_untrusted",
            ) from exc
        if stored != rebuilt:
            raise TutorContractError(
                "Practice item provenance does not match its truth",
                reason_code="source_untrusted",
            )
        if stored["grader_kind"] not in _GRADER_SHAPES:
            raise TutorContractError(
                "Practice grader is not a total Tutor v1 grader",
                reason_code="grader_not_supported",
            )
        if stored["grader_kind"] == "short_answer_exact":
            truth = [question.get("answer"), *(question.get("accepted") or [])]
            if not any(isinstance(item, str) and item.strip() for item in truth):
                raise TutorContractError(
                    "Practice short-answer truth is empty",
                    reason_code="source_untrusted",
                )
        if stored["grader_kind"] == "code_transcribe" and not str(
            question.get("target_code") or ""
        ).strip():
            raise TutorContractError(
                "Practice transcription truth is empty",
                reason_code="source_untrusted",
            )
        return stored

    @staticmethod
    def _prompt(question: Mapping[str, Any], grader_kind: str) -> dict[str, Any]:
        options: list[dict[str, str]] = []
        if grader_kind == "choice_exact":
            options = [
                {"id": str(index), "label": str(label)}
                for index, label in enumerate(question.get("options") or [])
            ]
        elif grader_kind == "boolean_exact":
            options = [
                {"id": "true", "label": "True"},
                {"id": "false", "label": "False"},
            ]
        return {
            "schema_version": 1,
            "template": "practice-v1",
            "message": str(question.get("prompt") or ""),
            "options": options,
        }

    def resolve_check(
        self,
        *,
        artifact_id: str,
        item_id: str,
    ) -> ResolvedTutorPracticeCheckV1:
        """Pin one active source; correct completion is host policy, not input."""
        try:
            question = self._quiz.get_active_question(
                artifact_id,
                item_id,
                include_answers=True,
            )
        except (KeyError, ValueError) as exc:
            raise TutorContractError(
                "Practice source is not active",
                reason_code="source_missing",
            ) from exc
        provenance = self._trusted_provenance(question, artifact_id=artifact_id)
        expected_input, normalization = _GRADER_SHAPES[provenance["grader_kind"]]
        rubric_ref = PinnedTutorSourceRefV1(
            source_kind="activated_quiz_item",
            source_id=item_id,
            source_version=provenance["artifact_version"],
            source_sha256=provenance["rubric_sha256"],
        )
        return ResolvedTutorPracticeCheckV1(
            check_spec=TutorCheckSpecV1(
                check_id=f"practice:{item_id}",
                expected_input=expected_input,
                evaluation_mode="deterministic",
                normalization_policy=normalization,
                rubric_ref=rubric_ref,
                correct_action="complete",
            ),
            prompt=self._prompt(question, provenance["grader_kind"]),
        )

    def _load_pinned_source(
        self,
        rubric_ref: PinnedTutorSourceRefV1,
    ) -> tuple[SourceStatus, tuple[str, dict[str, Any], dict[str, Any]] | None]:
        if rubric_ref.source_kind != "activated_quiz_item":
            return "missing", None
        loaded = self._question_by_source_id(rubric_ref.source_id)
        if loaded is None:
            return "missing", None
        artifact_id, question = loaded
        try:
            provenance = self._trusted_provenance(question, artifact_id=artifact_id)
        except TutorContractError:
            return "hash_mismatch", None
        if provenance["artifact_version"] != rubric_ref.source_version:
            return "stale", None
        if provenance["rubric_sha256"] != rubric_ref.source_sha256:
            return "hash_mismatch", None
        return "verified", (artifact_id, question, provenance)

    def source_status(self, rubric_ref: PinnedTutorSourceRefV1) -> SourceStatus:
        return self._load_pinned_source(rubric_ref)[0]

    @staticmethod
    def _quiz_response(
        question: Mapping[str, Any], answer: Any, grader_kind: str
    ) -> dict[str, Any] | None:
        if not isinstance(answer, Mapping):
            return None
        if grader_kind == "choice_exact":
            if set(answer) != {"type", "selected"} or answer.get("type") != "choice":
                return None
            selected = answer.get("selected")
            if not isinstance(selected, list) or len(selected) != len(set(selected)):
                return None
            try:
                indices = [int(item) for item in selected]
            except (TypeError, ValueError):
                return None
            option_count = len(question.get("options") or [])
            if any(str(index) != raw or not 0 <= index < option_count for index, raw in zip(indices, selected)):
                return None
            return {"selected": indices}
        if grader_kind == "boolean_exact":
            if set(answer) != {"type", "selected"} or answer.get("type") != "choice":
                return None
            selected = answer.get("selected")
            if selected not in (["true"], ["false"]):
                return None
            return {"value": selected == ["true"]}
        if set(answer) != {"type", "text"} or answer.get("type") != "free_text":
            return None
        text = answer.get("text")
        if not isinstance(text, str):
            return None
        if grader_kind == "short_answer_exact":
            return {"text": text}
        if grader_kind == "code_transcribe":
            return {"code": text}
        return None

    def evaluate(
        self,
        *,
        key: LearningActivityKeyV1,
        checkpoint_revision: int,
        check_spec: TutorCheckSpecV1,
        answer: Mapping[str, Any],
    ) -> tuple[DeterministicEvaluationResultV1, SourceStatus]:
        """Return typed branch evidence and source status without writing."""
        if key.activity_kind != "tutor" or check_spec.evaluation_mode != "deterministic":
            raise TutorContractError("Practice evaluation identity is invalid")
        if check_spec.rubric_ref is None:
            raise TutorContractError("Practice evaluation requires rubric_ref")
        answer_fingerprint = hashlib.sha256(canonical_json_bytes(answer)).hexdigest()
        status, loaded = self._load_pinned_source(check_spec.rubric_ref)
        outcome: Literal["correct", "incorrect", "invalid"] = "invalid"
        grader_kind = "unverified"
        if status == "verified":
            if loaded is None:  # Satisfy type narrowing; verified always carries it.
                raise TutorContractError("verified Practice source is unavailable")
            _artifact_id, question, provenance = loaded
            grader_kind = provenance["grader_kind"]
            response = self._quiz_response(question, answer, grader_kind)
            if response is not None:
                grade = self._quiz.grade_question_snapshot(question, response)
                if grade.get("outcome") in {"correct", "incorrect"}:
                    outcome = grade["outcome"]
        codes = {
            "correct": ("deterministic_correct", "rubric_verified"),
            "incorrect": ("deterministic_incorrect", "rubric_verified"),
            "invalid": ("answer_invalid",),
        }[outcome]
        digest = hashlib.sha256(
            canonical_json_bytes(
                {
                    "activity_id": key.activity_id,
                    "check_id": check_spec.check_id,
                    "checkpoint_revision": checkpoint_revision,
                    "answer_fingerprint": answer_fingerprint,
                }
            )
        ).hexdigest()
        return (
            DeterministicEvaluationResultV1(
                evaluation_id=f"teval_{digest[:48]}",
                activity_id=key.activity_id,
                activity_kind=key.activity_kind,
                check_id=check_spec.check_id,
                checkpoint_revision=checkpoint_revision,
                mode="deterministic",
                outcome=outcome,
                grader_id=f"practice.{grader_kind}",
                grader_version=PRACTICE_GRADER_POLICY_VERSION,
                rubric_ref=check_spec.rubric_ref,
                answer_fingerprint=answer_fingerprint,
                evidence_codes=codes,
                evaluated_at=self._now(),
            ),
            status,
        )


__all__ = [
    "ResolvedTutorPracticeCheckV1",
    "TUTOR_PRACTICE_ADAPTER_VERSION",
    "TutorPracticeAdapter",
]
