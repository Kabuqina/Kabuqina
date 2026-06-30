"""Durable, profile-local state for the Bounded Goal Runner (G0 foundation).

This module owns the on-disk contract for a Goal Task's run state and its
immutable per-iteration evidence records. It is engine-neutral: it never imports
LangGraph, the inner agent, or any provider SDK, and it never reads the clock,
config, or model. Callers inject ``now`` explicitly so the persistence layer
stays deterministic and testable.

File layout, scoped to the active ``HERMES_HOME``::

    <HERMES_HOME>/cron/goal-runs/<job-id>/state.json
    <HERMES_HOME>/cron/goal-runs/<job-id>/iterations/000001/report.json
    <HERMES_HOME>/cron/goal-runs/<job-id>/iterations/000001/verification.json
    <HERMES_HOME>/cron/goal-runs/<job-id>/iterations/000001/transition.json

``state.json`` is mutable and written atomically (temp file -> fsync ->
``os.replace``). Iteration records are write-once: they are created with
exclusive-create semantics so a retry or recovery path can never rewrite the
evidence used for a prior decision.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Literal, Mapping, Sequence, Union

from hermes_constants import get_hermes_home

__all__ = [
    "JSONValue",
    "GoalStatus",
    "GoalLimits",
    "GoalReport",
    "GoalDefinition",
    "GoalRunState",
    "GoalStateError",
    "goal_state_to_json",
    "goal_state_from_json",
    "goal_run_dir",
    "new_goal_state",
    "load_goal_state",
    "save_goal_state",
    "save_iteration_record",
]

# Recursive JSON value type used across the goal modules.
JSONValue = Union[
    None, bool, int, float, str, Mapping[str, "JSONValue"], Sequence["JSONValue"]
]

GoalStatus = Literal[
    "scheduled",
    "running",
    "verifying",
    "completed",
    "paused",
    "failed",
    "cancelled",
]

_VALID_STATUSES: frozenset[str] = frozenset(
    {
        "scheduled",
        "running",
        "verifying",
        "completed",
        "paused",
        "failed",
        "cancelled",
    }
)

_JOB_ID_RE = re.compile(r"^[a-f0-9]{12}$")
_SCHEMA_VERSION = 1
_RECORD_KINDS: frozenset[str] = frozenset({"report", "verification", "transition"})


class GoalStateError(Exception):
    """Raised for invalid job IDs, malformed committed state, or rewrite attempts."""


@dataclass(frozen=True)
class GoalLimits:
    """Bounds that pause or fail a goal before it can run unbounded."""

    max_runs: int
    max_cost_usd: Decimal | None
    max_wall_seconds: int
    deadline: datetime | None
    no_progress_limit: int
    max_infrastructure_failures: int = 3


@dataclass(frozen=True)
class GoalReport:
    """A worker's self-report for one iteration — evidence, not authority."""

    status: Literal["progress", "candidate_done", "blocked"]
    summary: str
    artifacts: tuple[str, ...]
    evidence: Mapping[str, "JSONValue"]
    next_step: str | None
    external_side_effects: tuple[str, ...]


@dataclass(frozen=True)
class GoalDefinition:
    """The immutable specification of a Goal Task."""

    job_id: str
    objective: str
    iteration_prompt: str
    workdir: Path
    verifier_kind: str
    verifier_config: Mapping[str, "JSONValue"]
    limits: GoalLimits
    enabled_toolsets: tuple[str, ...]
    approval_mode: Literal["ask_before_external_side_effect", "always"]
    progress_delivery_every: int | None


@dataclass(frozen=True)
class GoalRunState:
    """The mutable, durable run state for a Goal Task."""

    schema_version: Literal[1]
    job_id: str
    status: GoalStatus
    iteration: int
    accumulated_cost_usd: Decimal
    cost_accounting: Literal["complete", "incomplete"]
    accumulated_wall_seconds: float
    no_progress_count: int
    infrastructure_failures: int
    last_evidence_hash: str | None
    last_summary: str | None
    last_verifier_outcome: Literal["pass", "fail", "error"] | None
    pause_reason: str | None
    last_error: str | None
    started_at: datetime | None
    completed_at: datetime | None
    updated_at: datetime
    last_artifact_hash: str | None = None


# ---------------------------------------------------------------------------
# Paths & validation
# ---------------------------------------------------------------------------

