"""Quiz practice service for STUDY M3.

The model-facing ``learning`` tools create ``quiz`` drafts. This module is the
trusted practice layer used by UI/API commands: activate/reject a quiz,
materialize active questions into ``learning_items``, and record deterministic
quiz attempts.
"""

from __future__ import annotations

import ast
import copy
import unicodedata
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from learning.learning_context import LearningExecutionContext
from learning.code_grader import check_numeric_equivalence, run_python_grading

QUIZ_QUESTION_ITEM_TYPE = "quiz_question"
QUIZ_ATTEMPT_ACTIVITY = "quiz.attempt"

MAX_TEXT = 1200
MAX_OPTION_TEXT = 600
MAX_OPTIONS = 26
MAX_TAGS = 8
MAX_POINTS = 100
MAX_CODE_TEXT = 20_000
MAX_DERIVATION_STEPS = 50


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


def _normalize_code(value: Any) -> str:
    """Normalize harmless trailing whitespace while retaining code structure."""
    text = _clean_text(value, MAX_CODE_TEXT)
    lines: List[str] = []
    previous_blank = False
    for line in text.splitlines():
        normalized = line.rstrip()
        blank = not normalized
        if blank and previous_blank:
            continue
        lines.append(normalized)
        previous_blank = blank
    return "\n".join(lines).strip()


def _normalize_expression(value: Any) -> str:
    text = unicodedata.normalize("NFKC", _clean_text(value, MAX_CODE_TEXT)).casefold()
    return "".join(text.split())


def _failure_kind(summary: str) -> str:
    """Return the display-safe classifier part of an arbitrary failure string."""
    return _clean_text(summary.split(":", 1)[0], 100)


def _expression_variables(*expressions: str) -> List[str]:
    """Extract public identifiers for the numeric-equivalence runner."""
    names: set[str] = set()
    try:
        for expression in expressions:
            tree = ast.parse(expression, mode="eval")
            names.update(
                node.id
                for node in ast.walk(tree)
                if isinstance(node, ast.Name) and node.id != "math" and not node.id.startswith("_")
            )
    except (SyntaxError, TypeError):
        return []
    return sorted(names)[:16]


