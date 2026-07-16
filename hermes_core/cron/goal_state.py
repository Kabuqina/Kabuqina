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
import math
import os
import re
import tempfile
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Literal, Mapping, Sequence, Union

from kabuqina_constants import get_kabuqina_home

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
_VALID_COST_ACCOUNTING: frozenset[str] = frozenset({"complete", "incomplete"})
_VALID_VERIFIER_OUTCOMES: frozenset[str] = frozenset({"pass", "fail", "error"})

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
    return (get_kabuqina_home() / "cron" / "goal-runs").resolve()


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
    if value is None:
        return None
    if not isinstance(value, str):
        raise GoalStateError("datetime fields must be ISO-8601 strings or null")
    return datetime.fromisoformat(value)


def _nonnegative_int(value: object, field: str) -> int:
    if type(value) is not int or value < 0:
        raise GoalStateError(f"{field} must be a non-negative integer")
    return value


def _nonnegative_float(value: object, field: str) -> float:
    if type(value) not in (int, float):
        raise GoalStateError(f"{field} must be a non-negative finite number")
    result = float(value)
    if not math.isfinite(result) or result < 0:
        raise GoalStateError(f"{field} must be a non-negative finite number")
    return result


def _nonnegative_decimal(value: object, field: str, *, serialized: bool) -> Decimal:
    expected_type = str if serialized else Decimal
    if not isinstance(value, expected_type):
        expected = "string" if serialized else "Decimal"
        raise GoalStateError(f"{field} must be a {expected}")
    try:
        result = Decimal(value)
    except (ValueError, ArithmeticError) as exc:
        raise GoalStateError(f"{field} must be a valid decimal") from exc
    if not result.is_finite() or result < 0:
        raise GoalStateError(f"{field} must be a non-negative finite decimal")
    return result


def _optional_string(value: object, field: str) -> str | None:
    if value is not None and not isinstance(value, str):
        raise GoalStateError(f"{field} must be a string or null")
    return value


