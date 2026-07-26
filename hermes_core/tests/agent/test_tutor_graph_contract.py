from __future__ import annotations

import copy

import pytest

from agent.graph_engine.tutor_contracts import (
    TutorProviderPlanV1,
    classify_learner_control,
    new_tutor_state,
    validate_tutor_state,
)
from learning.tutor_contract import LearningActivityKeyV1, TutorContractError


def _key() -> LearningActivityKeyV1:
    return LearningActivityKeyV1("owner-1", "space-1", "tutor", "activity-1")


def _plan() -> TutorProviderPlanV1:
    return TutorProviderPlanV1(
        provider_id="custom",
        model_id="model-1",
        api_mode="chat_completions",
        endpoint_identity="https://example.invalid/v1",
    )


def test_new_state_is_serializable_and_contains_frozen_identity_and_budget() -> None:
    state = new_tutor_state(
        _key(),
        goal="Explain fractions",
        input_refs=({"kind": "source", "id": "source-1"},),
        provider_plan=_plan(),
    )

    assert state["schema_version"] == 1
    assert state["graph_schema_version"] == 1
    assert state["policy_version"] == "tutor-v1"
    assert state["identity"] == {
        "owner_id": "owner-1",
        "space_id": "space-1",
        "activity_kind": "tutor",
        "activity_id": "activity-1",
    }
    assert state["phase"] == "start"
    assert state["branch"] == "check_1"
    assert state["remediation_count"] == 0
    assert state["budget"] == {
        "nodes_used": 0,
        "attempts_used": 0,
        "reserved_input_tokens": 0,
        "reserved_output_tokens": 0,
        "reserved_wall_ms": 0,
        "active_elapsed_ms": 0,
    }
    assert state["provider_plan"] == _plan().to_checkpoint_dict()
    assert validate_tutor_state(copy.deepcopy(state)) == state


@pytest.mark.parametrize(
    ("branch", "selected", "expected"),
    [
        ("check_1", ["continue"], "continue"),
        ("check_1", ["explain_again"], "explain_again"),
        ("check_2", ["continue"], "continue"),
        ("check_2", ["explain_again"], "invalid"),
        ("check_1", [], "invalid"),
        ("check_1", ["continue", "explain_again"], "invalid"),
        ("check_1", ["forged"], "invalid"),
    ],
)
def test_control_branch_is_host_deterministic(
    branch: str, selected: list[str], expected: str
) -> None:
    answer = {"type": "choice", "selected": selected}
    assert classify_learner_control(branch, answer) == expected


@pytest.mark.parametrize(
    "mutator",
    [
        lambda state: state.update(schema_version=2),
        lambda state: state.update(policy_version="future-policy"),
        lambda state: state.update(phase="grader"),
        lambda state: state.update(remediation_count=2),
        lambda state: state["budget"].update(nodes_used=15),
        lambda state: state["provider_plan"].update(api_mode="responses"),
        lambda state: state.update(correct=True),
    ],
)
def test_state_rejects_unknown_versions_caps_and_correctness_fields(mutator) -> None:
    state = new_tutor_state(
        _key(), goal="Goal", input_refs=(), provider_plan=_plan()
    )
    mutator(state)
    with pytest.raises(TutorContractError):
        validate_tutor_state(state)


def test_provider_plan_hash_excludes_credentials_and_is_stable() -> None:
    plan = _plan()
    assert set(plan.to_checkpoint_dict()) == {
        "schema_version",
        "provider_id",
        "model_id",
        "api_mode",
        "endpoint_identity",
    }
    assert len(plan.plan_hash) == 64
    assert plan.plan_hash == _plan().plan_hash


@pytest.mark.parametrize(
    "endpoint",
    [
        "https://user:password@example.invalid/v1",
        "https://example.invalid/v1?api_key=secret",
        "https://example.invalid/v1?token=secret",
        "file:///tmp/provider",
    ],
)
def test_provider_plan_rejects_secret_bearing_or_non_http_endpoint(endpoint) -> None:
    with pytest.raises(TutorContractError):
        TutorProviderPlanV1(
            provider_id="custom",
            model_id="model-1",
            api_mode="chat_completions",
            endpoint_identity=endpoint,
        )
