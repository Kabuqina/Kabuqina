"""Quiz practice service for STUDY M3.

The model-facing ``learning`` tools create ``quiz`` drafts. This module is the
trusted practice layer used by UI/API commands: activate/reject a quiz,
materialize active questions into ``learning_items``, and record deterministic
quiz attempts.
"""

from __future__ import annotations

import unicodedata
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from learning.learning_context import LearningExecutionContext

QUIZ_QUESTION_ITEM_TYPE = "quiz_question"
QUIZ_ATTEMPT_ACTIVITY = "quiz.attempt"

MAX_TEXT = 1200
MAX_OPTION_TEXT = 600
MAX_OPTIONS = 26
MAX_TAGS = 8
MAX_POINTS = 100


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


def _clean_text(value: Any, limit: int = MAX_TEXT) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()[:limit]


def _clean_str_list(value: Any, limit: int = MAX_TEXT, max_items: int = MAX_TAGS) -> List[str]:
    if not isinstance(value, list):
        return []
    out: List[str] = []
    seen: set[str] = set()
    for raw in value:
        text = _clean_text(raw, limit)
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(text)
        if len(out) >= max_items:
            break
    return out


def _clean_options(value: Any) -> List[str]:
    return _clean_str_list(value, MAX_OPTION_TEXT, MAX_OPTIONS)


def _clean_tags(value: Any) -> List[str]:
    return _clean_str_list(value, 40, MAX_TAGS)


def _points(value: Any) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return 1
    return max(1, min(MAX_POINTS, n))


def _item_id(artifact_id: str, index: int) -> str:
    return f"{artifact_id}-{index:04d}"


def _edge_trim_punct_symbols(value: str) -> str:
    chars = list(value)
    while chars and unicodedata.category(chars[0])[0] in {"P", "S"}:
        chars.pop(0)
    while chars and unicodedata.category(chars[-1])[0] in {"P", "S"}:
        chars.pop()
    return "".join(chars)


def normalize_short_answer(value: Any) -> str:
    text = _clean_text(value).lower()
    text = " ".join(text.split())
    return _edge_trim_punct_symbols(text)


def _answer_indices(answer: Any, option_count: int) -> List[int]:
    raw = answer if isinstance(answer, list) else [answer]
    out: List[int] = []
    for value in raw:
        if isinstance(value, bool) or not isinstance(value, int):
            continue
        if 0 <= value < option_count and value not in out:
            out.append(value)
    return sorted(out)


def _selected_indices(response: Any, option_count: int) -> List[int]:
    if not isinstance(response, dict):
        return []
    selected = response.get("selected")
    if not isinstance(selected, list):
        return []
    out: List[int] = []
    for value in selected:
        if isinstance(value, bool) or not isinstance(value, int):
            continue
        if 0 <= value < option_count and value not in out:
            out.append(value)
    return sorted(out)


