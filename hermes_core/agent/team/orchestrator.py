"""StudyTeamOrchestrator — deterministic DAG execution for 小娜的编队.

Pure stdlib + this package. It does NOT know how to spawn a real child agent;
the caller injects a ``run_role`` callable. This keeps the orchestration logic
(topological ordering, blackboard result-passing, allowed_kinds enforcement,
agent_state event sequence) fully unit-testable without an LLM.

Contract of the injected ``run_role``::

    run_role(spec: RoleSpec, goal: str, upstream: Mapping[str, RoleResult]) -> RoleResult

``upstream`` maps each of ``spec.depends_on`` to the already-computed
``RoleResult`` (blackboard view). The production implementation lives in
``tools/team_tool.py`` and wraps ``delegate_tool._build_child_agent``.
"""

from __future__ import annotations

from typing import Callable, Dict, List, Mapping, Optional, Sequence

from . import events
from .dag import toposort_layers
from .roles import RoleResult, RoleSpec

RunRole = Callable[[RoleSpec, str, Mapping[str, RoleResult]], RoleResult]
Emit = Callable[[dict], None]


class StudyTeamOrchestrator:
    def __init__(self, run_role: RunRole, emit: Optional[Emit] = None):
        self._run_role = run_role
        self._emit = emit or (lambda _evt: None)

    # ------------------------------------------------------------------ #
    def run(
        self,
        goal: str,
        specs: Sequence[RoleSpec],
        *,
        run_id: str,
        session_id: Optional[str] = None,
    ) -> Dict:
        """Execute the team over the DAG derived from ``specs``. Returns a report."""
        spec_by_id: Dict[str, RoleSpec] = {s.role_id: s for s in specs}
        deps = {s.role_id: s.depends_on for s in specs}
        layers = toposort_layers(list(spec_by_id), deps)  # raises DagError on cycle

        self._emit(events.team_started(run_id, session_id, list(specs), layers))

        blackboard: Dict[str, RoleResult] = {}
        violations: List[dict] = []
        produced_count = 0

        for layer in layers:
            for role_id in layer:  # M0: sequential (ContextVar-safe); concurrency later
                spec = spec_by_id[role_id]
                self._emit(
                    events.role_state(run_id, session_id, spec, events.STATUS_WORKING)
                )

                upstream = {
                    rid: blackboard[rid]
                    for rid in spec.depends_on
                    if rid in blackboard
                }

                try:
                    result = self._run_role(spec, goal, upstream)
                    if result is None:
                        result = RoleResult(role_id, events.STATUS_SKIPPED, summary="(no result)")
                except Exception as exc:  # a failing role must not kill the team
                    result = RoleResult(role_id, events.STATUS_FAILED, error=str(exc))

                # D8: enforce allowed_kinds — the contract validates payloads,
                # not "may this role emit this kind". Gate roles emit nothing.
                kept: List[dict] = []
                dropped: List[dict] = []
                for art in result.produced:
                    kind = (art or {}).get("kind", "")
                    if not spec.is_gate and spec.allows_kind(kind):
                        kept.append(art)
                    else:
                        dropped.append(art)
                        violations.append({"role_id": role_id, "kind": kind})
                result = result.with_produced(kept)
                blackboard[role_id] = result
                produced_count += len(kept)

                self._emit(
                    events.role_state(
                        run_id,
                        session_id,
                        spec,
                        result.status,
                        produced=kept,
                        dropped=dropped,
                        summary=result.summary,
                        error=result.error,
                    )
                )

        report = self._build_report(specs, blackboard, violations, produced_count)
        self._emit(events.team_done(run_id, session_id, report))
        return report

    # ------------------------------------------------------------------ #
    @staticmethod
    def _build_report(
        specs: Sequence[RoleSpec],
        blackboard: Mapping[str, RoleResult],
        violations: Sequence[dict],
        produced_count: int,
    ) -> Dict:
        roles = []
        for s in specs:
            res = blackboard.get(s.role_id)
            roles.append(
                {
                    "role_id": s.role_id,
                    "display": s.display,
                    "status": res.status if res else events.STATUS_SKIPPED,
                    "produced": list(res.produced) if res else [],
                    "summary": (res.summary if res else "") or "",
                }
            )
        failed = [r["role_id"] for r in roles if r["status"] == events.STATUS_FAILED]
        return {
            "roles": roles,
            "drafts_total": produced_count,
            "violations": list(violations),
            "failed_roles": failed,
            "ok": not failed,
        }
