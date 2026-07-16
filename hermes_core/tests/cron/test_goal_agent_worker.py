# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""G1 Task 7 — adapter contract against a fake ``AIAgent`` factory.

Every behavioural case is run against exactly one selected engine; the plan
forbids exercising both ``loop`` and ``graph`` in a single case, so engine is a
parametrize axis, never a loop inside one test.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json
import os

import pytest

import cron.goal_state as goal_state
from agent.usage_events import UsageEvent
from agent.usage_pricing import BillingRoute, CanonicalUsage, CostResult
from cron.goal_agent_worker import GoalAgentWorker
from cron.goal_report import GoalReportError, record_active_goal_report
from cron.goal_state import (
    GoalDefinition,
    GoalLimits,
    new_goal_state,
)

NOW = datetime(2026, 6, 27, 12, 0, tzinfo=timezone.utc)
JOB_ID = "abc123def456"
_REPORT_PAYLOAD = {
    "status": "progress",
    "summary": "processed one item",
    "artifacts": ["manifest.json"],
    "evidence": {"count": 1},
    "next_step": "continue",
    "external_side_effects": [],
}


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    home = tmp_path / "hermes-home"
    monkeypatch.setattr(goal_state, "get_kabuqina_home", lambda: home)
    return home


@pytest.fixture
def definition(tmp_path):
    workdir = tmp_path / "workspace"
    workdir.mkdir()
    return GoalDefinition(
        job_id=JOB_ID,
        objective="complete the inventory",
        iteration_prompt="process one item",
        workdir=workdir.resolve(),
        verifier_kind="artifact_exists",
        verifier_config={"paths": ["manifest.json"]},
        limits=GoalLimits(
            max_runs=10,
            max_cost_usd=Decimal("5"),
            max_wall_seconds=3600,
            deadline=NOW + timedelta(hours=1),
            no_progress_limit=3,
        ),
        enabled_toolsets=("file",),
        approval_mode="ask_before_external_side_effect",
        progress_delivery_every=None,
    )


def _running_state(iteration=1, **changes):
    base = new_goal_state(JOB_ID, now=NOW)
    values = {"status": "running", "iteration": iteration, "updated_at": NOW}
    values.update(changes)
    return replace(base, **values)


def _event(index=0, *, amount="0.01", status="actual", usage=True, outcome="success"):
    return UsageEvent(
        attempt_index=index,
        outcome=outcome,
        route="call_transport",
        billing_route=BillingRoute(
            provider="anthropic", model="claude-x", billing_mode="anthropic_messages"
        ),
        usage=CanonicalUsage(input_tokens=10, output_tokens=5) if usage else None,
        cost=CostResult(
            amount_usd=Decimal(amount) if amount is not None else None,
            status=status,
            source="none",
            label="test",
        ),
    )


class FakeAgent:
    """Stand-in for ``AIAgent``: emits usage events, optionally reports/raises."""

    def __init__(
        self,
        *,
        report_payload=None,
        events=(),
        result=None,
        raise_exc=None,
        on_run=None,
    ):
        self._report_payload = report_payload
        self._events = tuple(events)
        self._result = {"response": "done"} if result is None else result
        self._raise_exc = raise_exc
        self._on_run = on_run
        self.sink = None
        self.run_calls = []
        self.close_calls = 0

    def run_conversation(self, *, user_message, system_message=None, **kwargs):
        self.run_calls.append(
            {
                "user_message": user_message,
                "system_message": system_message,
                "terminal_cwd": os.environ.get("TERMINAL_CWD"),
            }
        )
        for event in self._events:
            self.sink.on_attempt(event)
        if self._on_run is not None:
            self._on_run()
        if self._raise_exc is not None:
            raise self._raise_exc
        if self._report_payload is not None:
            record_active_goal_report(self._report_payload)
        return self._result

    def close(self):
        self.close_calls += 1


class RecordingFactory:
    """Capture constructor kwargs and hand back a prepared fake agent."""

    def __init__(self, agent=None, *, raise_exc=None):
        self._agent = agent
        self._raise_exc = raise_exc
        self.calls = []

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        if self._raise_exc is not None:
            raise self._raise_exc
        self._agent.sink = kwargs["usage_sink"]
        return self._agent