def _validate_job_id(job_id: str) -> str:
    if not isinstance(job_id, str) or not _JOB_ID_RE.match(job_id):
        raise GoalStateError(
            f"invalid goal job id {job_id!r}: must match ^[a-f0-9]{{12}}$"
        )
    return job_id


def _goal_runs_root() -> Path:
    return (get_hermes_home() / "cron" / "goal-runs").resolve()


def goal_run_dir(job_id: str) -> Path:
    """Return the confined goal-run directory for ``job_id``.

    The job id is validated and the resolved directory's parent is confirmed to
    be the resolved ``goal-runs`` root, so a crafted id cannot escape the tree.
    """
    _validate_job_id(job_id)
    root = _goal_runs_root()
    candidate = (root / job_id).resolve()
    if candidate.parent != root:
        raise GoalStateError(f"goal run dir for {job_id!r} escapes the goal-runs root")
    return candidate


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------

def new_goal_state(job_id: str, *, now: datetime) -> GoalRunState:
    """Return the initial ``scheduled`` state for a fresh Goal Task."""
    _validate_job_id(job_id)
    return GoalRunState(
        schema_version=_SCHEMA_VERSION,
        job_id=job_id,
        status="scheduled",
        iteration=0,
        accumulated_cost_usd=Decimal("0"),
        cost_accounting="complete",
        accumulated_wall_seconds=0.0,
        no_progress_count=0,
        infrastructure_failures=0,
        last_evidence_hash=None,
        last_summary=None,
        last_verifier_outcome=None,
        pause_reason=None,
        last_error=None,
        started_at=None,
        completed_at=None,
        updated_at=now,
        last_artifact_hash=None,
    )


# ---------------------------------------------------------------------------
# Serialization — decimals and datetimes persist as strings.
# ---------------------------------------------------------------------------

def _dt_to_json(value: datetime | None) -> str | None:
    return None if value is None else value.isoformat()


def _dt_from_json(value: object) -> datetime | None:
    return None if value is None else datetime.fromisoformat(str(value))


def _serialize_state(state: GoalRunState) -> dict:
    return {
        "schema_version": state.schema_version,
        "job_id": state.job_id,
        "status": state.status,
        "iteration": state.iteration,
        "accumulated_cost_usd": str(state.accumulated_cost_usd),
        "cost_accounting": state.cost_accounting,
        "accumulated_wall_seconds": state.accumulated_wall_seconds,
        "no_progress_count": state.no_progress_count,
        "infrastructure_failures": state.infrastructure_failures,
        "last_evidence_hash": state.last_evidence_hash,
        "last_summary": state.last_summary,
        "last_verifier_outcome": state.last_verifier_outcome,
        "pause_reason": state.pause_reason,
        "last_error": state.last_error,
        "started_at": _dt_to_json(state.started_at),
        "completed_at": _dt_to_json(state.completed_at),
        "updated_at": _dt_to_json(state.updated_at),
        "last_artifact_hash": state.last_artifact_hash,
    }


def _deserialize_state(raw: object, job_id: str) -> GoalRunState:
    if not isinstance(raw, dict):
        raise GoalStateError(f"goal state for {job_id!r} is not a JSON object")

    version = raw.get("schema_version")
    if version != _SCHEMA_VERSION:
        raise GoalStateError(
            f"unsupported goal state schema version {version!r} for {job_id!r}"
        )

    stored_job_id = raw.get("job_id")
    if stored_job_id != job_id:
        raise GoalStateError(
            f"goal state job id mismatch: expected {job_id!r}, found {stored_job_id!r}"
        )

    status = raw.get("status")
    if status not in _VALID_STATUSES:
        raise GoalStateError(f"unknown goal status {status!r} for {job_id!r}")

    try:
        updated_at = _dt_from_json(raw.get("updated_at"))
        if updated_at is None:
            raise GoalStateError(f"goal state for {job_id!r} missing updated_at")
        return GoalRunState(
            schema_version=_SCHEMA_VERSION,
            job_id=job_id,
            status=status,  # type: ignore[arg-type]
            iteration=int(raw["iteration"]),
            accumulated_cost_usd=Decimal(str(raw["accumulated_cost_usd"])),
            cost_accounting=raw["cost_accounting"],
            accumulated_wall_seconds=float(raw["accumulated_wall_seconds"]),
            no_progress_count=int(raw["no_progress_count"]),
            infrastructure_failures=int(raw["infrastructure_failures"]),
            last_evidence_hash=raw.get("last_evidence_hash"),
            last_summary=raw.get("last_summary"),
            last_verifier_outcome=raw.get("last_verifier_outcome"),
            pause_reason=raw.get("pause_reason"),
            last_error=raw.get("last_error"),
            started_at=_dt_from_json(raw.get("started_at")),
            completed_at=_dt_from_json(raw.get("completed_at")),
            updated_at=updated_at,
            last_artifact_hash=raw.get("last_artifact_hash"),
        )
    except GoalStateError:
        raise
    except (KeyError, ValueError, TypeError, ArithmeticError) as exc:
        raise GoalStateError(
            f"malformed goal state for {job_id!r}: {exc}"
        ) from exc


