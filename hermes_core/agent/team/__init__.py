"""小娜的智能体编队（Nina Core study team）.

A thin, dependency-free orchestration layer that turns the existing
``delegate_task`` sub-agent capability into a role-based multi-agent team
(画像师 / 讲解官 / 出题官 / 守门人 …) coordinated over a small DAG.

Design notes
------------
* This package imports **only the standard library** so the core
  (roles / dag / events / orchestrator) is unit-testable without an LLM,
  a provider key, or the rest of the Hermes runtime.
* All runtime coupling (spawning real child ``AIAgent`` instances, capturing
  learning drafts, streaming ``agent_state`` events) lives one layer up in
  ``tools/team_tool.py`` and is injected into the orchestrator as callables.
* The student only ever sees "小娜" — role agents run quietly in the
  background; this module is the backstage编队, not a second persona.
"""

from .roles import RoleSpec, RoleResult, ROLE_REGISTRY, default_team, get_roles
from .dag import toposort_layers, DagError
from .orchestrator import StudyTeamOrchestrator
from . import events

__all__ = [
    "RoleSpec",
    "RoleResult",
    "ROLE_REGISTRY",
    "default_team",
    "get_roles",
    "toposort_layers",
    "DagError",
    "StudyTeamOrchestrator",
    "events",
]