# --- lifecycle ------------------------------------------------------------


def test_runs_one_agent_and_one_conversation_per_iteration(definition):
    agent = FakeAgent(report_payload=_REPORT_PAYLOAD, events=[_event()])
    factory = RecordingFactory(agent)
    worker = GoalAgentWorker(agent_factory=factory)

    worker.run_iteration(definition, _running_state(iteration=1))

    assert len(factory.calls) == 1
    assert len(agent.run_calls) == 1


def test_does_not_pass_a_legacy_engine_selector_to_agent(definition):
    factory = RecordingFactory(FakeAgent(report_payload=_REPORT_PAYLOAD))
    worker = GoalAgentWorker(agent_factory=factory)

    worker.run_iteration(definition, _running_state())

    assert "agent_engine" not in factory.calls[0]


def test_profile_runtime_resolver_supplies_model_and_provider(definition):
    factory = RecordingFactory(FakeAgent(report_payload=_REPORT_PAYLOAD))
    calls = []

    def resolve_runtime(model, provider):
        calls.append((model, provider))
        return {
            "model": "deepseek-v4-flash",
            "provider": "deepseek",
            "api_key": "test-only-key",
            "base_url": "https://api.deepseek.example/v1",
            "api_mode": "chat_completions",
        }

    worker = GoalAgentWorker(
        agent_factory=factory,
        runtime_provider="deepseek",
        runtime_resolver=resolve_runtime,
    )

    worker.run_iteration(definition, _running_state())

    assert calls == [("", "deepseek")]
    assert factory.calls[0]["model"] == "deepseek-v4-flash"
    assert factory.calls[0]["provider"] == "deepseek"
    assert factory.calls[0]["api_mode"] == "chat_completions"


def test_generates_fresh_session_id_each_iteration(definition):
    factory = RecordingFactory(FakeAgent(report_payload=_REPORT_PAYLOAD))
    worker = GoalAgentWorker(agent_factory=factory)

    worker.run_iteration(definition, _running_state(iteration=1))
    worker.run_iteration(definition, _running_state(iteration=2))

    first, second = factory.calls[0]["session_id"], factory.calls[1]["session_id"]
    assert first != second
    assert first.startswith("goal-abc123def456-")


def test_manifest_goal_scope_allows_one_manifest_write_only(definition, monkeypatch):
    from tools import file_tools

    scoped_definition = replace(
        definition,
        verifier_kind="manifest_complete",
        verifier_config={"manifest": "learning-materials.json"},
    )
    monkeypatch.setenv("TERMINAL_CWD", str(scoped_definition.workdir))
    writes = []

    class Result:
        def to_dict(self):
            return {"status": "ok"}

    class FileOps:
        def write_file(self, path, content):
            writes.append((path, content))
            return Result()

    def exercise_file_boundary():
        blocked = json.loads(file_tools.write_file_tool("notes.txt", "no"))
        assert "only the configured manifest" in blocked["error"]

        allowed = json.loads(
            file_tools.write_file_tool("learning-materials.json", "{}")
        )
        assert allowed["status"] == "ok"

        repeated = json.loads(
            file_tools.write_file_tool("learning-materials.json", "{}")
        )
        assert "only once" in repeated["error"]

        patched = json.loads(
            file_tools.patch_tool(
                mode="replace",
                path="learning-materials.json",
                old_string="{}",
                new_string="{}",
            )
        )
        assert "patch blocked" in patched["error"]

    monkeypatch.setattr(file_tools, "_get_file_ops", lambda task_id: FileOps())
    agent = FakeAgent(report_payload=_REPORT_PAYLOAD, on_run=exercise_file_boundary)
    worker = GoalAgentWorker(agent_factory=RecordingFactory(agent))

    observation = worker.run_iteration(scoped_definition, _running_state())

    assert observation.report is not None
    assert writes == [("learning-materials.json", "{}")]


# --- report scope ---------------------------------------------------------


