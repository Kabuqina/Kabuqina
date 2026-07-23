"""Contract tests for the versioned Tutor activity wire model."""

import copy
import hashlib
import json
from pathlib import Path

import pytest

from learning.tutor_contract import (
    ACTIVITY_KINDS,
    ACTIVITY_STATUSES,
    ALLOWED_ACTIVITY_TRANSITIONS,
    TERMINAL_ACTIVITY_STATUSES,
    LearningActivityKeyV1,
    LearningActivitySnapshotV1,
    LearningInterruptV1,
    TutorContractError,
    TutorConflictError,
    canonical_json_bytes,
    canonical_request_fingerprint,
    is_allowed_activity_transition,
    validate_cancel_request,
    validate_resume_request,
    validate_start_request,
)


CANONICAL_FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "tutor_canonical_json_vectors.json"
)


def _start(**overrides):
    body = {
        "schema_version": 1,
        "space_id": "space-1",
        "activity_kind": "tutor",
        "idempotency_key": "start-1",
        "goal": "Understand quadratic equations",
        "input_refs": [
            {"kind": "artifact", "id": "note-1", "version": 2},
            {"kind": "source", "id": "book-1", "sha256": "a" * 64},
        ],
    }
    body.update(overrides)
    return body


def test_frozen_activity_vocabulary_and_transitions():
    assert ACTIVITY_KINDS == frozenset({"tutor", "review", "practice"})
    assert ACTIVITY_STATUSES == frozenset(
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
    assert TERMINAL_ACTIVITY_STATUSES == frozenset(
        {"completed", "blocked", "cancelled"}
    )
    assert ALLOWED_ACTIVITY_TRANSITIONS == frozenset(
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


def test_activity_key_requires_the_full_four_part_identity():
    key = LearningActivityKeyV1("owner-1", "space-1", "tutor", "activity-1")
    assert key.as_tuple() == ("owner-1", "space-1", "tutor", "activity-1")

    with pytest.raises(TypeError):
        LearningActivityKeyV1("owner-1", "space-1", "activity-1")
    with pytest.raises(TutorContractError, match="activity_kind"):
        LearningActivityKeyV1("owner-1", "space-1", "lesson", "activity-1")
    with pytest.raises(TutorContractError, match="activity_id"):
        LearningActivityKeyV1("owner-1", "space-1", "tutor", "bad id")


def test_start_injects_owner_and_host_activity_id_and_rejects_public_owner():
    request = validate_start_request(
        _start(), owner_id="owner-1", activity_id="activity-1"
    )
    assert request.key.as_tuple() == (
        "owner-1",
        "space-1",
        "tutor",
        "activity-1",
    )
    assert request.idempotency_namespace == (
        "owner-1",
        "space-1",
        "tutor",
        "start-1",
    )

    with pytest.raises(TutorContractError, match="owner_id"):
        validate_start_request(
            _start(owner_id="attacker"),
            owner_id="owner-1",
            activity_id="activity-1",
        )


def test_start_fingerprint_is_nfc_canonical_and_excludes_idempotency_key():
    composed = _start(goal="Caf\u00e9")
    decomposed = _start(goal="Cafe\u0301", idempotency_key="another-key")
    assert canonical_request_fingerprint(composed) == canonical_request_fingerprint(
        decomposed
    )

    reordered_keys = {
        "input_refs": copy.deepcopy(composed["input_refs"]),
        "goal": composed["goal"],
        "idempotency_key": composed["idempotency_key"],
        "activity_kind": composed["activity_kind"],
        "space_id": composed["space_id"],
        "schema_version": composed["schema_version"],
    }
    assert canonical_request_fingerprint(composed) == canonical_request_fingerprint(
        reordered_keys
    )


def test_start_fingerprint_preserves_input_ref_order():
    first = _start()
    second = _start(input_refs=list(reversed(first["input_refs"])))
    assert canonical_request_fingerprint(first) != canonical_request_fingerprint(second)


@pytest.mark.parametrize(
    "body,match",
    [
        (_start(schema_version=2), "schema_version"),
        (_start(goal="x" * 4001), "goal"),
        (_start(input_refs=[{"kind": "item", "id": f"i-{i}"} for i in range(17)]), "input_refs"),
        (_start(extra=True), "unknown field"),
        (_start(input_refs=[{"kind": "other", "id": "x"}]), "input_refs"),
        (_start(input_refs=[{"kind": "source", "id": "x", "sha256": "ABC"}]), "sha256"),
    ],
)
def test_start_rejects_unknown_version_caps_and_invalid_refs(body, match):
    with pytest.raises(TutorContractError, match=match):
        validate_start_request(body, owner_id="owner-1", activity_id="activity-1")


def test_canonical_json_subset_rejects_float_values():
    with pytest.raises(TutorContractError, match="number"):
        canonical_request_fingerprint(_start(input_refs=[{"kind": "item", "id": "x", "version": 1.5}]))


def test_shared_canonical_json_fixture_matches_python_contract():
    fixture = json.loads(CANONICAL_FIXTURE.read_text(encoding="utf-8"))
    for vector in fixture["equivalent_pairs"]:
        left = hashlib.sha256(canonical_json_bytes(vector["left"])).hexdigest()
        right = hashlib.sha256(canonical_json_bytes(vector["right"])).hexdigest()
        assert left == right == vector["sha256"], vector["name"]
    for vector in fixture["canonical_values"]:
        actual = hashlib.sha256(canonical_json_bytes(vector["value"])).hexdigest()
        assert actual == vector["sha256"], vector["name"]
    with pytest.raises(TutorContractError, match="duplicate normalized keys"):
        canonical_json_bytes(fixture["normalized_key_collision"])


def test_resume_answer_and_recover_are_a_strict_discriminated_union():
    answer = validate_resume_request(
        {
            "schema_version": 1,
            "space_id": "space-1",
            "expected_revision": 3,
            "mode": "answer",
            "interrupt_id": "lint-1",
            "answer": {"type": "choice", "selected": ["option-1"]},
        }
    )
    assert answer.mode == "answer"
    assert answer.expected_revision == 3

    recover = validate_resume_request(
        {
            "schema_version": 1,
            "space_id": "space-1",
            "expected_revision": 4,
            "mode": "recover",
        }
    )
    assert recover.mode == "recover"

    with pytest.raises(TutorContractError, match="recover"):
        validate_resume_request(
            {
                "schema_version": 1,
                "space_id": "space-1",
                "expected_revision": 4,
                "mode": "recover",
                "answer": {"type": "free_text", "text": "not allowed"},
            }
        )


def test_resume_answer_caps_and_cancel_revision_validation():
    with pytest.raises(TutorContractError, match="answer"):
        validate_resume_request(
            {
                "schema_version": 1,
                "space_id": "space-1",
                "expected_revision": 1,
                "mode": "answer",
                "interrupt_id": "lint-1",
                "answer": {"type": "free_text", "text": "x" * 8001},
            }
        )
    cancel = validate_cancel_request(
        {"schema_version": 1, "space_id": "space-1", "expected_revision": 0}
    )
    assert cancel.expected_revision == 0
    with pytest.raises(TutorContractError, match="expected_revision"):
        validate_cancel_request(
            {"schema_version": 1, "space_id": "space-1", "expected_revision": -1}
        )


def test_transition_helper_fails_closed_and_terminal_states_are_immutable():
    for transition in ALLOWED_ACTIVITY_TRANSITIONS:
        assert is_allowed_activity_transition(*transition)
    for status in TERMINAL_ACTIVITY_STATUSES:
        for destination in ACTIVITY_STATUSES:
            assert not is_allowed_activity_transition(status, destination)
    assert not is_allowed_activity_transition("running", "created")
    assert not is_allowed_activity_transition("bogus", "running")


def test_typed_conflict_exposes_stable_reason_code():
    error = TutorConflictError("idempotency_payload_mismatch")
    assert error.reason_code == "idempotency_payload_mismatch"


def test_public_snapshot_and_interrupt_projection_never_exposes_owner():
    key = LearningActivityKeyV1("private-owner", "space-1", "tutor", "activity-1")
    interrupt = LearningInterruptV1(
        interrupt_id="lint-1",
        key=key,
        checkpoint_revision=2,
        prompt={"markdown": "Try the next step"},
        expected_input="step",
        created_at="2026-07-19T00:00:00Z",
    )
    snapshot = LearningActivitySnapshotV1(
        key=key,
        status="waiting_for_learner",
        revision=2,
        label="Quadratics",
        interrupt=interrupt,
        created_at="2026-07-19T00:00:00Z",
        updated_at="2026-07-19T00:01:00Z",
    ).to_public_dict()
    assert "owner_id" not in snapshot
    assert "owner_id" not in snapshot["interrupt"]
    assert snapshot["interrupt"]["activity_kind"] == "tutor"
