"""Unit tests for 小娜的智能体编队 orchestration core (dependency-free).

These exercise the pure layer only — a fake ``run_role`` stands in for real
child-agent spawning, so no LLM/provider is needed.
"""

import pytest

from agent.team import (
    StudyTeamOrchestrator,
    default_team,
    get_roles,
    toposort_layers,
)
from agent.team.dag import DagError
from agent.team.roles import RoleResult, RoleSpec, ROLE_REGISTRY, KNOWN_KINDS
from agent.team import events as ev


# --------------------------------------------------------------------------- #
# DAG
# --------------------------------------------------------------------------- #

def test_toposort_linear_chain():
    deps = {"a": (), "b": ("a",), "c": ("b",)}
    assert toposort_layers(["a", "b", "c"], deps) == [["a"], ["b"], ["c"]]


def test_toposort_groups_independent_into_one_layer():
    deps = {"a": (), "b": (), "gate": ("a", "b")}
    layers = toposort_layers(["a", "b", "gate"], deps)
    assert layers[0] == ["a", "b"]  # sorted, same layer
    assert layers[1] == ["gate"]


def test_toposort_detects_cycle():
    deps = {"a": ("b",), "b": ("a",)}
    with pytest.raises(DagError):
        toposort_layers(["a", "b"], deps)


def test_toposort_ignores_missing_deps_by_default():
    # a subset run: 'gate' depends on roles not selected -> deps pruned
    deps = {"gate": ("missing",)}
    assert toposort_layers(["gate"], deps) == [["gate"]]


def test_toposort_strict_missing_dep_raises():
    with pytest.raises(DagError):
        toposort_layers(["gate"], {"gate": ("missing",)}, ignore_missing_deps=False)


# --------------------------------------------------------------------------- #
# Roles / registry
# --------------------------------------------------------------------------- #

def test_default_team_roles():
    ids = {s.role_id for s in default_team()}
    assert ids == {
        "profiler", "lecturer", "quizmaster",
        "mindmapper", "filmmaker", "librarian", "guardian",
    }
    # guardian is the sole gate and reviews everyone
    guardian = next(s for s in default_team() if s.role_id == "guardian")
    assert guardian.is_gate and set(guardian.depends_on) == ids - {"guardian"}


def test_role_allowed_kinds_are_real_contract_kinds():
    for spec in default_team():
        assert spec.allowed_kinds <= KNOWN_KINDS


def test_get_roles_subset_always_appends_guardian():
    specs = get_roles(["lecturer"])
    ids = {s.role_id for s in specs}
    assert "lecturer" in ids and "guardian" in ids


def test_role_prompt_mentions_goal_and_upstream():
    lecturer = ROLE_REGISTRY["lecturer"]
    up = {"profiler": RoleResult("profiler", ev.STATUS_PRODUCED, summary="6维画像已建")}
    prompt = lecturer.build_prompt("讲第3章", up)
    assert "讲第3章" in prompt
    assert "6维画像已建" in prompt


# --------------------------------------------------------------------------- #
# Orchestrator
# --------------------------------------------------------------------------- #

def _recording_run_role(produced_by_role):
    """Build a fake run_role that returns canned produced-artifacts per role,
    and records the (role_id, upstream_ids) it was called with."""
    calls = []

    def run_role(spec, goal, upstream):
        calls.append((spec.role_id, sorted(upstream.keys())))
        arts = produced_by_role.get(spec.role_id, [])
        status = ev.STATUS_PASSED if spec.is_gate else ev.STATUS_PRODUCED
        return RoleResult(spec.role_id, status, summary=f"{spec.role_id} done", produced=tuple(arts))

    return run_role, calls