def _response_steps(response: Any) -> Dict[int, Dict[str, Any]]:
    if not isinstance(response, dict):
        return {}
    raw = response.get("steps")
    if isinstance(raw, list):
        return {index: value for index, value in enumerate(raw) if isinstance(value, dict)}
    if not isinstance(raw, dict):
        return {}
    out: Dict[int, Dict[str, Any]] = {}
    for key, value in raw.items():
        if not isinstance(value, dict):
            continue
        try:
            index = int(key)
        except (TypeError, ValueError):
            continue
        if index >= 0:
            out[index] = value
    return out


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

    def submit_attempt(
        self,
        artifact_id: str,
        responses: Dict[str, Any],
        *,
        item_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        artifact = self._require_quiz(artifact_id)
        if artifact["status"] != "active":
            raise ValueError("quiz is not active")
        if not isinstance(responses, dict):
            responses = {}

        questions = self.list_questions(artifact_id=artifact_id, include_answers=True)
        if item_ids is not None:
            requested_list: List[str] = []
            seen_requested: set[str] = set()
            for item_id in item_ids:
                if not isinstance(item_id, str) or not item_id.strip():
                    raise ValueError("item_ids must name questions in this quiz")
                normalized = item_id.strip()
                if normalized in seen_requested:
                    raise ValueError("item_ids must not contain duplicates")
                seen_requested.add(normalized)
                requested_list.append(normalized)
            requested = set(requested_list)
            available = {question["item_id"] for question in questions}
            if not requested or not requested.issubset(available):
                raise ValueError("item_ids must name questions in this quiz")
            questions = [
                question for question in questions
                if question["item_id"] in requested
            ]
        per_question: List[Dict[str, Any]] = []
        weak_tags: List[str] = []
        seen_weak: set[str] = set()
        score = 0
        max_score = 0
        correct_count = 0

        for question in questions:
            response = responses.get(question["item_id"], {})
            graded = self._grade_question(question, response)
            if graded["scored"]:
                max_score += graded["points"]
            if graded["scored"] and graded["correct"]:
                score += graded["points"]
                correct_count += 1
            elif graded["scored"]:
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
        activity_detail = {
            **detail,
            "perQuestion": self._activity_question_detail(per_question),
        }
        activity_id = self._ctx.record_activity(
            activity_type=QUIZ_ATTEMPT_ACTIVITY,
            artifact_id=artifact_id,
            detail=activity_detail,
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
        elif qtype == "code":
            state.update(
                {
                    "language": _clean_text(question.get("language"), 40).casefold(),
                    "mode": _clean_text(question.get("mode"), 40).casefold(),
                    "starter": _clean_text(question.get("starter"), MAX_CODE_TEXT),
                    "target_code": _clean_text(question.get("target_code"), MAX_CODE_TEXT),
                    "test_code": _clean_text(question.get("test_code"), MAX_CODE_TEXT),
                    "reference": _clean_text(question.get("reference"), MAX_CODE_TEXT),
                    "variant_of": _clean_text(question.get("variant_of"), 200),
                }
            )
        elif qtype == "derivation":
            steps = question.get("steps") if isinstance(question.get("steps"), list) else []
            mode = _clean_text(question.get("mode"), 40).casefold() or "solve"
            state.update(
                {
                    "mode": mode,
                    "steps": [
                        {
                            "expr": _clean_text(step.get("expr"), MAX_CODE_TEXT),
                            "expr_py": _clean_text(step.get("expr_py"), MAX_CODE_TEXT),
                            "justification": _clean_text(step.get("justification"), MAX_TEXT),
                            "accepted": _clean_str_list(step.get("accepted"), 200, 16),
                        }
                        for step in steps[:MAX_DERIVATION_STEPS]
                        if isinstance(step, dict)
                    ],
                    "check": _clean_text(question.get("check"), 40).casefold(),
                    "cloze": [
                        index
                        for index in (question.get("cloze") or [])
                        if isinstance(index, int) and not isinstance(index, bool) and index >= 0
                    ][:MAX_DERIVATION_STEPS],
                    "target_steps": [
                        {
                            "expr": _clean_text(step.get("expr"), MAX_CODE_TEXT),
                            "justification": _clean_text(step.get("justification"), MAX_TEXT),
                        }
                        for step in (question.get("target_steps") or [])[:MAX_DERIVATION_STEPS]
                        if isinstance(step, dict)
                    ],
                }
            )
        return state

    def _question_from_item(self, row: Dict[str, Any], *, include_answers: bool) -> Dict[str, Any]:
        state = copy.deepcopy(row.get("state") or {})
        out = {
            **state,
            "item_id": row["item_id"],
            "artifact_id": row.get("artifact_id") or state.get("artifact_id") or "",
        }
        if not include_answers:
            out.pop("answer", None)
            out.pop("accepted", None)
            if out.get("type") == "code":
                out.pop("reference", None)
                out.pop("test_code", None)
                if out.get("mode") != "transcribe":
                    out.pop("target_code", None)
            elif out.get("type") == "derivation":
                if out.get("mode") != "transcribe":
                    out.pop("target_steps", None)
                cloze = set(out.get("cloze") or [])
                for index, step in enumerate(out.get("steps") or []):
                    if not isinstance(step, dict):
                        continue
                    step.pop("expr_py", None)
                    step.pop("accepted", None)
                    if index in cloze:
                        step["expr"] = ""
                        step["justification"] = ""
                        step["cloze"] = True
        return out

    @staticmethod
    def _activity_question_detail(per_question: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove code-controlled free text before durable telemetry/index input."""
        detail: List[Dict[str, Any]] = []
        for grade in per_question:
            safe = copy.deepcopy(grade)
            safe.pop("failure_summary", None)
            detail.append(safe)
        return detail

    def _grade_question(self, question: Dict[str, Any], response: Any) -> Dict[str, Any]:
        qtype = question.get("type")
        points = _points(question.get("points"))
        correct = False
        normalized_response: Dict[str, Any] = {}
        failure_summary = ""
        failure_kind = ""
        timed_out = False
        ungraded_steps: List[int] = []
        ungraded = False
        gradable = True
        scored = True
        mode = ""

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
        elif qtype == "code":
            mode = _clean_text(question.get("mode"), 40).casefold()
            language = _clean_text(question.get("language"), 40).casefold()
            submitted = response.get("code") if isinstance(response, dict) else ""
            normalized_response = {"code": _clean_text(submitted, MAX_CODE_TEXT)}
            if language != "python":
                gradable = False
                scored = False
                ungraded = True
            elif mode == "transcribe":
                correct = _normalize_code(submitted) == _normalize_code(question.get("target_code"))
            elif mode in {"solve", "variant"}:
                starter = _clean_text(question.get("starter"), MAX_CODE_TEXT)
                learner_source = _clean_text(submitted, MAX_CODE_TEXT)
                # B-3 may submit the whole editor buffer (including its starter)
                # or just its learner-owned suffix; accept both without duplicating.
                source = learner_source if _normalize_code(learner_source).startswith(_normalize_code(starter)) else "\n".join(
                    part for part in (starter, learner_source) if part
                )
                result = run_python_grading(source, _clean_text(question.get("test_code"), MAX_CODE_TEXT))
                correct = result["passed"]
                failure_summary = result["failure_summary"]
                failure_kind = _failure_kind(failure_summary)
                timed_out = result["timed_out"]
            else:
                gradable = False
                scored = False
                ungraded = True
        elif qtype == "derivation":
            mode = _clean_text(question.get("check"), 40).casefold()
            submitted_steps = _response_steps(response)
            steps = question.get("steps") if isinstance(question.get("steps"), list) else []
            cloze = [index for index in question.get("cloze") or [] if isinstance(index, int)]
            graded_components = 0
            failed_components = 0
            response_detail: Dict[str, Dict[str, str]] = {}
            for index in cloze:
                if index < 0 or index >= len(steps) or not isinstance(steps[index], dict):
                    continue
                expected = steps[index]
                submitted_step = submitted_steps.get(index, {})
                expression = _clean_text(submitted_step.get("expr"), MAX_CODE_TEXT)
                expression_py = _clean_text(submitted_step.get("expr_py"), MAX_CODE_TEXT)
                response_detail[str(index)] = {"expr": expression, "expr_py": expression_py}
                expected_py = _clean_text(expected.get("expr_py"), MAX_CODE_TEXT)
                if mode == "numeric-equivalence" and expected_py and expression_py:
                    equivalence = check_numeric_equivalence(
                        expected_py,
                        expression_py,
                        _expression_variables(expected_py, expression_py),
                    )
                    if equivalence["needs_human_check"]:
                        ungraded_steps.append(index)
                    else:
                        graded_components += 1
                        if not equivalence["equivalent"]:
                            failed_components += 1
                else:
                    graded_components += 1
                    if not expression or _normalize_expression(expression) != _normalize_expression(expected.get("expr")):
                        failed_components += 1

                accepted = [normalize_short_answer(value) for value in expected.get("accepted") or []]
                accepted = [value for value in accepted if value]
                justification = _clean_text(submitted_step.get("justification"), MAX_TEXT)
                response_detail[str(index)]["justification"] = justification
                if accepted:
                    graded_components += 1
                    if normalize_short_answer(justification) not in accepted:
                        failed_components += 1
                elif index not in ungraded_steps:
                    ungraded_steps.append(index)
            normalized_response = {"steps": response_detail}
            scored = graded_components > 0
            ungraded = not scored
            correct = scored and failed_components == 0

        answer = question.get("answer")
        earned = points if scored and correct else 0
        return {
            "item_id": question["item_id"],
            "prompt": question.get("prompt") or "",
            "type": qtype,
            "correct": correct,
            "earned": earned,
            "points": points,
            "scored": scored,
            "mode": mode,
            "timed_out": timed_out,
            "ungraded": ungraded,
            "gradable": gradable,
            "ungraded_steps": ungraded_steps,
            "failure_summary": failure_summary,
            "failure_kind": failure_kind,
            "answer": answer,
            "accepted": question.get("accepted") or [],
            "explanation": question.get("explanation") or "",
            "tags": question.get("tags") or [],
            "response": normalized_response,
        }
