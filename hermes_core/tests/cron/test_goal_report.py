from __future__ import annotations

import contextvars
import json
from concurrent.futures import ThreadPoolExecutor

import pytest

from cron.goal_report import GoalReportError, goal_report_scope
from tools.registry import registry
import tools.goal_report_tool  # noqa: F401 - module-level registration is the contract


def _valid_args(**changes):
    args = {
        "status": "progress",
        "summary": "indexed one document",
        "artifacts": ["learning-materials.json"],
        "evidence": {"before": 1, "after": 2},
        "next_step": "index the next document",
        "external_side_effects": [],
    }
    args.update(changes)
    return args


def _dispatch(args):
    return json.loads(registry.dispatch("goal_report", args))


def test_tool_is_registered_only_in_internal_toolset():
    entry = registry.get_entry("goal_report")

    assert entry is not None
    assert entry.toolset == "goal_internal"
    assert entry.check_fn is None


def test_tool_rejects_calls_without_active_scope():
    result = _dispatch(_valid_args())

    assert "error" in result
    assert "active goal" in result["error"]


def test_scope_accepts_exactly_one_valid_report_and_resets_after_exit():
    with goal_report_scope("abc123def456", 3) as collector:
        result = _dispatch(_valid_args())
        assert result == {
            "success": True,
            "job_id": "abc123def456",
            "iteration": 3,
        }
        assert collector.report is not None
        assert collector.report.status == "progress"
        assert collector.report.artifacts == ("learning-materials.json",)

        duplicate = _dispatch(_valid_args(summary="second report"))
        assert "error" in duplicate
        assert "already" in duplicate["error"]

    assert "error" in _dispatch(_valid_args())


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"unknown": True}, "unknown"),
        ({"status": "completed"}, "status"),
        ({"summary": "x" * 4001}, "summary"),
        ({"next_step": "x" * 4001}, "next_step"),
        ({"artifacts": [f"file-{i}" for i in range(201)]}, "artifacts"),
        ({"evidence": {"body": "x" * (64 * 1024)}}, "evidence"),
        ({"evidence": {"not_json": object()}}, "JSON"),
        ({"external_side_effects": "none"}, "external_side_effects"),
    ],
)
def test_tool_rejects_unknown_keys_and_oversized_or_invalid_fields(changes, message):
    with goal_report_scope("abc123def456", 1) as collector:
        result = _dispatch(_valid_args(**changes))

    assert "error" in result
    assert message.lower() in result["error"].lower()
    assert collector.report is None


def test_independently_created_scopes_are_isolated_across_copied_contexts():
    def run(job_id, summary):
        with goal_report_scope(job_id, 1) as collector:
            assert _dispatch(_valid_args(summary=summary))["success"] is True
            return collector.report.summary

    first_context = contextvars.copy_context()
    second_context = contextvars.copy_context()

    assert first_context.run(run, "abc123def456", "first") == "first"
    assert second_context.run(run, "def456abc123", "second") == "second"


def test_parallel_threads_keep_scopes_isolated():
    def run(job_id):
        with goal_report_scope(job_id, 7) as collector:
            assert _dispatch(_valid_args(summary=job_id))["success"] is True
            return collector.job_id, collector.report.summary

    ids = ["abc123def456", "def456abc123"]
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(run, ids))

    assert sorted(results) == sorted((job_id, job_id) for job_id in ids)


def test_collector_rejects_direct_second_record():
    with goal_report_scope("abc123def456", 1) as collector:
        collector.record(_valid_args())
        with pytest.raises(GoalReportError):
            collector.record(_valid_args())

