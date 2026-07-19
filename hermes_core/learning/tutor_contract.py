"""Versioned contracts for resumable learning activities.

This module is deliberately dependency-free.  HTTP adapters and SQLite stores
consume these types; neither layer is allowed to re-derive identity, wire, or
lifecycle rules.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
import unicodedata
from typing import Any, Mapping


TUTOR_CONTRACT_VERSION = 1
MAX_REQUEST_BYTES = 32 * 1024
MAX_GOAL_CODEPOINTS = 4_000
MAX_ANSWER_CODEPOINTS = 8_000
MAX_INPUT_REFS = 16

ACTIVITY_KINDS = frozenset({"tutor", "review", "practice"})
ACTIVITY_STATUSES = frozenset(
    {
        "created",
        "running",
        "waiting_for_learner",
        "interrupted",
        "completed",
        "blocked",
        "cancelled",
    }
)
TERMINAL_ACTIVITY_STATUSES = frozenset({"completed", "blocked", "cancelled"})
ALLOWED_ACTIVITY_TRANSITIONS = frozenset(
    {
        ("created", "running"),
        ("created", "cancelled"),
        ("running", "waiting_for_learner"),
        ("running", "interrupted"),
        ("running", "completed"),
        ("running", "blocked"),
        ("running", "cancelled"),
        ("waiting_for_learner", "running"),
        ("waiting_for_learner", "cancelled"),
        ("interrupted", "running"),
        ("interrupted", "cancelled"),
    }
)

_OPAQUE_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_START_FIELDS = frozenset(
    {
        "schema_version",
        "space_id",
        "activity_kind",
        "idempotency_key",
        "goal",
        "input_refs",
    }
)


class TutorContractError(ValueError):
    """A public or internal Tutor value violated the frozen contract."""

    def __init__(self, message: str, *, reason_code: str = "invalid_request") -> None:
        super().__init__(message)
        self.reason_code = reason_code


class TutorConflictError(TutorContractError):
    """A lifecycle/idempotency/CAS conflict with a stable machine reason."""

    def __init__(self, reason_code: str) -> None:
        super().__init__(reason_code, reason_code=reason_code)


def _nfc(value: str) -> str:
    return unicodedata.normalize("NFC", value)


def _require_mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TutorContractError(f"{field} must be an object")
    if not all(isinstance(key, str) for key in value):
        raise TutorContractError(f"{field} keys must be strings")
    return value


def _require_exact_fields(
    value: Mapping[str, Any], allowed: frozenset[str], field: str
) -> None:
    unknown = set(value) - set(allowed)
    if unknown:
        raise TutorContractError(
            f"{field} contains unknown field: {sorted(unknown)[0]}"
        )


def _require_schema_version(value: Mapping[str, Any]) -> None:
    version = value.get("schema_version")
    if type(version) is not int or version != TUTOR_CONTRACT_VERSION:
        raise TutorContractError("unsupported schema_version")


def _require_opaque_id(value: Any, field: str) -> str:
    if not isinstance(value, str) or not _OPAQUE_ID_RE.fullmatch(value):
        raise TutorContractError(f"{field} is not a valid opaque id")
    return value


def _require_owner_id(value: Any) -> str:
    # Owner identity is host-issued and may use a different alphabet from public
    # opaque IDs. It is nevertheless bounded and cannot be empty.
    if not isinstance(value, str) or not value or len(value) > 256:
        raise TutorContractError("owner_id is invalid")
    return value


def _require_revision(value: Any) -> int:
    if type(value) is not int or value < 0:
        raise TutorContractError("expected_revision must be a non-negative integer")
    return value


def _json_safe_nfc(value: Any, *, path: str = "request") -> Any:
    """Return an NFC-normalized JSON value in the RFC 8785 request subset.

    Tutor request schemas contain integers but no floating-point values.  We
    reject floats instead of relying on runtime-specific number formatting;
    sorted compact UTF-8 JSON is therefore the RFC 8785 representation for the
    accepted subset.
    """

    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, str):
        return _nfc(value)
    if type(value) is int:
        return value
    if isinstance(value, float):
        raise TutorContractError(f"{path} contains unsupported JSON number")
    if isinstance(value, list):
        return [
            _json_safe_nfc(item, path=f"{path}[{index}]")
            for index, item in enumerate(value)
        ]
    if isinstance(value, Mapping):
        normalized: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise TutorContractError(f"{path} contains a non-string key")
            normalized_key = _nfc(key)
            if normalized_key in normalized:
                raise TutorContractError(f"{path} contains duplicate normalized keys")
            normalized[normalized_key] = _json_safe_nfc(
                item, path=f"{path}.{normalized_key}"
            )
        return normalized
    raise TutorContractError(f"{path} contains a non-JSON value")


def canonical_json_bytes(value: Any) -> bytes:
    normalized = _json_safe_nfc(value)
    return json.dumps(
        normalized,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _require_request_size(value: Mapping[str, Any]) -> None:
    if len(canonical_json_bytes(value)) > MAX_REQUEST_BYTES:
        raise TutorContractError("request exceeds 32 KiB")


def _normalize_input_refs(value: Any) -> tuple[dict[str, Any], ...]:
    if not isinstance(value, list) or len(value) > MAX_INPUT_REFS:
        raise TutorContractError("input_refs must be a list with at most 16 entries")
    normalized: list[dict[str, Any]] = []
    for index, raw in enumerate(value):
        ref = _require_mapping(raw, f"input_refs[{index}]")
        _require_exact_fields(
            ref, frozenset({"kind", "id", "version", "sha256"}), f"input_refs[{index}]"
        )
        kind = ref.get("kind")
        if kind not in {"artifact", "item", "source"}:
            raise TutorContractError(f"input_refs[{index}].kind is invalid")
        item: dict[str, Any] = {
            "kind": kind,
            "id": _require_opaque_id(ref.get("id"), f"input_refs[{index}].id"),
        }
        if "version" in ref:
            version = ref["version"]
            if type(version) is not int or version < 0:
                raise TutorContractError(
                    f"input_refs[{index}].version must be a non-negative integer"
                )
            item["version"] = version
        if "sha256" in ref:
            sha256 = ref["sha256"]
            if not isinstance(sha256, str) or not _SHA256_RE.fullmatch(sha256):
                raise TutorContractError(
                    f"input_refs[{index}].sha256 must be lowercase hex"
                )
            item["sha256"] = sha256
        normalized.append(item)
    return tuple(normalized)


def _normalize_start_body(body: Mapping[str, Any]) -> dict[str, Any]:
    request = _require_mapping(body, "start request")
    if "owner_id" in request:
        raise TutorContractError("public start request must not contain owner_id")
    _require_exact_fields(request, _START_FIELDS, "start request")
    _require_schema_version(request)
    _require_request_size(request)
    space_id = _require_opaque_id(request.get("space_id"), "space_id")
    activity_kind = request.get("activity_kind")
    if activity_kind not in ACTIVITY_KINDS:
        raise TutorContractError("activity_kind is invalid")
    idempotency_key = _require_opaque_id(
        request.get("idempotency_key"), "idempotency_key"
    )
    goal = request.get("goal")
    if not isinstance(goal, str) or not goal or len(goal) > MAX_GOAL_CODEPOINTS:
        raise TutorContractError("goal must contain 1 to 4000 Unicode code points")
    normalized = {
        "schema_version": TUTOR_CONTRACT_VERSION,
        "space_id": space_id,
        "activity_kind": activity_kind,
        "idempotency_key": idempotency_key,
        "goal": _nfc(goal),
        "input_refs": list(_normalize_input_refs(request.get("input_refs"))),
    }
    # Validate the normalized representation too; normalization must never grow
    # a request past the wire cap unnoticed.
    _require_request_size(normalized)
    return normalized


def canonical_request_fingerprint(body: Mapping[str, Any]) -> str:
    normalized = _normalize_start_body(body)
    fingerprint_body = dict(normalized)
    fingerprint_body.pop("idempotency_key")
    return hashlib.sha256(canonical_json_bytes(fingerprint_body)).hexdigest()


@dataclass(frozen=True)
class LearningActivityKeyV1:
    owner_id: str
    space_id: str
    activity_kind: str
    activity_id: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "owner_id", _require_owner_id(self.owner_id))
        object.__setattr__(self, "space_id", _require_opaque_id(self.space_id, "space_id"))
        if self.activity_kind not in ACTIVITY_KINDS:
            raise TutorContractError("activity_kind is invalid")
        object.__setattr__(
            self, "activity_id", _require_opaque_id(self.activity_id, "activity_id")
        )

    def as_tuple(self) -> tuple[str, str, str, str]:
        return (self.owner_id, self.space_id, self.activity_kind, self.activity_id)


@dataclass(frozen=True)
class LearningActivityStartV1:
    key: LearningActivityKeyV1
    idempotency_key: str
    goal: str
    input_refs: tuple[dict[str, Any], ...]
    request_fingerprint: str
    schema_version: int = TUTOR_CONTRACT_VERSION

    @property
    def idempotency_namespace(self) -> tuple[str, str, str, str]:
        return (
            self.key.owner_id,
            self.key.space_id,
            self.key.activity_kind,
            self.idempotency_key,
        )


def validate_start_request(
    body: Mapping[str, Any], *, owner_id: str, activity_id: str
) -> LearningActivityStartV1:
    normalized = _normalize_start_body(body)
    key = LearningActivityKeyV1(
        owner_id=owner_id,
        space_id=normalized["space_id"],
        activity_kind=normalized["activity_kind"],
        activity_id=activity_id,
    )
    return LearningActivityStartV1(
        key=key,
        idempotency_key=normalized["idempotency_key"],
        goal=normalized["goal"],
        input_refs=tuple(normalized["input_refs"]),
        request_fingerprint=canonical_request_fingerprint(normalized),
    )


@dataclass(frozen=True)
class LearningActivityResumeV1:
    space_id: str
    expected_revision: int
    mode: str
    interrupt_id: str | None = None
    answer: dict[str, Any] | None = None
    schema_version: int = TUTOR_CONTRACT_VERSION


def _normalize_answer(value: Any) -> dict[str, Any]:
    answer = _require_mapping(value, "answer")
    answer_type = answer.get("type")
    if answer_type in {"free_text", "step"}:
        _require_exact_fields(answer, frozenset({"type", "text"}), "answer")
        text = answer.get("text")
        if not isinstance(text, str) or len(text) > MAX_ANSWER_CODEPOINTS:
            raise TutorContractError("answer text exceeds 8000 Unicode code points")
        return {"type": answer_type, "text": _nfc(text)}
    if answer_type == "choice":
        _require_exact_fields(answer, frozenset({"type", "selected"}), "answer")
        selected = answer.get("selected")
        if not isinstance(selected, list):
            raise TutorContractError("answer selected must be a list")
        return {
            "type": "choice",
            "selected": [
                _require_opaque_id(item, f"answer.selected[{index}]")
                for index, item in enumerate(selected)
            ],
        }
    raise TutorContractError("answer type is invalid")


def validate_resume_request(body: Mapping[str, Any]) -> LearningActivityResumeV1:
    request = _require_mapping(body, "resume request")
    if "owner_id" in request:
        raise TutorContractError("public resume request must not contain owner_id")
    _require_schema_version(request)
    _require_request_size(request)
    mode = request.get("mode")
    common = {
        "space_id": _require_opaque_id(request.get("space_id"), "space_id"),
        "expected_revision": _require_revision(request.get("expected_revision")),
    }
    if mode == "recover":
        _require_exact_fields(
            request,
            frozenset({"schema_version", "space_id", "expected_revision", "mode"}),
            "recover request",
        )
        return LearningActivityResumeV1(mode="recover", **common)
    if mode == "answer":
        _require_exact_fields(
            request,
            frozenset(
                {
                    "schema_version",
                    "space_id",
                    "expected_revision",
                    "mode",
                    "interrupt_id",
                    "answer",
                }
            ),
            "answer request",
        )
        return LearningActivityResumeV1(
            mode="answer",
            interrupt_id=_require_opaque_id(request.get("interrupt_id"), "interrupt_id"),
            answer=_normalize_answer(request.get("answer")),
            **common,
        )
    raise TutorContractError("resume mode is invalid")


@dataclass(frozen=True)
class LearningActivityCancelV1:
    space_id: str
    expected_revision: int
    schema_version: int = TUTOR_CONTRACT_VERSION


def validate_cancel_request(body: Mapping[str, Any]) -> LearningActivityCancelV1:
    request = _require_mapping(body, "cancel request")
    if "owner_id" in request:
        raise TutorContractError("public cancel request must not contain owner_id")
    _require_exact_fields(
        request,
        frozenset({"schema_version", "space_id", "expected_revision"}),
        "cancel request",
    )
    _require_schema_version(request)
    _require_request_size(request)
    return LearningActivityCancelV1(
        space_id=_require_opaque_id(request.get("space_id"), "space_id"),
        expected_revision=_require_revision(request.get("expected_revision")),
    )


@dataclass(frozen=True)
class LearningInterruptV1:
    interrupt_id: str
    key: LearningActivityKeyV1
    checkpoint_revision: int
    prompt: dict[str, Any]
    expected_input: str
    created_at: str
    kind: str = "learner_check"
    schema_version: int = TUTOR_CONTRACT_VERSION

    def __post_init__(self) -> None:
        _require_opaque_id(self.interrupt_id, "interrupt_id")
        if self.kind != "learner_check":
            raise TutorContractError("interrupt kind is invalid")
        _require_revision(self.checkpoint_revision)
        if self.expected_input not in {"free_text", "choice", "step"}:
            raise TutorContractError("expected_input is invalid")
        _require_mapping(self.prompt, "interrupt prompt")

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "interrupt_id": self.interrupt_id,
            "kind": self.kind,
            "space_id": self.key.space_id,
            "activity_kind": self.key.activity_kind,
            "activity_id": self.key.activity_id,
            "checkpoint_revision": self.checkpoint_revision,
            "prompt": _json_safe_nfc(self.prompt, path="interrupt.prompt"),
            "expected_input": self.expected_input,
            "created_at": self.created_at,
        }


@dataclass(frozen=True)
class LearningActivitySnapshotV1:
    key: LearningActivityKeyV1
    status: str
    revision: int
    label: str
    created_at: str
    updated_at: str
    latest_output: dict[str, Any] | None = None
    interrupt: LearningInterruptV1 | None = None
    terminal: dict[str, Any] | None = None
    schema_version: int = TUTOR_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if self.status not in ACTIVITY_STATUSES:
            raise TutorContractError("activity status is invalid")
        _require_revision(self.revision)

    def to_public_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "schema_version": self.schema_version,
            "activity_id": self.key.activity_id,
            "space_id": self.key.space_id,
            "activity_kind": self.key.activity_kind,
            "status": self.status,
            "revision": self.revision,
            "label": self.label,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
        if self.latest_output is not None:
            result["latest_output"] = _json_safe_nfc(
                self.latest_output, path="snapshot.latest_output"
            )
        if self.interrupt is not None:
            result["interrupt"] = self.interrupt.to_public_dict()
        if self.terminal is not None:
            result["terminal"] = _json_safe_nfc(
                self.terminal, path="snapshot.terminal"
            )
        return result


def is_allowed_activity_transition(source: str, destination: str) -> bool:
    return (source, destination) in ALLOWED_ACTIVITY_TRANSITIONS


__all__ = [
    "ACTIVITY_KINDS",
    "ACTIVITY_STATUSES",
    "ALLOWED_ACTIVITY_TRANSITIONS",
    "TERMINAL_ACTIVITY_STATUSES",
    "LearningActivityCancelV1",
    "LearningActivityKeyV1",
    "LearningActivityResumeV1",
    "LearningActivitySnapshotV1",
    "LearningActivityStartV1",
    "LearningInterruptV1",
    "TutorConflictError",
    "TutorContractError",
    "canonical_json_bytes",
    "canonical_request_fingerprint",
    "is_allowed_activity_transition",
    "validate_cancel_request",
    "validate_resume_request",
    "validate_start_request",
]