def test_captures_submitted_report(definition):
    factory = RecordingFactory(FakeAgent(report_payload=_REPORT_PAYLOAD))
    worker = GoalAgentWorker(agent_factory=factory)

    observation = worker.run_iteration(definition, _running_state())

    assert observation.report is not None
    assert observation.report.status == "progress"
    assert observation.report.summary == "processed one item"


def test_report_scope_is_closed_after_iteration(definition):
    factory = RecordingFactory(FakeAgent(report_payload=_REPORT_PAYLOAD))
    worker = GoalAgentWorker(agent_factory=factory)

    worker.run_iteration(definition, _running_state())

    # The iteration-scoped collector must not outlive run_iteration.
    with pytest.raises(GoalReportError):
        record_active_goal_report(_REPORT_PAYLOAD)


def test_missing_report_yields_none_without_ambiguity(definition):
    factory = RecordingFactory(FakeAgent(report_payload=None, events=[_event()]))
    worker = GoalAgentWorker(agent_factory=factory)

    observation = worker.run_iteration(definition, _running_state())

    assert observation.report is None
    assert observation.infrastructure_error is None
    assert observation.ambiguous_external_effect is False


# --- usage accounting -----------------------------------------------------


def test_complete_usage_is_summed(definition):
    agent = FakeAgent(
        report_payload=_REPORT_PAYLOAD,
        events=[_event(0, amount="0.01"), _event(1, amount="0.02")],
    )
    factory = RecordingFactory(agent)
    worker = GoalAgentWorker(agent_factory=factory)

    observation = worker.run_iteration(definition, _running_state())

    assert observation.usage.complete is True
    assert observation.usage.amount_usd == Decimal("0.03")
    assert len(observation.usage.events) == 2


def test_no_transport_attempt_is_complete_zero_cost(definition):
    factory = RecordingFactory(FakeAgent(report_payload=_REPORT_PAYLOAD, events=[]))
    worker = GoalAgentWorker(agent_factory=factory)

    observation = worker.run_iteration(definition, _running_state())

    assert observation.usage.complete is True
    assert observation.usage.amount_usd == Decimal("0")


@pytest.mark.parametrize(
    ("event", "reason"),
    [
        (_event(0, amount=None, status="estimated"), "missing_amount"),
        (_event(0, status="unknown"), "unknown_cost"),
        (_event(0, usage=False), "missing_usage"),
    ],
)
def test_any_unpriced_attempt_makes_usage_incomplete(definition, event, reason):
    agent = FakeAgent(
        report_payload=_REPORT_PAYLOAD, events=[_event(0, amount="0.01"), event]
    )
    # Re-index the second event so the ledger sees a clean attempt sequence.
    agent._events = (agent._events[0], replace(event, attempt_index=1))
    factory = RecordingFactory(agent)
    worker = GoalAgentWorker(agent_factory=factory)

    observation = worker.run_iteration(definition, _running_state())

    assert observation.usage.complete is False
    assert observation.usage.amount_usd is None
    assert observation.usage.incomplete_reason == reason


# --- failure classification ----------------------------------------------


def test_setup_exception_is_safe_infrastructure_failure(definition):
    factory = RecordingFactory(raise_exc=RuntimeError("no provider credentials"))
    worker = GoalAgentWorker(agent_factory=factory)

    observation = worker.run_iteration(definition, _running_state())

    assert observation.report is None
    assert observation.infrastructure_error is not None
    assert observation.ambiguous_external_effect is False
    # No transport attempt was made, so the ledger is a complete zero-cost one.
    assert observation.usage.complete is True


def test_run_exception_after_entry_is_ambiguous(definition):
    agent = FakeAgent(events=[_event()], raise_exc=RuntimeError("crash mid-turn"))
    factory = RecordingFactory(agent)
    worker = GoalAgentWorker(agent_factory=factory)

    observation = worker.run_iteration(definition, _running_state())

    assert observation.report is None
    assert observation.infrastructure_error is not None
    assert observation.ambiguous_external_effect is True


# --- toolset policy & context --------------------------------------------


def test_enabled_toolsets_add_goal_internal_without_broadening(definition):
    factory = RecordingFactory(FakeAgent(report_payload=_REPORT_PAYLOAD))
    worker = GoalAgentWorker(agent_factory=factory)

    worker.run_iteration(definition, _running_state())

    toolsets = factory.calls[0]["enabled_toolsets"]
    assert toolsets == ["file", "goal_internal"]


