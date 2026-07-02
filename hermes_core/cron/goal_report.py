"""Iteration-scoped collector for one bounded-goal worker report."""

from __future__ import annotations

import json
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Iterator, Mapping

from cron.goal_state import GoalReport, JSONValue

__all__ = [
    "GoalReportError",
    "GoalReportCollector",
    "goal_report_scope",
    "record_active_goal_report",
]


_REPORT_KEYS = frozenset(
    {
        "status",
        "summary",
        "artifacts",
        "evidence",
        "next_step",
        "external_side_effects",
    }
)
_REPORT_STATUSES = frozenset({"progress", "candidate_done", "blocked"})
_MAX_TEXT_CHARS = 4_000
_MAX_ARTIFACTS = 200
_MAX_EXTERNAL_SIDE_EFFECTS = 200
_MAX_EVIDENCE_BYTES = 64 * 1024


class GoalReportError(ValueError):
    """Raised when a report is invalid, duplicated, or outside a scope."""


@dataclass
class GoalReportCollector:
    job_id: str
    iteration: int
    report: GoalReport | None = None

    def record(self, payload: Mapping[str, object]) -> GoalReport:
        if self.report is not None:
            raise GoalReportError("goal report was already recorded for this iteration")
        if not isinstance(payload, Mapping):
            raise GoalReportError("goal report must be an object")
        keys = frozenset(payload)
        unknown = sorted(keys - _REPORT_KEYS)
        missing = sorted(_REPORT_KEYS - keys)
        if unknown:
            raise GoalReportError(f"unknown goal report fields: {', '.join(unknown)}")
        if missing:
            raise GoalReportError(f"missing goal report fields: {', '.join(missing)}")

        status = payload["status"]
        if status not in _REPORT_STATUSES:
            raise GoalReportError("status must be progress, candidate_done, or blocked")
        summary = _bounded_text(payload["summary"], "summary", required=True)
        next_step_value = payload["next_step"]
        next_step = (
            None
            if next_step_value is None
            else _bounded_text(next_step_value, "next_step", required=False)
        )
        artifacts = _string_sequence(
            payload["artifacts"], "artifacts", maximum=_MAX_ARTIFACTS
        )
        external_side_effects = _string_sequence(
            payload["external_side_effects"],
            "external_side_effects",
            maximum=_MAX_EXTERNAL_SIDE_EFFECTS,
        )
        evidence = payload["evidence"]
        if not isinstance(evidence, Mapping):
            raise GoalReportError("evidence must be a JSON object")
        try:
            encoded = json.dumps(
                evidence,
                allow_nan=False,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
        except (TypeError, ValueError) as exc:
            raise GoalReportError("evidence must contain only JSON values") from exc
        if len(encoded) > _MAX_EVIDENCE_BYTES:
            raise GoalReportError("evidence exceeds the 64 KiB serialized limit")

        report = GoalReport(
            status=status,  # type: ignore[arg-type]
            summary=summary,
            artifacts=artifacts,
            evidence=dict(evidence),  # defensive snapshot of the top-level mapping
            next_step=next_step,
            external_side_effects=external_side_effects,
        )
        self.report = report
        return report


def _bounded_text(value: object, field: str, *, required: bool) -> str:
    if not isinstance(value, str):
        raise GoalReportError(f"{field} must be a string")
    if required and not value.strip():
        raise GoalReportError(f"{field} must not be empty")
    if len(value) > _MAX_TEXT_CHARS:
        raise GoalReportError(f"{field} exceeds the 4000 character limit")
    return value


def _string_sequence(value: object, field: str, *, maximum: int) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        raise GoalReportError(f"{field} must be a list")
    if len(value) > maximum:
        raise GoalReportError(f"{field} exceeds the {maximum} entry limit")
    if not all(isinstance(item, str) and item for item in value):
        raise GoalReportError(f"{field} entries must be non-empty strings")
    return tuple(value)


_active_goal_report: ContextVar[GoalReportCollector | None] = ContextVar(
    "active_goal_report", default=None
)


@contextmanager
def goal_report_scope(job_id: str, iteration: int) -> Iterator[GoalReportCollector]:
    collector = GoalReportCollector(job_id=job_id, iteration=iteration)
    token = _active_goal_report.set(collector)
    try:
        yield collector
    finally:
        _active_goal_report.reset(token)


def record_active_goal_report(payload: Mapping[str, object]) -> GoalReportCollector:
    collector = _active_goal_report.get()
    if collector is None:
        raise GoalReportError("goal_report requires an active goal-report scope")
    collector.record(payload)
    return collector

