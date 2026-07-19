"""Application-service tests for the B02 Tutor lifecycle candidate."""

from __future__ import annotations

import pytest

from learning.checkpoint_store import LearningCheckpointV1
from learning.tutor_activity import (
    TutorActivityNotFoundError,
    TutorActivityNotReadyError,
    TutorActivityService,
)
from learning.tutor_contract import TutorContractError, validate_start_request
from learning.tutor_runtime_store import TutorRuntimeStore


def _body(**overrides):
    body = {
        "schema_version": 1,
        "space_id": "space-1",
        "activity_kind": "tutor",
        "idempotency_key": "start-1",
        "goal": "Learn quadratics",
        "input_refs": [],
    }
    body.update(overrides)
    return body


def _seed(store: TutorRuntimeStore):
    request = validate_start_request(
        _body(), owner_id="owner-1", activity_id="activity-1"
    )
    checkpoint = LearningCheckpointV1(
        request.key,
        0,
        "created",
        {
            "schema_version": 1,
            "phase": "start",
            "goal": request.goal,
            "input_refs": [],
            "latest_output": {
                "kind": "explanation",
                "markdown": "Public explanation",
            },
        },
    )
    store.create(request, checkpoint, label="Quadratics")
    return request


@pytest.fixture()
def service(tmp_path):
    store = TutorRuntimeStore(tmp_path / "tutor_runtime.db")
    yield TutorActivityService(store), store
    store.close()


def test_start_is_validated_then_fails_not_ready_without_a_row(service):
    activity, store = service
    with pytest.raises(TutorActivityNotReadyError):
        activity.start("owner-1", _body())
    assert store.list("owner-1", "space-1", "tutor") == []

    with pytest.raises(TutorContractError):
        activity.start("owner-1", _body(owner_id="attacker"))
    assert store.list("owner-1", "space-1", "tutor") == []


def test_get_and_list_are_scoped_public_projections(service):
    activity, store = service
    request = _seed(store)
    snapshot = activity.get("owner-1", "space-1", "tutor", "activity-1")
    public = snapshot.to_public_dict()
    assert public["label"] == "Quadratics"
    assert public["latest_output"]["markdown"] == "Public explanation"
    assert "owner_id" not in str(public)
    assert "Learn quadratics" not in str(public)
    assert [item.key for item in activity.list("owner-1", "space-1", "tutor")] == [
        request.key
    ]

    with pytest.raises(TutorActivityNotFoundError):
        activity.get("other-owner", "space-1", "tutor", "activity-1")
    with pytest.raises(TutorActivityNotFoundError):
        activity.get("owner-1", "other-space", "tutor", "activity-1")
    with pytest.raises(TutorActivityNotFoundError):
        activity.get("owner-1", "space-1", "review", "activity-1")


def test_resume_remains_not_ready_and_does_not_advance_fixture(service):
    activity, store = service
    request = _seed(store)
    with pytest.raises(TutorActivityNotReadyError):
        activity.resume(
            "owner-1",
            "tutor",
            "activity-1",
            {
                "schema_version": 1,
                "space_id": "space-1",
                "expected_revision": 0,
                "mode": "recover",
            },
        )
    assert store.load(request.key).revision == 0


def test_cancel_uses_cas_and_returns_terminal_budget_projection(service):
    activity, store = service
    request = _seed(store)
    cancelled = activity.cancel(
        "owner-1",
        "tutor",
        "activity-1",
        {"schema_version": 1, "space_id": "space-1", "expected_revision": 0},
    ).to_public_dict()
    assert cancelled["status"] == "cancelled"
    assert cancelled["revision"] == 1
    assert cancelled["terminal"] == {
        "outcome": "cancelled",
        "reason_code": "user_cancelled",
        "budget_summary": {
            "nodes_used": 0,
            "attempts_used": 0,
            "reserved_input_tokens": 0,
            "reserved_output_tokens": 0,
            "reserved_wall_ms": 0,
            "active_elapsed_ms": 0,
        },
    }
    assert store.load(request.key).checkpoint is None