def test_goal_internal_not_duplicated_when_already_declared(definition):
    definition = replace(definition, enabled_toolsets=("goal_internal", "file"))
    factory = RecordingFactory(FakeAgent(report_payload=_REPORT_PAYLOAD))
    worker = GoalAgentWorker(agent_factory=factory)

    worker.run_iteration(definition, _running_state())

    toolsets = factory.calls[0]["enabled_toolsets"]
    assert toolsets.count("goal_internal") == 1
    assert set(toolsets) == {"file", "goal_internal"}


def test_system_message_carries_bounds_and_excludes_evidence_bodies(definition):
    agent = FakeAgent(report_payload=_REPORT_PAYLOAD)
    factory = RecordingFactory(agent)
    worker = GoalAgentWorker(agent_factory=factory)

    state = _running_state(
        iteration=3, last_summary="prev summary", last_evidence_hash="deadbeef"
    )
    worker.run_iteration(definition, state)

    sysmsg = agent.run_calls[0]["system_message"]
    assert "complete the inventory" in sysmsg
    assert "iteration: 3" in sysmsg.lower()
    assert definition.workdir.as_posix() in sysmsg
    assert "goal_report" in sysmsg
    assert "file_metadata" in sysmsg
    # Compact carry-over only: the fingerprint and one-line summary, never a
    # raw evidence body.
    assert "deadbeef" in sysmsg
    assert "prev summary" in sysmsg
    assert "model_text" not in sysmsg


def test_user_message_is_the_iteration_prompt(definition):
    agent = FakeAgent(report_payload=_REPORT_PAYLOAD)
    factory = RecordingFactory(agent)
    worker = GoalAgentWorker(agent_factory=factory)

    worker.run_iteration(definition, _running_state())

    assert agent.run_calls[0]["user_message"] == "process one item"


def test_agent_constructed_with_goal_workdir_context(definition):
    factory = RecordingFactory(FakeAgent(report_payload=_REPORT_PAYLOAD))
    worker = GoalAgentWorker(agent_factory=factory)

    worker.run_iteration(definition, _running_state())

    call = factory.calls[0]
    assert call["platform"] == "cron"
    assert call["skip_context_files"] is False
    assert call["skip_memory"] is True


def test_goal_iteration_binds_and_restores_terminal_cwd(definition, monkeypatch):
    agent = FakeAgent(report_payload=_REPORT_PAYLOAD)
    factory = RecordingFactory(agent)
    worker = GoalAgentWorker(agent_factory=factory)
    monkeypatch.setenv("TERMINAL_CWD", "D:\\prior")

    worker.run_iteration(definition, _running_state())

    assert os.environ["TERMINAL_CWD"] == "D:\\prior"
    assert agent.run_calls[0]["terminal_cwd"] == str(definition.workdir)


def test_goal_iteration_removes_terminal_cwd_when_previously_unset(
    definition, monkeypatch
):
    agent = FakeAgent(report_payload=_REPORT_PAYLOAD)
    factory = RecordingFactory(agent)
    worker = GoalAgentWorker(agent_factory=factory)
    monkeypatch.delenv("TERMINAL_CWD", raising=False)

    worker.run_iteration(definition, _running_state())

    assert "TERMINAL_CWD" not in os.environ
    assert agent.run_calls[0]["terminal_cwd"] == str(definition.workdir)


def test_agent_is_closed_after_successful_iteration(definition):
    agent = FakeAgent(report_payload=_REPORT_PAYLOAD)
    factory = RecordingFactory(agent)
    worker = GoalAgentWorker(agent_factory=factory)

    worker.run_iteration(definition, _running_state())

    assert agent.close_calls == 1


def test_agent_is_closed_after_run_exception(definition):
    agent = FakeAgent(events=[_event()], raise_exc=RuntimeError("crash mid-turn"))
    factory = RecordingFactory(agent)
    worker = GoalAgentWorker(agent_factory=factory)

    worker.run_iteration(definition, _running_state())

    assert agent.close_calls == 1