def goal_state_to_json(state: GoalRunState) -> dict[str, JSONValue]:
    """Return the canonical JSON representation used by durable state records."""
    return _serialize_state(state)


def goal_state_from_json(raw: object, job_id: str) -> GoalRunState:
    """Decode state while binding it to the trusted containing job identity."""
    return _deserialize_state(raw, job_id)


# ---------------------------------------------------------------------------
# Load / save
# ---------------------------------------------------------------------------

def load_goal_state(job_id: str) -> GoalRunState | None:
    """Load committed state for ``job_id``, or ``None`` if none is committed.

    A stale ``state.json.tmp`` is never read — only ``state.json`` is committed
    state. Malformed JSON and unsupported schema versions raise ``GoalStateError``
    rather than being silently reset.
    """
    target = goal_run_dir(job_id) / "state.json"
    if not target.exists():
        return None
    try:
        with open(target, "r", encoding="utf-8") as handle:
            raw = json.load(handle)
    except json.JSONDecodeError as exc:
        raise GoalStateError(f"corrupt goal state for {job_id!r}: {exc}") from exc
    except OSError as exc:
        raise GoalStateError(f"failed to read goal state for {job_id!r}: {exc}") from exc
    return _deserialize_state(raw, job_id)


def save_goal_state(state: GoalRunState) -> Path:
    """Atomically persist ``state`` to ``state.json`` and return its path."""
    run_dir = goal_run_dir(state.job_id)
    run_dir.mkdir(parents=True, exist_ok=True)
    target = run_dir / "state.json"
    tmp = run_dir / "state.json.tmp"

    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(_serialize_state(state), handle, indent=2, sort_keys=True)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, target)
    return target


def save_iteration_record(
    job_id: str,
    iteration: int,
    kind: Literal["report", "verification", "transition"],
    payload: Mapping[str, "JSONValue"],
) -> Path:
    """Write an immutable per-iteration evidence record and return its path.

    The record is created with exclusive-create semantics: if the same record
    already exists, ``GoalStateError`` is raised so a retry or recovery path can
    never rewrite evidence behind a prior decision.
    """
    if kind not in _RECORD_KINDS:
        raise GoalStateError(f"unknown iteration record kind {kind!r}")
    if not isinstance(iteration, int) or iteration < 1:
        raise GoalStateError(f"invalid iteration index {iteration!r}")

    serialized = json.dumps(
        payload,
        indent=2,
        sort_keys=True,
        default=_json_default,
    )
    iteration_dir = goal_run_dir(job_id) / "iterations" / f"{iteration:06d}"
    iteration_dir.mkdir(parents=True, exist_ok=True)
    target = iteration_dir / f"{kind}.json"

    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=iteration_dir,
            prefix=f".{kind}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            tmp_path = Path(handle.name)
            handle.write(serialized)
            handle.flush()
            os.fsync(handle.fileno())
        # Publishing by hard link is atomic and never replaces an existing
        # record. The temporary file and target are on the same filesystem.
        os.link(tmp_path, target)
    except FileExistsError as exc:
        raise GoalStateError(
            f"iteration record {kind} for {job_id!r}#{iteration} already exists"
        ) from exc
    finally:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)
    return target


def _json_default(value: object) -> str:
    """Coerce Decimal/datetime into strings so evidence payloads stay JSON-safe."""
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(f"object of type {type(value).__name__} is not JSON serializable")
