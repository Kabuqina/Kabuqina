from __future__ import annotations

import copy

from agent.graph_engine.tutor_builder import build_tutor_graph
from agent.graph_engine.tutor_contracts import TutorProviderPlanV1, new_tutor_state
from learning.tutor_contract import LearningActivityKeyV1


class _Services:
    def __init__(self) -> None:
        self.generated: list[str] = []
        self.persisted: list[str] = []

    def generate(self, state, *, purpose: str) -> str:
        self.generated.append(purpose)
        return f"{purpose} output"

    def after_node(self, node_name: str, state):
        self.persisted.append(node_name)
        updated = copy.deepcopy(state)
        if node_name == "learner_control_check":
            updated["pending_interrupt"] = {
                "schema_version": 1,
                "interrupt_id": f"lint_{len(self.persisted)}",
                "kind": "learner_check",
                "owner_id": updated["identity"]["owner_id"],
                "space_id": updated["identity"]["space_id"],
                "activity_kind": updated["identity"]["activity_kind"],
                "activity_id": updated["identity"]["activity_id"],
                "checkpoint_revision": len(self.persisted),
                "prompt": {"template": updated["branch"]},
                "expected_input": "choice",
                "created_at": "2026-07-26T00:00:00Z",
            }
        return updated


def _state():
    return new_tutor_state(
        LearningActivityKeyV1("owner-1", "space-1", "tutor", "activity-1"),
        goal="Explain fractions",
        input_refs=(),
        provider_plan=TutorProviderPlanV1(
            provider_id="custom",
            model_id="model-1",
            api_mode="chat_completions",
            endpoint_identity="https://example.invalid/v1",
        ),
    )


def _invoke(state, services):
    return build_tutor_graph().invoke(
        state,
        {"recursion_limit": 32},
        context={"services": services},
    )


def test_start_uses_one_generation_and_ends_at_first_learner_check() -> None:
    services = _Services()
    result = _invoke(_state(), services)

    assert services.generated == ["explain"]
    assert services.persisted == [
        "validate_context",
        "explain_bounded_unit",
        "handoff_to_learner",
        "learner_control_check",
    ]
    assert result["phase"] == "acknowledge"
    assert result["branch"] == "check_1"
    assert result["budget"]["nodes_used"] == 4
    assert result["pending_interrupt"]["prompt"] == {"template": "check_1"}


def test_continue_completes_without_provider_call() -> None:
    state = _state()
    state.update(
        phase="acknowledge",
        learner_answer={"type": "choice", "selected": ["continue"]},
    )
    services = _Services()

    result = _invoke(state, services)

    assert services.generated == []
    assert services.persisted == ["acknowledge", "complete"]
    assert result["phase"] == "terminal"
    assert result["terminal"] == {
        "outcome": "completed",
        "completion_basis": "participation_only",
    }


def test_explain_again_uses_exactly_one_remediation_then_second_check() -> None:
    state = _state()
    state.update(
        phase="acknowledge",
        learner_answer={"type": "choice", "selected": ["explain_again"]},
        latest_output={"kind": "explanation", "markdown": "first"},
    )
    services = _Services()

    result = _invoke(state, services)

    assert services.generated == ["remediate"]
    assert services.persisted == [
        "acknowledge",
        "remediate_once",
        "handoff_to_learner",
        "learner_control_check",
    ]
    assert result["branch"] == "check_2"
    assert result["remediation_count"] == 1
    assert result["pending_interrupt"]["prompt"] == {"template": "check_2"}


def test_invalid_second_check_reissues_same_check_with_zero_provider_calls() -> None:
    state = _state()
    state.update(
        phase="acknowledge",
        branch="check_2",
        remediation_count=1,
        learner_answer={"type": "choice", "selected": ["explain_again"]},
    )
    services = _Services()

    result = _invoke(state, services)

    assert services.generated == []
    assert services.persisted == ["acknowledge", "learner_control_check"]
    assert result["branch"] == "check_2"
    assert result["remediation_count"] == 1
    assert result["phase"] == "acknowledge"

