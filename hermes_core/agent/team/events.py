"""``agent_state`` stream-event builders for the study team.

Pure stdlib. Each function returns a plain dict shaped exactly as the SSE frame
the desk_server ``emit()`` closure forwards to the web panel (see
``A3-M0-智能体编队-实现方案.md`` §4.2). Keeping construction here means the
protocol has one source of truth and is unit-testable.
"""

from __future__ import annotations

import time
from typing import Dict, List, Mapping, Optional, Sequence

from .roles import RoleResult, RoleSpec

EVENT_TYPE = "agent_state"

# Role lifecycle states surfaced to the panel.
STATUS_WAITING = "waiting"
STATUS_WORKING = "working"
STATUS_PRODUCED = "produced"
STATUS_PASSED = "passed"
STATUS_FLAGGED = "flagged"
STATUS_FAILED = "failed"
STATUS_SKIPPED = "skipped"


def _now() -> float:
    return round(time.time(), 3)


def team_started(
    run_id: str,
    session_id: Optional[str],
    specs: Sequence[RoleSpec],
    layers: Sequence[Sequence[str]],
) -> Dict:
    """Opening frame: the DAG snapshot the panel draws lanes from."""
    edges: List[List[str]] = []
    for spec in specs:
        for dep in spec.depends_on:
            if any(s.role_id == dep for s in specs):
                edges.append([dep, spec.role_id])
    return {
        "type": EVENT_TYPE,
        "phase": "team_started",
        "session_id": session_id,
        "run_id": run_id,
        "ts": _now(),
        "dag": {
            "nodes": [
                {
                    "role_id": s.role_id,
                    "display": s.display,
                    "blurb": s.blurb,
                    "is_gate": s.is_gate,
                }
                for s in specs
            ],
            "edges": edges,
            "layers": [list(layer) for layer in layers],
        },
    }


def role_state(
    run_id: str,
    session_id: Optional[str],
    spec: RoleSpec,
    status: str,
    *,
    current_tool: Optional[str] = None,
    produced: Optional[Sequence[dict]] = None,
    summary: Optional[str] = None,
    error: Optional[str] = None,
    dropped: Optional[Sequence[dict]] = None,
    depth: int = 1,
    parent_id: str = "nina-core",
) -> Dict:
    """Per-role state-change frame."""
    return {
        "type": EVENT_TYPE,
        "phase": "role",
        "session_id": session_id,
        "run_id": run_id,
        "ts": _now(),
        "role_id": spec.role_id,
        "display": spec.display,
        "is_gate": spec.is_gate,
        "status": status,
        "current_tool": current_tool,
        "produced": list(produced or []),
        "dropped": list(dropped or []),
        "summary": summary,
        "error": error,
        "depth": depth,
        "parent_id": parent_id,
    }


def team_done(run_id: str, session_id: Optional[str], report: Mapping) -> Dict:
    """Closing frame with the run summary."""
    return {
        "type": EVENT_TYPE,
        "phase": "team_done",
        "session_id": session_id,
        "run_id": run_id,
        "ts": _now(),
        "report": dict(report),
    }
