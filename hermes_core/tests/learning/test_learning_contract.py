"""Tests for learning/learning_contract.py — the single source of truth for the
STUDY Learning Output Envelope v1: frozen vocabulary, per-kind payload schemas
(including the quiz discriminated union), lifecycle transitions, default review
modes, and the per-kind migration hook.

These tests pin the contract so Planner / Output Writer / capability registry
can import the same constants and validators instead of re-deriving them.
"""

import copy

import pytest

from learning.learning_contract import (
    CONTRACT_VERSION,
    KINDS,
    LIFECYCLE_STATUSES,
    INITIAL_STATUS,
    ALLOWED_TRANSITIONS,
    REVIEW_MODES,
    REVIEW_STATUSES,
    DEFAULT_REVIEW_MODE,
    ContractError,
    LearningOutputEnvelope,
    validate_envelope,
    is_allowed_transition,
    default_review_mode,
    migrate_to_current,
)


# --------------------------------------------------------------------------- #
# Frozen vocabulary — the contract is the *only* source of these values.
# --------------------------------------------------------------------------- #

def test_kinds_are_exactly_the_v1_set():
    assert KINDS == frozenset(
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


def test_lifecycle_vocabulary_is_frozen():
    assert LIFECYCLE_STATUSES == frozenset(
        {"draft", "active", "rejected", "archived"}
    )
    assert INITIAL_STATUS == "draft"


def test_review_vocabulary_is_frozen():
    assert REVIEW_MODES == frozenset({"deterministic", "semantic"})
    assert REVIEW_STATUSES == frozenset({"pending", "passed", "failed"})


def test_contract_version_is_one():
    assert CONTRACT_VERSION == 1


def test_vocabulary_constants_are_immutable():
    # frozenset has no mutating API; guard against accidental swap to a set.
    for const in (KINDS, LIFECYCLE_STATUSES, REVIEW_MODES, REVIEW_STATUSES):
        assert isinstance(const, frozenset)


# --------------------------------------------------------------------------- #
# Lifecycle transitions
# --------------------------------------------------------------------------- #

def test_allowed_transitions_are_exactly_the_design_set():
    assert ALLOWED_TRANSITIONS == frozenset(
        {
            ("draft", "active"),
            ("draft", "rejected"),
            ("active", "archived"),
        }
    )


@pytest.mark.parametrize(
    "src,dst",
    [("draft", "active"), ("draft", "rejected"), ("active", "archived")],
)
def test_is_allowed_transition_accepts_valid(src, dst):
    assert is_allowed_transition(src, dst) is True


@pytest.mark.parametrize(
    "src,dst",
    [
        ("active", "draft"),      # no going back to draft
        ("archived", "active"),   # archived is terminal
        ("draft", "archived"),    # must go active first
        ("rejected", "active"),   # rejected is terminal
        ("draft", "draft"),       # no self-loop
        ("active", "rejected"),   # rejection only from draft
        ("draft", "bogus"),       # unknown status
    ],
)
def test_is_allowed_transition_rejects_invalid(src, dst):
    assert is_allowed_transition(src, dst) is False


# --------------------------------------------------------------------------- #
# Default review mode per kind (design §6 table)
# --------------------------------------------------------------------------- #

def test_default_review_mode_matches_design_table():
    expected = {
        "student_state": "deterministic",
        "knowledge_base": "semantic",
        "learning_plan": "semantic",
        "resource_pack": "semantic",
        "flashcard_deck": "semantic",
        "quiz": "semantic",
        "tutoring_note": "deterministic",
        "evaluation": "deterministic",
    }
    assert DEFAULT_REVIEW_MODE == expected
    for kind, mode in expected.items():
        assert default_review_mode(kind) == mode


def test_default_review_mode_covers_every_kind():
    assert set(DEFAULT_REVIEW_MODE) == set(KINDS)


# --------------------------------------------------------------------------- #
# Valid payload samples per kind
# --------------------------------------------------------------------------- #

def _envelope(kind, payload, **overrides):
    env = {
        "version": 1,
        "kind": kind,
        "space_id": "course-space-1",
        "title": f"{kind} sample",
        "source_refs": [],
        "payload": payload,
    }
    env.update(overrides)
    return env


VALID_PAYLOADS = {
    "student_state": {
        "goals": ["Pass the algebra final"],
        "preferences": {"pace": "steady"},
        "constraints": ["30 minutes per day"],
    },
    "knowledge_base": {
        "concepts": [
            {
                "term": "Derivative",
                "explanation": "Rate of change of a function.",
                "needs_verification": False,
            }
        ]
    },
    "learning_plan": {
        "goals": ["Understand limits"],
        "phases": [
            {
                "title": "Foundations",
                "tasks": [{"title": "Review functions", "order": 1}],
            }
        ],
    },
    "resource_pack": {
        "resources": [
            {
                "title": "Khan Academy Calculus",
                "purpose": "Video primer on limits",
                "credibility": "Reputable OER",
            }
        ]
    },
    "flashcard_deck": {
        "cards": [
            {"front": "2+2", "back": "4", "tags": ["arithmetic"]},
        ]
    },
    "quiz": {
        "questions": [
            {
                "type": "choice",
                "prompt": "Pick the prime.",
                "options": ["4", "6", "7"],
                "answer": 2,
                "explanation": "7 has no divisors other than 1 and itself.",
            },
            {
                "type": "true_false",
                "prompt": "0 is even.",
                "answer": True,
            },
            {
                "type": "short_answer",
                "prompt": "Capital of France?",
                "answer": "Paris",
            },
        ]
    },
    "tutoring_note": {
        "goal": "Unblock the student on integration by parts",
        "hints": ["Identify u and dv", "Differentiate u"],
        "misconceptions": ["Swapping u and dv arbitrarily"],
        "next_steps": ["Try a worked example"],
    },
    "evaluation": {
        "observations": ["Solved 8/10 correctly"],
        "evidence": ["quiz-artifact-42"],
        "weak_points": ["Chain rule"],
        "suggestions": ["Practice composite functions"],
    },
}


@pytest.mark.parametrize("kind", sorted(VALID_PAYLOADS))
def test_valid_envelope_per_kind(kind):
    env = validate_envelope(_envelope(kind, VALID_PAYLOADS[kind]))
    assert isinstance(env, LearningOutputEnvelope)
    assert env.kind == kind
    assert env.space_id == "course-space-1"
    # review defaulted from the contract when omitted.
    assert env.review["mode"] == default_review_mode(kind)
    assert env.review["status"] == "pending"


def test_valid_payloads_cover_every_kind():
    assert set(VALID_PAYLOADS) == set(KINDS)


# --------------------------------------------------------------------------- #
# Envelope-level rejections
# --------------------------------------------------------------------------- #

def test_unknown_kind_rejected():
    with pytest.raises(ContractError):
        validate_envelope(_envelope("space_diagram", {"cards": []}))


def test_wrong_version_rejected():
    with pytest.raises(ContractError):
        validate_envelope(
            _envelope("flashcard_deck", VALID_PAYLOADS["flashcard_deck"], version=2)
        )


def test_missing_space_id_rejected():
    env = _envelope("flashcard_deck", VALID_PAYLOADS["flashcard_deck"])
    env["space_id"] = ""
    with pytest.raises(ContractError):
        validate_envelope(env)


def test_payload_must_be_a_mapping():
    with pytest.raises(ContractError):
        validate_envelope(_envelope("flashcard_deck", ["not", "a", "dict"]))


def test_title_over_limit_rejected():
    env = _envelope("flashcard_deck", VALID_PAYLOADS["flashcard_deck"])
    env["title"] = "x" * 10_000
    with pytest.raises(ContractError):
        validate_envelope(env)


def test_bad_review_mode_rejected():
    env = _envelope(
        "flashcard_deck",
        VALID_PAYLOADS["flashcard_deck"],
        review={"mode": "vibes", "status": "pending"},
    )
    with pytest.raises(ContractError):
        validate_envelope(env)


def test_bad_review_status_rejected():
    env = _envelope(
        "flashcard_deck",
        VALID_PAYLOADS["flashcard_deck"],
        review={"mode": "semantic", "status": "approved"},  # not in vocab
    )
    with pytest.raises(ContractError):
        validate_envelope(env)


def test_explicit_valid_review_is_preserved():
    env = validate_envelope(
        _envelope(
            "quiz",
            VALID_PAYLOADS["quiz"],
            review={"mode": "deterministic", "status": "passed"},
        )
    )
    assert env.review == {"mode": "deterministic", "status": "passed"}


def test_oversize_payload_rejected():
    huge = {"cards": [{"front": "a", "back": "b" * 2000} for _ in range(2000)]}
    with pytest.raises(ContractError):
        validate_envelope(_envelope("flashcard_deck", huge))


def test_oversize_source_refs_rejected():
    env = _envelope(
        "flashcard_deck",
        VALID_PAYLOADS["flashcard_deck"],
        source_refs=["x" * (600 * 1024)],
    )
    with pytest.raises(ContractError):
        validate_envelope(env)


def test_non_json_serializable_source_ref_rejected():
    env = _envelope(
        "flashcard_deck",
        VALID_PAYLOADS["flashcard_deck"],
        source_refs=[{"bad": {1, 2}}],
    )
    with pytest.raises(ContractError):
        validate_envelope(env)


# --------------------------------------------------------------------------- #
# Per-kind payload rejections
# --------------------------------------------------------------------------- #

def test_flashcard_missing_back_rejected():
    with pytest.raises(ContractError):
        validate_envelope(
            _envelope("flashcard_deck", {"cards": [{"front": "only front"}]})
        )


def test_flashcard_empty_deck_rejected():
    with pytest.raises(ContractError):
        validate_envelope(_envelope("flashcard_deck", {"cards": []}))


def test_knowledge_base_missing_explanation_rejected():
    with pytest.raises(ContractError):
        validate_envelope(
            _envelope("knowledge_base", {"concepts": [{"term": "Limit"}]})
        )


def test_learning_plan_requires_phases():
    with pytest.raises(ContractError):
        validate_envelope(_envelope("learning_plan", {"goals": ["x"]}))


def test_resource_pack_requires_purpose():
    with pytest.raises(ContractError):
        validate_envelope(
            _envelope("resource_pack", {"resources": [{"title": "no purpose"}]})
        )


def test_student_state_rejects_fixed_capability_labels():
    # design: student_state carries editable prefs/goals, never fixed ability labels.
    with pytest.raises(ContractError):
        validate_envelope(
            _envelope(
                "student_state",
                {"goals": ["x"], "capability_labels": ["advanced"]},
            )
        )


def test_evaluation_rejects_personality_labeling():
    with pytest.raises(ContractError):
        validate_envelope(
            _envelope(
                "evaluation",
                {"observations": ["ok"], "ability_labels": ["gifted"]},
            )
        )


def test_evaluation_requires_observations():
    with pytest.raises(ContractError):
        validate_envelope(_envelope("evaluation", {"suggestions": ["study more"]}))


def test_evaluation_evidence_refs_are_valid():
    env = validate_envelope(
        _envelope(
            "evaluation",
            {
                "observations": ["Quiz score improved."],
                "weak_points": ["prime numbers"],
                "suggestions": ["Add mixed drills"],
                "evidence_refs": [
                    {"activity_id": "act-1", "activity_type": "quiz.attempt"},
                    {"artifact_id": "quiz-1"},
                ],
            },
        )
    )
    assert env.payload["evidence_refs"][0]["activity_id"] == "act-1"


def test_source_refs_reject_nested_or_content_dump_values():
    with pytest.raises(ContractError):
        validate_envelope(
            _envelope(
                "tutoring_note",
                {"goal": "g", "hints": ["h"]},
                source_refs=[{"raw_chat": {"messages": []}}],
            )
        )
    with pytest.raises(ContractError):
        validate_envelope(
            _envelope(
                "tutoring_note",
                {"goal": "g", "hints": ["h"]},
                source_refs=[{"gist": "x" * 2001}],
            )
        )


@pytest.mark.parametrize(
    "refs",
    [
        ["not an object"],
        [{"activity_id": 42}],
        [{}] * 201,
    ],
)
def test_evaluation_evidence_refs_must_be_bounded_string_map_list(refs):
    with pytest.raises(ContractError):
        validate_envelope(
            _envelope(
                "evaluation",
                {"observations": ["x"], "evidence_refs": refs},
            )
        )


def test_learning_plan_has_a_total_item_bound():
    with pytest.raises(ContractError, match="plan items"):
        validate_envelope(
            _envelope(
                "learning_plan",
                {
                    "phases": [
                        {
                            "title": "Too much",
                            "tasks": [
                                {"title": f"Task {index}"} for index in range(501)
                            ],
                        }
                    ]
                },
            )
        )


# --------------------------------------------------------------------------- #
# Quiz discriminated union — each question type has its own sub-schema.
# --------------------------------------------------------------------------- #

def test_quiz_unknown_question_type_rejected():
    with pytest.raises(ContractError):
        validate_envelope(
            _envelope(
                "quiz",
                {"questions": [{"type": "matching", "prompt": "?", "answer": "x"}]},
            )
        )


def test_quiz_choice_answer_index_out_of_range_rejected():
    with pytest.raises(ContractError):
        validate_envelope(
            _envelope(
                "quiz",
                {
                    "questions": [
                        {
                            "type": "choice",
                            "prompt": "Pick one",
                            "options": ["a", "b"],
                            "answer": 5,
                        }
                    ]
                },
            )
        )


def test_quiz_choice_requires_multiple_options():
    with pytest.raises(ContractError):
        validate_envelope(
            _envelope(
                "quiz",
                {
                    "questions": [
                        {
                            "type": "choice",
                            "prompt": "Pick one",
                            "options": ["only-one"],
                            "answer": 0,
                        }
                    ]
                },
            )
        )


def test_quiz_true_false_answer_must_be_bool():
    with pytest.raises(ContractError):
        validate_envelope(
            _envelope(
                "quiz",
                {
                    "questions": [
                        {"type": "true_false", "prompt": "?", "answer": "yes"}
                    ]
                },
            )
        )


def test_quiz_short_answer_requires_answer_or_accepted():
    with pytest.raises(ContractError):
        validate_envelope(
            _envelope(
                "quiz",
                {"questions": [{"type": "short_answer", "prompt": "?"}]},
            )
        )


def test_quiz_short_answer_accepted_list_is_valid():
    env = validate_envelope(
        _envelope(
            "quiz",
            {
                "questions": [
                    {
                        "type": "short_answer",
                        "prompt": "Largest ocean?",
                        "accepted": ["Pacific", "The Pacific"],
                    }
                ]
            },
        )
    )
    assert env.kind == "quiz"


@pytest.mark.parametrize(
    "question",
    [
        {
            "type": "code",
            "prompt": "Implement sigmoid",
            "language": "python",
            "mode": "solve",
            "starter": "def sigmoid(x):\n    ...",
            "test_code": "assert abs(sigmoid(0) - 0.5) < 1e-9",
            "reference": "def sigmoid(x): return 1 / (1 + exp(-x))",
            "tags": ["activation"],
        },
        {
            "type": "code",
            "prompt": "Transcribe this function",
            "language": "python",
            "mode": "transcribe",
            "target_code": "def add(a, b):\n    return a + b",
        },
        {
            "type": "code",
            "prompt": "Implement in JavaScript",
            "language": "javascript",
            "mode": "solve",
        },
        {
            "type": "derivation",
            "prompt": "Derive variance",
            "steps": [
                {
                    "expr": "Var(X)=E[(X-E[X])^2]",
                    "expr_py": "E_x2 - 2*mu*mu + mu*mu",
                    "justification": "definition",
                    "accepted": ["definition", "by definition"],
                },
                {"expr": "=E[X^2]-E[X]^2", "justification": "expand"},
            ],
            "check": "numeric-equivalence",
            "cloze": [1],
            "tags": ["variance"],
        },
        {
            "type": "derivation",
            "prompt": "Transcribe variance",
            "mode": "transcribe",
            "steps": [{"expr": "Var(X)"}],
            "target_steps": [{"expr": "Var(X)", "justification": "definition"}],
            "check": "normalized-match",
            "cloze": [0],
        },
    ],
)
def test_quiz_code_and_derivation_members_are_valid(question):
    env = validate_envelope(_envelope("quiz", {"questions": [question]}))
    assert env.payload["questions"][0]["type"] in {"code", "derivation"}


@pytest.mark.parametrize(
    "question,match",
    [
        (
            {"type": "code", "prompt": "x", "language": "python", "mode": "copy"},
            "mode",
        ),
        (
            {"type": "code", "prompt": "x", "language": "python", "mode": "transcribe"},
            "target_code",
        ),
        (
            {"type": "code", "prompt": "x", "language": "python", "mode": "solve"},
            "test_code",
        ),
        (
            {"type": "code", "prompt": "x", "language": "javascript", "mode": "solve", "target_code": "secret"},
            "only allowed",
        ),
        (
            {"type": "code", "prompt": "x", "language": "", "mode": "solve"},
            "language",
        ),
        (
            {
                "type": "derivation",
                "prompt": "x",
                "steps": [{"expr": "x"}],
                "check": "symbolic",
                "cloze": [0],
            },
            "check",
        ),
        (
            {
                "type": "derivation",
                "prompt": "x",
                "steps": [{"expr": "x"}],
                "check": "normalized-match",
                "cloze": [1],
            },
            "cloze",
        ),
        (
            {
                "type": "derivation",
                "prompt": "x",
                "steps": [{"expr": "x"}] * 51,
                "check": "normalized-match",
                "cloze": [0],
            },
            "50",
        ),
        (
            {
                "type": "derivation",
                "prompt": "x",
                "steps": [{"expr": "x"}],
                "target_steps": [{"expr": "secret"}],
                "check": "normalized-match",
                "cloze": [0],
            },
            "only allowed",
        ),
        (
            {
                "type": "derivation",
                "prompt": "x",
                "mode": "transcribe",
                "steps": [{"expr": "x"}],
                "check": "normalized-match",
                "cloze": [0],
            },
            "target_steps",
        ),
    ],
)
def test_quiz_code_and_derivation_invalid_rules_are_rejected(question, match):
    with pytest.raises(ContractError, match=match):
        validate_envelope(_envelope("quiz", {"questions": [question]}))


@pytest.mark.parametrize("field", ["starter", "target_code", "test_code", "reference"])
def test_quiz_code_fields_use_contract_string_cap(field):
    question = {
        "type": "code",
        "prompt": "x",
        "language": "python",
        "mode": "transcribe" if field == "target_code" else "solve",
        "test_code": "assert True",
        field: "x" * 20_001,
    }
    with pytest.raises(ContractError, match=field):
        validate_envelope(_envelope("quiz", {"questions": [question]}))


# --------------------------------------------------------------------------- #
# Envelope object behaviour
# --------------------------------------------------------------------------- #

def test_envelope_roundtrips_to_dict():
    src = _envelope("flashcard_deck", VALID_PAYLOADS["flashcard_deck"])
    env = validate_envelope(src)
    as_dict = env.to_dict()
    # A validated dict re-validates cleanly (idempotent).
    again = validate_envelope(as_dict)
    assert again.to_dict() == as_dict


def test_validate_does_not_mutate_input():
    src = _envelope("quiz", VALID_PAYLOADS["quiz"])
    snapshot = copy.deepcopy(src)
    validate_envelope(src)
    assert src == snapshot


# --------------------------------------------------------------------------- #
# Migration hook
# --------------------------------------------------------------------------- #

def test_migrate_current_version_is_noop():
    src = _envelope("flashcard_deck", VALID_PAYLOADS["flashcard_deck"])
    out = migrate_to_current(src)
    assert out["version"] == CONTRACT_VERSION
    validate_envelope(out)


def test_migrate_future_version_rejected():
    src = _envelope("flashcard_deck", VALID_PAYLOADS["flashcard_deck"], version=99)
    with pytest.raises(ContractError):
        migrate_to_current(src)


def test_migrate_bad_version_rejected():
    src = _envelope("flashcard_deck", VALID_PAYLOADS["flashcard_deck"], version=0)
    with pytest.raises(ContractError):
        migrate_to_current(src)
