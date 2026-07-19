"""Learning Output Envelope v1 — the single source of truth for STUDY.

This module owns the *frozen vocabulary* (artifact kinds, lifecycle statuses,
allowed transitions, review modes/statuses), the per-kind payload schemas
(including the quiz discriminated union), and the deterministic validator that
the Output Writer, Planner registry, capability registry, and (later) Web types
all import from here. Nothing else re-declares these values.

Design: docs/superpowers/specs/2026-07-01-study-four-layer-learning-pipeline-design.md §6.

Validation here is *deterministic and dependency-free* on purpose: it is the
write-time gate for AI-generated content (which is always persisted as
``draft``). Per-kind *semantic* review is a later milestone, never here.
"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Mapping


# --------------------------------------------------------------------------- #
# Frozen vocabulary — the ONLY source of these values.
# --------------------------------------------------------------------------- #

CONTRACT_VERSION: int = 1

KINDS: frozenset = frozenset(
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

# Artifact lifecycle. AI content starts at ``draft``; trust-boundary transitions
# (activate/reject/archive) are enforced by the Output Writer / trusted callers,
# never by a model tool.
LIFECYCLE_STATUSES: frozenset = frozenset({"draft", "active", "rejected", "archived"})
INITIAL_STATUS: str = "draft"
ALLOWED_TRANSITIONS: frozenset = frozenset(
    {
        ("draft", "active"),
        ("draft", "rejected"),
        ("active", "archived"),
    }
)

REVIEW_MODES: frozenset = frozenset({"deterministic", "semantic"})
REVIEW_STATUSES: frozenset = frozenset({"pending", "passed", "failed"})

# Default review mode per kind (design §6 table). A plain dict so callers can
# read it directly; treat as read-only.
DEFAULT_REVIEW_MODE: Dict[str, str] = {
    "student_state": "deterministic",
    "knowledge_base": "semantic",
    "learning_plan": "semantic",
    "resource_pack": "semantic",
    "flashcard_deck": "semantic",
    "quiz": "semantic",
    "tutoring_note": "deterministic",
    "evaluation": "deterministic",
}

# Size limits — cheap deterministic guards, not policy. Keep generous.
MAX_TITLE_LEN: int = 300
MAX_STR_LEN: int = 20_000
MAX_SOURCE_REFS: int = 200
MAX_LIST_ITEMS: int = 1_000
MAX_QUIZ_QUESTIONS: int = 500
MAX_CHOICE_OPTIONS: int = 26
MAX_ENVELOPE_BYTES: int = 512 * 1024

QUIZ_QUESTION_TYPES: frozenset = frozenset({"choice", "true_false", "short_answer"})


class ContractError(ValueError):
    """Raised when a Learning Output Envelope or payload violates the contract."""


# --------------------------------------------------------------------------- #
# Envelope object
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class LearningOutputEnvelope:
    """A validated ``LearningOutputEnvelope v1``.

    Produced only by :func:`validate_envelope`. ``payload``/``source_refs``/
    ``review`` are owned copies; use :meth:`to_dict` for a fresh serializable
    snapshot.
    """

    version: int
    kind: str
    space_id: str
    title: str
    source_refs: List[Any]
    payload: Dict[str, Any]
    review: Dict[str, str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "kind": self.kind,
            "space_id": self.space_id,
            "title": self.title,
            "source_refs": copy.deepcopy(self.source_refs),
            "payload": copy.deepcopy(self.payload),
            "review": dict(self.review),
        }


# --------------------------------------------------------------------------- #
# Small validation helpers
# --------------------------------------------------------------------------- #

def _mapping(value: Any, ctx: str) -> Dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ContractError(f"{ctx} must be an object")
    return dict(value)


def _req_str(obj: Mapping[str, Any], key: str, ctx: str) -> str:
    val = obj.get(key)
    if not isinstance(val, str) or not val.strip():
        raise ContractError(f"{ctx}: '{key}' must be a non-empty string")
    if len(val) > MAX_STR_LEN:
        raise ContractError(f"{ctx}: '{key}' exceeds {MAX_STR_LEN} chars")
    return val


def _opt_str(obj: Mapping[str, Any], key: str, ctx: str) -> None:
    if key in obj:
        _req_str(obj, key, ctx)


def _req_nonempty_list(obj: Mapping[str, Any], key: str, ctx: str) -> List[Any]:
    val = obj.get(key)
    if not isinstance(val, list) or not val:
        raise ContractError(f"{ctx}: '{key}' must be a non-empty list")
    if len(val) > MAX_LIST_ITEMS:
        raise ContractError(f"{ctx}: '{key}' exceeds {MAX_LIST_ITEMS} items")
    return val


def _opt_str_list(obj: Mapping[str, Any], key: str, ctx: str) -> None:
    if key not in obj:
        return
    val = obj[key]
    if not isinstance(val, list) or len(val) > MAX_LIST_ITEMS:
        raise ContractError(f"{ctx}: '{key}' must be a list")
    for i, item in enumerate(val):
        if not isinstance(item, str):
            raise ContractError(f"{ctx}: '{key}[{i}]' must be a string")


def _forbid_keys(obj: Mapping[str, Any], keys: frozenset, ctx: str) -> None:
    banned = keys & set(obj)
    if banned:
        raise ContractError(
            f"{ctx}: forbidden field(s) {sorted(banned)} — this kind never "
            f"carries fixed ability/capability labels"
        )


# --------------------------------------------------------------------------- #
# Per-kind payload validators
# --------------------------------------------------------------------------- #

# student_state / evaluation must never fossilize a learner into fixed labels.
_FIXED_LABEL_KEYS: frozenset = frozenset(
    {"capability_labels", "ability_labels", "personality", "personality_labels"}
)


def _opt_evidence_refs(obj: Mapping[str, Any], ctx: str) -> None:
    refs = obj.get("evidence_refs")
    if refs is None:
        return
    if not isinstance(refs, list) or len(refs) > MAX_SOURCE_REFS:
        raise ContractError(f"{ctx}: 'evidence_refs' must be a bounded list")
    for i, ref in enumerate(refs):
        rctx = f"{ctx}.evidence_refs[{i}]"
        rm = _mapping(ref, rctx)
        for key, value in rm.items():
            if not isinstance(key, str) or not isinstance(value, str):
                raise ContractError(f"{rctx}: keys and values must be strings")
            if len(key) > MAX_STR_LEN or len(value) > MAX_STR_LEN:
                raise ContractError(
                    f"{rctx}: keys and values must not exceed {MAX_STR_LEN} chars"
                )


def _v_student_state(p: Mapping[str, Any]) -> None:
    _forbid_keys(p, _FIXED_LABEL_KEYS, "student_state")
    if "preferences" in p and not isinstance(p["preferences"], (dict, list)):
        raise ContractError("student_state: 'preferences' must be an object or list")
    _opt_str_list(p, "goals", "student_state")
    _opt_str_list(p, "constraints", "student_state")
    # M1: optional multi-dimensional profile. Each dimension is a *dynamic,
    # editable snapshot* (level 0-5 = current familiarity/engagement, not a
    # fixed ability judgment) plus a free-text summary. Backward-compatible:
    # older student_state without 'dimensions' stays valid.
    dims = p.get("dimensions")
    if dims is not None:
        if not isinstance(dims, list):
            raise ContractError("student_state: 'dimensions' must be a list")
        for i, d in enumerate(dims):
            ctx = f"student_state.dimensions[{i}]"
            dm = _mapping(d, ctx)
            _req_str(dm, "key", ctx)
            _req_str(dm, "label", ctx)
            if "level" in dm:
                lvl = dm["level"]
                if isinstance(lvl, bool) or not isinstance(lvl, (int, float)):
                    raise ContractError(f"{ctx}: 'level' must be a number (0-5)")
                if lvl < 0 or lvl > 5:
                    raise ContractError(f"{ctx}: 'level' must be within 0-5")
            _opt_str(dm, "summary", ctx)


def _v_knowledge_base(p: Mapping[str, Any]) -> None:
    concepts = _req_nonempty_list(p, "concepts", "knowledge_base")
    for i, c in enumerate(concepts):
        ctx = f"knowledge_base.concepts[{i}]"
        cm = _mapping(c, ctx)
        _req_str(cm, "term", ctx)
        _req_str(cm, "explanation", ctx)


def _v_learning_plan(p: Mapping[str, Any]) -> None:
    _opt_str_list(p, "goals", "learning_plan")
    phases = _req_nonempty_list(p, "phases", "learning_plan")
    for i, ph in enumerate(phases):
        ctx = f"learning_plan.phases[{i}]"
        pm = _mapping(ph, ctx)
        _req_str(pm, "title", ctx)
        tasks = _req_nonempty_list(pm, "tasks", ctx)
        for j, t in enumerate(tasks):
            tctx = f"{ctx}.tasks[{j}]"
            tm = _mapping(t, tctx)
            _req_str(tm, "title", tctx)
            if "order" in tm and not isinstance(tm["order"], int):
                raise ContractError(f"{tctx}: 'order' must be an integer")
            _opt_str(tm, "done_when", tctx)


# resource_pack subtypes (M3 备课组). "doc" is the implicit default when a
# pack omits the discriminator; older packs without it remain valid.
_RESOURCE_TYPES: frozenset = frozenset({"doc", "mindmap", "reading", "video_script"})


def _v_resource_pack(p: Mapping[str, Any]) -> None:
    resources = _req_nonempty_list(p, "resources", "resource_pack")
    # Optional discriminator (M3): lets 备课组 produce typed resources
    # (mindmap / reading / video_script) while old packs (no type) stay valid.
    rtype = p.get("resource_type")
    if rtype is not None and rtype not in _RESOURCE_TYPES:
        raise ContractError(
            f"resource_pack: 'resource_type' must be one of {sorted(_RESOURCE_TYPES)}"
        )
    for i, r in enumerate(resources):
        ctx = f"resource_pack.resources[{i}]"
        rm = _mapping(r, ctx)
        _req_str(rm, "title", ctx)
        _req_str(rm, "purpose", ctx)
        _opt_str(rm, "credibility", ctx)
        r_rtype = rm.get("resource_type")
        if r_rtype is not None and r_rtype not in _RESOURCE_TYPES:
            raise ContractError(
                f"{ctx}: 'resource_type' must be one of {sorted(_RESOURCE_TYPES)}"
            )


def _v_flashcard_deck(p: Mapping[str, Any]) -> None:
    cards = _req_nonempty_list(p, "cards", "flashcard_deck")
    for i, c in enumerate(cards):
        ctx = f"flashcard_deck.cards[{i}]"
        cm = _mapping(c, ctx)
        _req_str(cm, "front", ctx)
        _req_str(cm, "back", ctx)
        _opt_str_list(cm, "tags", ctx)


def _v_quiz_choice(q: Mapping[str, Any], ctx: str) -> None:
    options = q.get("options")
    if not isinstance(options, list) or not (2 <= len(options) <= MAX_CHOICE_OPTIONS):
        raise ContractError(
            f"{ctx}: choice 'options' must be a list of 2..{MAX_CHOICE_OPTIONS}"
        )
    for i, opt in enumerate(options):
        if not isinstance(opt, str):
            raise ContractError(f"{ctx}: option[{i}] must be a string")
    answer = q.get("answer")
    indices = answer if isinstance(answer, list) else [answer]
    if not indices:
        raise ContractError(f"{ctx}: choice 'answer' is required")
    for a in indices:
        if isinstance(a, bool) or not isinstance(a, int) or not (0 <= a < len(options)):
            raise ContractError(
                f"{ctx}: choice 'answer' index out of range 0..{len(options) - 1}"
            )


def _v_quiz_true_false(q: Mapping[str, Any], ctx: str) -> None:
    if not isinstance(q.get("answer"), bool):
        raise ContractError(f"{ctx}: true_false 'answer' must be a boolean")


def _v_quiz_short_answer(q: Mapping[str, Any], ctx: str) -> None:
    has_answer = isinstance(q.get("answer"), str) and q["answer"].strip()
    accepted = q.get("accepted")
    has_accepted = (
        isinstance(accepted, list)
        and accepted
        and all(isinstance(a, str) for a in accepted)
    )
    if not (has_answer or has_accepted):
        raise ContractError(
            f"{ctx}: short_answer needs 'answer' (string) or 'accepted' (list of strings)"
        )


_QUIZ_TYPE_VALIDATORS: Dict[str, Callable[[Mapping[str, Any], str], None]] = {
    "choice": _v_quiz_choice,
    "true_false": _v_quiz_true_false,
    "short_answer": _v_quiz_short_answer,
}


def _v_quiz(p: Mapping[str, Any]) -> None:
    questions = _req_nonempty_list(p, "questions", "quiz")
    if len(questions) > MAX_QUIZ_QUESTIONS:
        raise ContractError(f"quiz: exceeds {MAX_QUIZ_QUESTIONS} questions")
    for i, q in enumerate(questions):
        ctx = f"quiz.questions[{i}]"
        qm = _mapping(q, ctx)
        qtype = qm.get("type")
        if qtype not in QUIZ_QUESTION_TYPES:
            raise ContractError(
                f"{ctx}: unknown question type {qtype!r}; "
                f"expected one of {sorted(QUIZ_QUESTION_TYPES)}"
            )
        _req_str(qm, "prompt", ctx)
        _QUIZ_TYPE_VALIDATORS[qtype](qm, ctx)
        _opt_str(qm, "explanation", ctx)


def _v_tutoring_note(p: Mapping[str, Any]) -> None:
    _req_str(p, "goal", "tutoring_note")
    _req_nonempty_list(p, "hints", "tutoring_note")
    _opt_str_list(p, "hints", "tutoring_note")
    _opt_str_list(p, "misconceptions", "tutoring_note")
    _opt_str_list(p, "next_steps", "tutoring_note")


def _v_evaluation(p: Mapping[str, Any]) -> None:
    _forbid_keys(p, _FIXED_LABEL_KEYS, "evaluation")
    _req_nonempty_list(p, "observations", "evaluation")
    _opt_str_list(p, "observations", "evaluation")
    _opt_str_list(p, "weak_points", "evaluation")
    _opt_str_list(p, "suggestions", "evaluation")
    _opt_evidence_refs(p, "evaluation")


_PAYLOAD_VALIDATORS: Dict[str, Callable[[Mapping[str, Any]], None]] = {
    "student_state": _v_student_state,
    "knowledge_base": _v_knowledge_base,
    "learning_plan": _v_learning_plan,
    "resource_pack": _v_resource_pack,
    "flashcard_deck": _v_flashcard_deck,
    "quiz": _v_quiz,
    "tutoring_note": _v_tutoring_note,
    "evaluation": _v_evaluation,
}

# Every kind must have a validator; guards against vocabulary drift.
assert set(_PAYLOAD_VALIDATORS) == set(KINDS)
assert set(DEFAULT_REVIEW_MODE) == set(KINDS)


# --------------------------------------------------------------------------- #
# Per-kind migration hook
# --------------------------------------------------------------------------- #

# One ordered list of (payload) migration steps per kind, keyed by the version
# they migrate *from*. Empty in v1 — the hook exists so future schema bumps
# never need to touch the Writer or the store.
_PAYLOAD_MIGRATIONS: Dict[str, Dict[int, Callable[[Dict[str, Any]], Dict[str, Any]]]] = {
    kind: {} for kind in KINDS
}


def migrate_payload(kind: str, payload: Dict[str, Any], from_version: int) -> Dict[str, Any]:
    """Apply per-kind payload migrations from ``from_version`` to current.

    Identity in v1. Raises for unknown/unsupported versions.
    """
    if kind not in KINDS:
        raise ContractError(f"unknown kind: {kind!r}")
    if not isinstance(from_version, int) or from_version < 1:
        raise ContractError(f"invalid source version: {from_version!r}")
    if from_version > CONTRACT_VERSION:
        raise ContractError(
            f"cannot migrate {kind} from future version {from_version}"
        )
    steps = _PAYLOAD_MIGRATIONS[kind]
    out = copy.deepcopy(payload)
    for v in range(from_version, CONTRACT_VERSION):
        step = steps.get(v)
        if step is not None:
            out = step(out)
    return out


def migrate_to_current(data: Mapping[str, Any]) -> Dict[str, Any]:
    """Migrate a whole envelope dict to :data:`CONTRACT_VERSION`.

    Version ``CONTRACT_VERSION`` passes through; earlier versions run their
    per-kind payload migrations; future/invalid versions raise.
    """
    d = _mapping(data, "envelope")
    version = d.get("version")
    if version == CONTRACT_VERSION:
        return copy.deepcopy(d)
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        raise ContractError(f"invalid contract version: {version!r}")
    if version > CONTRACT_VERSION:
        raise ContractError(
            f"cannot migrate from future contract version {version}"
        )
    out = copy.deepcopy(d)
    kind = out.get("kind")
    if isinstance(out.get("payload"), Mapping):
        out["payload"] = migrate_payload(kind, dict(out["payload"]), version)
    out["version"] = CONTRACT_VERSION
    return out


# --------------------------------------------------------------------------- #
# Public helpers
# --------------------------------------------------------------------------- #

def is_allowed_transition(src: str, dst: str) -> bool:
    """True iff ``src -> dst`` is an allowed lifecycle transition."""
    return (src, dst) in ALLOWED_TRANSITIONS


def default_review_mode(kind: str) -> str:
    """Default review mode for ``kind`` (design §6)."""
    try:
        return DEFAULT_REVIEW_MODE[kind]
    except KeyError:
        raise ContractError(f"unknown kind: {kind!r}")


def _normalize_review(review: Any, kind: str) -> Dict[str, str]:
    if review is None:
        return {"mode": default_review_mode(kind), "status": "pending"}
    rm = _mapping(review, "review")
    mode = rm.get("mode", default_review_mode(kind))
    status = rm.get("status", "pending")
    if mode not in REVIEW_MODES:
        raise ContractError(
            f"review.mode {mode!r} not in {sorted(REVIEW_MODES)}"
        )
    if status not in REVIEW_STATUSES:
        raise ContractError(
            f"review.status {status!r} not in {sorted(REVIEW_STATUSES)}"
        )
    return {"mode": mode, "status": status}


def _validate_source_refs(refs: Any) -> List[Any]:
    if not isinstance(refs, list):
        raise ContractError("source_refs must be a list")
    if len(refs) > MAX_SOURCE_REFS:
        raise ContractError(f"source_refs exceeds {MAX_SOURCE_REFS} entries")
    for i, ref in enumerate(refs):
        if not isinstance(ref, (str, dict)):
            raise ContractError(f"source_refs[{i}] must be a string or object")
    return copy.deepcopy(refs)


def _json_size_bytes(value: Any, label: str) -> int:
    try:
        return len(json.dumps(value, ensure_ascii=False).encode("utf-8"))
    except (TypeError, ValueError):
        raise ContractError(f"{label} is not JSON-serializable")


def validate_envelope(data: Mapping[str, Any]) -> LearningOutputEnvelope:
    """Validate a ``LearningOutputEnvelope v1`` and return an owned copy.

    Deterministic and side-effect free: never mutates ``data``, never calls an
    LLM. Raises :class:`ContractError` on any violation.
    """
    d = _mapping(data, "envelope")

    version = d.get("version")
    if version != CONTRACT_VERSION:
        raise ContractError(
            f"unsupported envelope version {version!r}; expected {CONTRACT_VERSION}"
        )

    kind = d.get("kind")
    if kind not in KINDS:
        raise ContractError(
            f"unknown kind {kind!r}; expected one of {sorted(KINDS)}"
        )

    space_id = d.get("space_id")
    if not isinstance(space_id, str) or not space_id.strip():
        raise ContractError("space_id must be a non-empty string")

    title = d.get("title")
    if not isinstance(title, str) or not title.strip():
        raise ContractError("title must be a non-empty string")
    if len(title) > MAX_TITLE_LEN:
        raise ContractError(f"title exceeds {MAX_TITLE_LEN} chars")

    source_refs = _validate_source_refs(d.get("source_refs", []))

    payload = d.get("payload")
    if not isinstance(payload, Mapping):
        raise ContractError("payload must be an object")
    payload = dict(payload)

    _PAYLOAD_VALIDATORS[kind](payload)

    review = _normalize_review(d.get("review"), kind)
    envelope = {
        "version": CONTRACT_VERSION,
        "kind": kind,
        "space_id": space_id,
        "title": title,
        "source_refs": source_refs,
        "payload": payload,
        "review": review,
    }

    size = _json_size_bytes(envelope, "envelope")
    if size > MAX_ENVELOPE_BYTES:
        raise ContractError(
            f"envelope {size} bytes exceeds cap {MAX_ENVELOPE_BYTES}"
        )

    return LearningOutputEnvelope(
        version=CONTRACT_VERSION,
        kind=kind,
        space_id=space_id,
        title=title,
        source_refs=source_refs,
        payload=copy.deepcopy(payload),
        review=review,
    )
