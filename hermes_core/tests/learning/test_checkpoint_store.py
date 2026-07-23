"""Port contract tests using the in-memory Tutor repository fake."""

import pytest

from learning.checkpoint_store import (
    InMemoryLearningActivityRepository,
    LearningCheckpointV1,
    validate_checkpoint_state,
)
from learning.tutor_contract import (
    LearningActivityKeyV1,
    TutorConflictError,
    TutorContractError,
    validate_start_request,
)


def _request(*, owner="owner-1", kind="tutor", activity="activity-1", key="start-1", goal="Learn"):
    return validate_start_request(
        {
            "schema_version": 1,
            "space_id": "space-1",
            "activity_kind": kind,
            "idempotency_key": key,
            "goal": goal,
            "input_refs": [],
        },
        owner_id=owner,
        activity_id=activity,
    )


def _checkpoint(key, *, revision=0, status="created", state=None):
    return LearningCheckpointV1(
        key=key,
        revision=revision,
        status=status,
        state=state or {"node": "start"},
    )


def test_create_is_idempotent_for_same_namespace_and_fingerprint():
    repository = InMemoryLearningActivityRepository()
    original = _request(activity="activity-1")
    duplicate = _request(activity="activity-generated-on-retry")

    created, was_created = repository.create(original, _checkpoint(original.key))
    repeated, repeated_was_created = repository.create(
        duplicate, _checkpoint(duplicate.key)
    )

    assert was_created is True
    assert repeated_was_created is False
    assert repeated.key == created.key == original.key
    assert len(repository.list("owner-1", "space-1", "tutor")) == 1


def test_same_idempotency_namespace_with_different_payload_conflicts():
    repository = InMemoryLearningActivityRepository()
    original = _request(goal="First goal")
    repository.create(original, _checkpoint(original.key))

    changed = _request(activity="activity-2", goal="Changed goal")
    with pytest.raises(TutorConflictError) as caught:
        repository.create(changed, _checkpoint(changed.key))
    assert caught.value.reason_code == "idempotency_payload_mismatch"


def test_activity_kind_is_part_of_idempotency_and_lookup_identity():
    repository = InMemoryLearningActivityRepository()
    tutor = _request(kind="tutor", activity="same-id")
    review = _request(kind="review", activity="same-id")
    repository.create(tutor, _checkpoint(tutor.key))
    repository.create(review, _checkpoint(review.key))

    assert repository.load(tutor.key).key.activity_kind == "tutor"
    assert repository.load(review.key).key.activity_kind == "review"
    assert len(repository.list("owner-1", "space-1", "tutor")) == 1
    assert len(repository.list("owner-1", "space-1", "review")) == 1


def test_save_uses_revision_cas_and_increments_exactly_once():
    repository = InMemoryLearningActivityRepository()
    request = _request()
    repository.create(request, _checkpoint(request.key))

    saved = repository.save(
        _checkpoint(request.key, revision=0, status="running", state={"node": "teach"}),
        expected_revision=0,
    )
    assert saved.revision == 1
    assert saved.checkpoint.revision == 1
    assert saved.status == "running"

    with pytest.raises(TutorConflictError) as caught:
        repository.save(
            _checkpoint(request.key, revision=0, status="running"),
            expected_revision=0,
        )
    assert caught.value.reason_code == "stale_revision"


def test_cross_scope_lookup_does_not_fall_back_to_bare_activity_id():
    repository = InMemoryLearningActivityRepository()
    request = _request()
    repository.create(request, _checkpoint(request.key))
    assert repository.load(
        LearningActivityKeyV1("owner-2", "space-1", "tutor", "activity-1")
    ) is None
    assert repository.load(
        LearningActivityKeyV1("owner-1", "space-2", "tutor", "activity-1")
    ) is None


def test_terminal_transition_clears_checkpoint_and_cannot_be_changed():
    repository = InMemoryLearningActivityRepository()
    request = _request()
    repository.create(request, _checkpoint(request.key))
    running = repository.save(
        _checkpoint(request.key, revision=0, status="running"), expected_revision=0
    )
    terminal = repository.save(
        _checkpoint(request.key, revision=1, status="completed"), expected_revision=1
    )
    assert running.revision == 1
    assert terminal.revision == 2
    assert terminal.checkpoint is None

    with pytest.raises(TutorConflictError) as caught:
        repository.save(
            _checkpoint(request.key, revision=2, status="running"), expected_revision=2
        )
    assert caught.value.reason_code == "terminal_immutable"


def test_illegal_transition_and_mismatched_checkpoint_identity_fail_closed():
    repository = InMemoryLearningActivityRepository()
    request = _request()
    repository.create(request, _checkpoint(request.key))
    with pytest.raises(TutorConflictError) as caught:
        repository.save(
            _checkpoint(request.key, revision=0, status="completed"), expected_revision=0
        )
    assert caught.value.reason_code == "invalid_transition"

    other = _request(activity="other", key="other")
    with pytest.raises(TutorContractError, match="checkpoint key"):
        repository.create(request, _checkpoint(other.key))


def test_returned_state_is_defensively_copied():
    repository = InMemoryLearningActivityRepository()
    request = _request()
    repository.create(request, _checkpoint(request.key, state={"nested": {"value": 1}}))
    loaded = repository.load(request.key)
    loaded.checkpoint.state["nested"]["value"] = 99
    assert repository.load(request.key).checkpoint.state["nested"]["value"] == 1


@pytest.mark.parametrize(
    "state",
    [
        {"api_key": "secret"},
        {"nested": {"gateway_id": "chat-1"}},
        {"items": [{"raw_source_bytes": "content"}]},
        {"exception": "raw stack trace"},
    ],
)
def test_checkpoint_forbidden_fields_are_rejected_recursively(state):
    with pytest.raises(TutorContractError, match="forbidden field"):
        validate_checkpoint_state(state)


def test_checkpoint_size_cap_uses_canonical_utf8_bytes():
    validate_checkpoint_state({"text": "x" * 100})
    with pytest.raises(TutorContractError) as caught:
        validate_checkpoint_state({"text": "界" * (256 * 1024)})
    assert caught.value.reason_code == "checkpoint_too_large"
