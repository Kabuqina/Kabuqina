"""Iteration-scoped file-mutation boundary for bounded Goal Tasks.

The normal ``file`` toolset remains available for read/search/metadata work,
but a Pilot 1 Goal Task may make only one manifest write.  The scope is backed
by a :class:`contextvars.ContextVar` so concurrent scheduler workers cannot
share a mutable process-wide permission.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Mapping

__all__ = [
    "goal_manifest_write_scope",
    "goal_file_write_error",
    "goal_file_patch_error",
    "approved_manifest_path",
]


@dataclass
class _GoalFileScope:
    workdir: Path
    manifest: Path | None
    write_attempts: int = 0


_active_goal_file_scope: ContextVar[_GoalFileScope | None] = ContextVar(
    "active_goal_file_scope", default=None
)


def approved_manifest_path(
    *,
    workdir: Path,
    verifier_kind: str,
    verifier_config: Mapping[str, object],
) -> Path | None:
    """Return the sole writable Pilot 1 artifact, or ``None`` to deny writes."""
    if verifier_kind != "manifest_complete":
        return None
    raw = verifier_config.get("manifest")
    if not isinstance(raw, str) or not raw.strip():
        return None
    candidate = Path(raw)
    if candidate.is_absolute() or ".." in candidate.parts:
        return None
    return (workdir.resolve() / candidate).resolve()


@contextmanager
def goal_manifest_write_scope(
    *,
    workdir: Path,
    verifier_kind: str,
    verifier_config: Mapping[str, object],
) -> Iterator[None]:
    """Restrict file mutations for one Goal Task iteration.

    A malformed or non-manifest verifier intentionally grants no write access;
    future Goal templates must opt in explicitly rather than inheriting Pilot 1
    mutation authority.
    """
    root = workdir.resolve()
    scope = _GoalFileScope(
        workdir=root,
        manifest=approved_manifest_path(
            workdir=root,
            verifier_kind=verifier_kind,
            verifier_config=verifier_config,
        ),
    )
    token = _active_goal_file_scope.set(scope)
    try:
        yield
    finally:
        _active_goal_file_scope.reset(token)


def _resolve_candidate(path: object, workdir: Path) -> Path | None:
    if not isinstance(path, str) or not path.strip():
        return None
    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        candidate = workdir / candidate
    return candidate.resolve()


def goal_file_write_error(path: object) -> str | None:
    """Consume the one allowed Goal write, or return a deterministic denial."""
    scope = _active_goal_file_scope.get()
    if scope is None:
        return None
    if scope.manifest is None:
        return "Goal Task write blocked: this iteration has no approved manifest target."
    candidate = _resolve_candidate(path, scope.workdir)
    if candidate != scope.manifest:
        return "Goal Task write blocked: only the configured manifest may be written."
    if scope.write_attempts >= 1:
        return "Goal Task write blocked: the manifest may be written only once per iteration."
    # Count the attempt before dispatch. A backend error can be ambiguous about
    # whether it wrote anything, so retrying it would weaken the one-write bound.
    scope.write_attempts += 1
    return None


def goal_file_patch_error() -> str | None:
    """Pilot 1 forbids patch because V4A patches can mutate multiple paths."""
    if _active_goal_file_scope.get() is None:
        return None
    return "Goal Task patch blocked: use the single write_file manifest update instead."