def _validate_state(state: GoalRunState) -> None:
    if type(state.schema_version) is not int or state.schema_version != _SCHEMA_VERSION:
        raise GoalStateError(f"unsupported goal state schema version {state.schema_version!r}")
    _validate_job_id(state.job_id)
    if not isinstance(state.status, str) or state.status not in _VALID_STATUSES:
        raise GoalStateError(f"unknown goal status {state.status!r} for {state.job_id!r}")
    _nonnegative_int(state.iteration, "iteration")
    _nonnegative_decimal(
        state.accumulated_cost_usd, "accumulated_cost_usd", serialized=False
    )
    if (
        not isinstance(state.cost_accounting, str)
        or state.cost_accounting not in _VALID_COST_ACCOUNTING
    ):
        raise GoalStateError(f"unknown cost_accounting {state.cost_accounting!r}")
    _nonnegative_float(state.accumulated_wall_seconds, "accumulated_wall_seconds")
    _nonnegative_int(state.no_progress_count, "no_progress_count")
    _nonnegative_int(state.infrastructure_failures, "infrastructure_failures")
    if (
        state.last_verifier_outcome is not None
        and (
            not isinstance(state.last_verifier_outcome, str)
            or state.last_verifier_outcome not in _VALID_VERIFIER_OUTCOMES
        )
    ):
        raise GoalStateError(
            f"unknown last_verifier_outcome {state.last_verifier_outcome!r}"
        )
    for field in (
        "last_evidence_hash",
        "last_artifact_hash",
        "last_summary",
        "pause_reason",
        "last_error",
    ):
        _optional_string(getattr(state, field), field)
    for field in ("started_at", "completed_at", "updated_at"):
        value = getattr(state, field)
        if value is None:
            continue
        if not isinstance(value, datetime):
            raise GoalStateError(f"{field} must be a datetime or null")
        # Persisted timestamps must be timezone-aware: they serialize via
        # ``datetime.isoformat()`` and the Rust projection rejects any
        # ``updated_at`` without an offset as a corrupt state. Reject naive
        # datetimes here so both sides agree at the write boundary.
        if value.utcoffset() is None:
            raise GoalStateError(f"{field} must be timezone-aware")
    if state.updated_at is None:
        raise GoalStateError(f"goal state for {state.job_id!r} missing updated_at")


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
    if type(version) is not int or version != _SCHEMA_VERSION:
        raise GoalStateError(
            f"unsupported goal state schema version {version!r} for {job_id!r}"
        )

    stored_job_id = raw.get("job_id")
    if stored_job_id != job_id:
        raise GoalStateError(
            f"goal state job id mismatch: expected {job_id!r}, found {stored_job_id!r}"
        )

    status = raw.get("status")
    if not isinstance(status, str) or status not in _VALID_STATUSES:
        raise GoalStateError(f"unknown goal status {status!r} for {job_id!r}")

    try:
        iteration = _nonnegative_int(raw["iteration"], "iteration")
        accumulated_cost = _nonnegative_decimal(
            raw["accumulated_cost_usd"],
            "accumulated_cost_usd",
            serialized=True,
        )
        cost_accounting = raw["cost_accounting"]
        if (
            not isinstance(cost_accounting, str)
            or cost_accounting not in _VALID_COST_ACCOUNTING
        ):
            raise GoalStateError(f"unknown cost_accounting {cost_accounting!r}")
        accumulated_wall = _nonnegative_float(
            raw["accumulated_wall_seconds"], "accumulated_wall_seconds"
        )
        no_progress_count = _nonnegative_int(
            raw["no_progress_count"], "no_progress_count"
        )
        infrastructure_failures = _nonnegative_int(
            raw["infrastructure_failures"], "infrastructure_failures"
        )
        verifier_outcome = raw.get("last_verifier_outcome")
        if (
            verifier_outcome is not None
            and (
                not isinstance(verifier_outcome, str)
                or verifier_outcome not in _VALID_VERIFIER_OUTCOMES
            )
        ):
            raise GoalStateError(
                f"unknown last_verifier_outcome {verifier_outcome!r}"
            )
        optional_strings = {
            field: _optional_string(raw.get(field), field)
            for field in (
                "last_evidence_hash",
                "last_artifact_hash",
                "last_summary",
                "pause_reason",
                "last_error",
            )
        }
        updated_at = _dt_from_json(raw.get("updated_at"))
        if updated_at is None:
            raise GoalStateError(f"goal state for {job_id!r} missing updated_at")
        return GoalRunState(
            schema_version=_SCHEMA_VERSION,
            job_id=job_id,
            status=status,  # type: ignore[arg-type]
            iteration=iteration,
            accumulated_cost_usd=accumulated_cost,
            cost_accounting=cost_accounting,  # type: ignore[arg-type]
            accumulated_wall_seconds=accumulated_wall,
            no_progress_count=no_progress_count,
            infrastructure_failures=infrastructure_failures,
            last_evidence_hash=optional_strings["last_evidence_hash"],
            last_summary=optional_strings["last_summary"],
            last_verifier_outcome=verifier_outcome,  # type: ignore[arg-type]
            pause_reason=optional_strings["pause_reason"],
            last_error=optional_strings["last_error"],
            started_at=_dt_from_json(raw.get("started_at")),
            completed_at=_dt_from_json(raw.get("completed_at")),
            updated_at=updated_at,
            last_artifact_hash=optional_strings["last_artifact_hash"],
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
            raw = json.load(
                handle,
                parse_constant=lambda value: (_ for _ in ()).throw(
                    ValueError(f"non-finite JSON number {value}")
                ),
            )
    except (json.JSONDecodeError, ValueError) as exc:
        raise GoalStateError(f"corrupt goal state for {job_id!r}: {exc}") from exc
    except OSError as exc:
        raise GoalStateError(f"failed to read goal state for {job_id!r}: {exc}") from exc
    return _deserialize_state(raw, job_id)


def save_goal_state(state: GoalRunState) -> Path:
    """Atomically persist ``state`` to ``state.json`` and return its path."""
    _validate_state(state)
    run_dir = goal_run_dir(state.job_id)
    run_dir.mkdir(parents=True, exist_ok=True)
    target = run_dir / "state.json"
    tmp = run_dir / "state.json.tmp"

    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(
            _serialize_state(state),
            handle,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
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