def test_orchestrator_runs_in_dependency_order_and_passes_upstream():
    run_role, calls = _recording_run_role({
        "profiler": [{"artifact_id": "s1", "kind": "student_state", "title": "画像"}],
        "lecturer": [{"artifact_id": "k1", "kind": "knowledge_base", "title": "KB"}],
        "quizmaster": [{"artifact_id": "q1", "kind": "quiz", "title": "测验"}],
        "mindmapper": [{"artifact_id": "m1", "kind": "resource_pack", "title": "导图"}],
    })
    events_log = []
    orch = StudyTeamOrchestrator(run_role, emit=events_log.append)

    report = orch.run("目标", default_team(), run_id="run-1", session_id="sess-1")

    order = [rid for rid, _ in calls]
    # DAG invariants (not the exact middle-layer order):
    assert order[0] == "profiler"
    assert order[1] == "lecturer"
    assert order[-1] == "guardian"
    # lecturer saw profiler; content roles saw lecturer; guardian saw everyone
    assert dict(calls)["lecturer"] == ["profiler"]
    assert dict(calls)["quizmaster"] == ["lecturer"]
    assert dict(calls)["mindmapper"] == ["lecturer"]
    assert dict(calls)["guardian"] == sorted(
        ["profiler", "lecturer", "quizmaster", "mindmapper", "filmmaker", "librarian"]
    )
    assert report["ok"] is True
    assert report["drafts_total"] == 4
    assert report["violations"] == []


def test_orchestrator_emits_expected_event_sequence():
    run_role, _ = _recording_run_role({})
    log = []
    orch = StudyTeamOrchestrator(run_role, emit=log.append)
    orch.run("g", default_team(), run_id="r", session_id="s")

    phases = [e["phase"] for e in log]
    assert phases[0] == "team_started"
    assert phases[-1] == "team_done"
    assert all(e["type"] == ev.EVENT_TYPE for e in log)
    # every role emits a working frame
    working = [e for e in log if e["phase"] == "role" and e["status"] == "working"]
    assert {e["role_id"] for e in working} == {
        "profiler", "lecturer", "quizmaster", "mindmapper", "filmmaker", "librarian", "guardian",
    }
    layers = log[0]["dag"]["layers"]
    assert layers[0] == ["profiler"]
    assert layers[1] == ["lecturer"]
    assert layers[-1] == ["guardian"]
    # the four content roles share the middle layer
    assert set(layers[2]) == {"quizmaster", "mindmapper", "filmmaker", "librarian"}


def test_orchestrator_enforces_allowed_kinds():
    # lecturer tries to emit a 'quiz' (not in its allowed_kinds) -> dropped + violation
    run_role, _ = _recording_run_role({
        "lecturer": [
            {"artifact_id": "k1", "kind": "knowledge_base", "title": "KB"},
            {"artifact_id": "x1", "kind": "quiz", "title": "越权测验"},
        ],
    })
    log = []
    orch = StudyTeamOrchestrator(run_role, emit=log.append)
    report = orch.run("g", get_roles(["lecturer"]), run_id="r")

    assert {"role_id": "lecturer", "kind": "quiz"} in report["violations"]
    lecturer = next(r for r in report["roles"] if r["role_id"] == "lecturer")
    kept_kinds = {a["kind"] for a in lecturer["produced"]}
    assert kept_kinds == {"knowledge_base"}


def test_orchestrator_survives_a_failing_role():
    def run_role(spec, goal, upstream):
        if spec.role_id == "lecturer":
            raise RuntimeError("讲解官炸了")
        return RoleResult(spec.role_id, ev.STATUS_PRODUCED, summary="ok")

    log = []
    report = StudyTeamOrchestrator(run_role, emit=log.append).run(
        "g", default_team(), run_id="r"
    )
    assert "lecturer" in report["failed_roles"]
    assert report["ok"] is False
    # downstream roles still ran (team didn't crash) — full 7-role team
    assert {r["role_id"] for r in report["roles"]} == {
        "profiler", "lecturer", "quizmaster",
        "mindmapper", "filmmaker", "librarian", "guardian",
    }