class QuizService:
    """Trusted operations for active quizzes and deterministic attempts."""

    def __init__(
        self,
        context: LearningExecutionContext,
        *,
        now: Optional[Callable[[], datetime]] = None,
    ):
        self._ctx = context
        self._now = now or _now_utc

    def activate_quiz(self, artifact_id: str) -> Dict[str, Any]:
        artifact = self._require_quiz(artifact_id)
        if artifact["status"] == "draft":
            self._ctx.set_artifact_status(artifact_id, "active")
            artifact = self._require_quiz(artifact_id)
        elif artifact["status"] != "active":
            self._ctx.set_artifact_status(artifact_id, "active")
            artifact = self._require_quiz(artifact_id)

        existing = {
            row["item_id"]
            for row in self._ctx.list_items(
                item_type=QUIZ_QUESTION_ITEM_TYPE,
                artifact_id=artifact_id,
            )
        }
        created = 0
        now = _iso(self._now())
        for index, question in enumerate(self._quiz_questions(artifact)):
            iid = _item_id(artifact_id, index)
            if iid in existing:
                continue
            self._ctx.upsert_item(
                item_id=iid,
                item_type=QUIZ_QUESTION_ITEM_TYPE,
                artifact_id=artifact_id,
                state=self._initial_state(
                    question,
                    item_id=iid,
                    artifact_id=artifact_id,
                    now=now,
                ),
            )
            created += 1
        return {"artifact_id": artifact_id, "status": "active", "materialized": created}

    def reject_quiz(self, artifact_id: str) -> Dict[str, Any]:
        artifact = self._require_quiz(artifact_id)
        if artifact["status"] != "rejected":
            self._ctx.set_artifact_status(artifact_id, "rejected")
        return {"artifact_id": artifact_id, "status": "rejected"}

    def list_quizzes(self, *, status: Optional[str] = None) -> List[Dict[str, Any]]:
        return self._ctx.list_artifacts(kind="quiz", status=status)

    def list_questions(
        self,
        *,
        artifact_id: Optional[str] = None,
        include_answers: bool = False,
    ) -> List[Dict[str, Any]]:
        rows = self._ctx.list_items(
            item_type=QUIZ_QUESTION_ITEM_TYPE,
            artifact_id=artifact_id,
        )
        return [self._question_from_item(row, include_answers=include_answers) for row in rows]

    def submit_attempt(self, artifact_id: str, responses: Dict[str, Any]) -> Dict[str, Any]:
        artifact = self._require_quiz(artifact_id)
        if artifact["status"] != "active":
            raise ValueError("quiz is not active")
        if not isinstance(responses, dict):
            responses = {}

        questions = self.list_questions(artifact_id=artifact_id, include_answers=True)
        per_question: List[Dict[str, Any]] = []
        weak_tags: List[str] = []
        seen_weak: set[str] = set()
        score = 0
        max_score = 0
        correct_count = 0

        for question in questions:
            response = responses.get(question["item_id"], {})
            graded = self._grade_question(question, response)
            max_score += graded["points"]
            if graded["correct"]:
                score += graded["points"]
                correct_count += 1
            else:
                for tag in question.get("tags") or []:
                    if tag not in seen_weak:
                        seen_weak.add(tag)
                        weak_tags.append(tag)
            per_question.append(graded)

        total = len(questions)
        percent = round((score / max_score) * 100) if max_score else 0
        detail = {
            "artifact_id": artifact_id,
            "score": score,
            "maxScore": max_score,
            "percent": percent,
            "correctCount": correct_count,
            "total": total,
            "weakTags": weak_tags,
            "perQuestion": per_question,
        }
        activity_id = self._ctx.record_activity(
            activity_type=QUIZ_ATTEMPT_ACTIVITY,
            artifact_id=artifact_id,
            detail=detail,
        )
        return {**detail, "activity_id": activity_id}

    def _require_quiz(self, artifact_id: str) -> Dict[str, Any]:
        artifact = self._ctx.get_artifact(artifact_id)
        if not artifact:
            raise KeyError(f"artifact {artifact_id!r} not found")
        if artifact.get("kind") != "quiz":
            raise ValueError("artifact is not a quiz")
        return artifact

    def _quiz_questions(self, artifact: Dict[str, Any]) -> List[Dict[str, Any]]:
        envelope = artifact.get("envelope") or {}
        payload = envelope.get("payload") if isinstance(envelope, dict) else {}
        questions = payload.get("questions") if isinstance(payload, dict) else []
        return [q for q in questions if isinstance(q, dict)]

    def _initial_state(
        self,
        question: Dict[str, Any],
        *,
        item_id: str,
        artifact_id: str,
        now: str,
    ) -> Dict[str, Any]:
        qtype = question.get("type")
        options = _clean_options(question.get("options"))
        state = {
            "item_id": item_id,
            "artifact_id": artifact_id,
            "type": qtype,
            "prompt": _clean_text(question.get("prompt")),
            "options": options,
            "answer": question.get("answer"),
            "accepted": _clean_str_list(question.get("accepted"), 200, 16),
            "explanation": _clean_text(question.get("explanation")),
            "tags": _clean_tags(question.get("tags")),
            "points": _points(question.get("points")),
            "createdAt": now,
        }
        if qtype == "true_false":
            state["answer"] = bool(question.get("answer"))
        if qtype == "choice":
            indices = _answer_indices(question.get("answer"), len(options))
            state["answer"] = indices if isinstance(question.get("answer"), list) else (indices[0] if indices else 0)
            state["multiple"] = len(indices) > 1
        return state

    def _question_from_item(self, row: Dict[str, Any], *, include_answers: bool) -> Dict[str, Any]:
        state = dict(row.get("state") or {})
        out = {
            **state,
            "item_id": row["item_id"],
            "artifact_id": row.get("artifact_id") or state.get("artifact_id") or "",
        }
        if not include_answers:
            out.pop("answer", None)
            out.pop("accepted", None)
        return out

    def _grade_question(self, question: Dict[str, Any], response: Any) -> Dict[str, Any]:
        qtype = question.get("type")
        points = _points(question.get("points"))
        correct = False
        normalized_response: Dict[str, Any] = {}

        if qtype == "choice":
            options = question.get("options") if isinstance(question.get("options"), list) else []
            selected = _selected_indices(response, len(options))
            answer = _answer_indices(question.get("answer"), len(options))
            correct = selected == answer and bool(answer)
            normalized_response = {"selected": selected}
        elif qtype == "true_false":
            value = response.get("value") if isinstance(response, dict) else None
            correct = isinstance(value, bool) and value is bool(question.get("answer"))
            normalized_response = {"value": value if isinstance(value, bool) else None}
        elif qtype == "short_answer":
            text = response.get("text") if isinstance(response, dict) else ""
            normalized = normalize_short_answer(text)
            accepted = [normalize_short_answer(question.get("answer"))]
            accepted.extend(normalize_short_answer(a) for a in question.get("accepted") or [])
            accepted = [a for a in accepted if a]
            correct = bool(normalized) and normalized in accepted
            normalized_response = {"text": _clean_text(text, 500), "normalized": normalized}

        answer = question.get("answer")
        earned = points if correct else 0
        return {
            "item_id": question["item_id"],
            "prompt": question.get("prompt") or "",
            "type": qtype,
            "correct": correct,
            "earned": earned,
            "points": points,
            "answer": answer,
            "accepted": question.get("accepted") or [],
            "explanation": question.get("explanation") or "",
            "tags": question.get("tags") or [],
            "response": normalized_response,
        }
