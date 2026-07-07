"""``convene_study_team`` — the tool小娜 calls to convene her backstage编队.

This is the runtime bridge between the pure orchestration core
(``agent/team``) and the Hermes agent runtime. It:

* builds each role as a child ``AIAgent`` (reusing ``delegate_tool``), running
  it **synchronously in the current thread** so the child inherits the active
  learning-context / created-callback ContextVars bound by the desk chat turn
  (this is why role drafts land in ``learning.db`` and stream out);
* captures the ``learning.output.created`` signals each role emits, so the
  panel can attribute drafts to roles, while still forwarding them to the desk
  SSE callback;
* streams ``agent_state`` frames through the agent's ``_team_state_callback``
  (wired by desk_server), falling back to a no-op on the CLI.

Dispatch is intercepted in ``run_agent.AIAgent._invoke_tool`` /
``_dispatch_convene_study_team`` (like ``delegate_task``) so ``parent_agent``
can be injected — the registry ``handler`` below is only for schema/discovery.
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Callable, List, Mapping, Optional, Sequence

from agent.team import StudyTeamOrchestrator, get_roles
from agent.team import events as ev
from agent.team.roles import RoleResult, RoleSpec

logger = logging.getLogger("tools")

_DEFAULT_CHILD_ITERATIONS = 12


# --------------------------------------------------------------------------- #
# Contract sanity check (best-effort; never fatal)
# --------------------------------------------------------------------------- #

def _validate_roles_against_contract(specs: Sequence[RoleSpec]) -> None:
    """Warn if a role declares a kind the learning contract doesn't know."""
    try:
        from learning.learning_contract import KINDS as _KINDS
    except Exception:
        return
    for spec in specs:
        unknown = set(spec.allowed_kinds) - set(_KINDS)
        if unknown:
            logger.warning(
                "study-team role '%s' declares unknown kinds %s (contract: %s)",
                spec.role_id, sorted(unknown), sorted(_KINDS),
            )


# --------------------------------------------------------------------------- #
# Production run_role: spawn a child AIAgent per role, in-thread
# --------------------------------------------------------------------------- #

def _extract_summary(result: object) -> str:
    if isinstance(result, dict):
        text = result.get("final_response") or result.get("response") or ""
    else:
        text = getattr(result, "final_response", "") or ""
    return (text or "").strip().replace("\n", " ")[:280]


def _make_run_role(parent_agent, run_id: str, max_iterations: int) -> Callable:
    import model_tools
    from tools.delegate_tool import _build_child_agent
    from learning.output_writer import (
        _active_created_callback,
        learning_created_callback_scope,
    )

    def run_role(spec: RoleSpec, goal: str, upstream: Mapping[str, RoleResult]) -> RoleResult:
        role_prompt = spec.build_prompt(goal, upstream)

        # Capture this role's created drafts while still forwarding to the
        # desk callback bound by the outer chat turn.
        captured: List[dict] = []
        outer_cb = _active_created_callback.get()

        def _capture(sig: dict) -> None:
            try:
                captured.append(
                    {
                        "artifact_id": sig.get("artifact_id"),
                        "kind": sig.get("kind"),
                        "title": sig.get("title") or sig.get("kind") or "",
                    }
                )
            except Exception:
                pass
            if outer_cb is not None:
                try:
                    outer_cb(sig)
                except Exception:
                    pass

        # Child construction mutates the module-global resolved tool names;
        # save/restore around the run (see delegate_tool._run_single_child).
        saved_names = list(getattr(model_tools, "_last_resolved_tool_names", []) or [])
        try:
            child = _build_child_agent(
                task_index=0,
                goal=role_prompt,
                context=None,
                toolsets=list(spec.toolsets) or None,
                model=None,  # M0: inherit parent's provider/model (tier is advisory)
                max_iterations=max_iterations,
                task_count=1,
                parent_agent=parent_agent,
                role="leaf",
            )
            with learning_created_callback_scope(_capture):
                result = child.run_conversation(
                    role_prompt, task_id=f"{run_id}-{spec.role_id}"
                )
            summary = _extract_summary(result) or f"{spec.display} 已完成"
            status = ev.STATUS_PASSED if spec.is_gate else ev.STATUS_PRODUCED
            return RoleResult(spec.role_id, status, summary=summary, produced=tuple(captured))
        except Exception as exc:  # surfaced by the orchestrator as a failed role
            logger.warning("study-team role '%s' failed: %s", spec.role_id, exc)
            return RoleResult(spec.role_id, ev.STATUS_FAILED, error=str(exc))
        finally:
            try:
                model_tools._last_resolved_tool_names = saved_names
            except Exception:
                pass

    return run_role


def _resolve_emit(parent_agent) -> Optional[Callable[[dict], None]]:
    """The desk layer sets ``_team_state_callback``; CLI has none (no-op)."""
    cb = getattr(parent_agent, "_team_state_callback", None)
    return cb if callable(cb) else None


# --------------------------------------------------------------------------- #
# Entry point (called from run_agent._dispatch_convene_study_team)
# --------------------------------------------------------------------------- #

def convene_study_team(
    goal: str,
    roles: Optional[Sequence[str]] = None,
    parent_agent=None,
    max_iterations: Optional[int] = None,
) -> str:
    if parent_agent is None:
        return json.dumps(
            {"error": "convene_study_team must run inside an agent (no parent_agent)"},
            ensure_ascii=False,
        )
    if not (goal or "").strip():
        return json.dumps({"error": "goal is required"}, ensure_ascii=False)

    try:
        specs = get_roles(list(roles) if roles else None)
    except KeyError as exc:
        return json.dumps({"error": f"unknown role: {exc}"}, ensure_ascii=False)
    _validate_roles_against_contract(specs)

    run_id = "team-" + uuid.uuid4().hex[:8]
    run_role = _make_run_role(
        parent_agent, run_id, max_iterations or _DEFAULT_CHILD_ITERATIONS
    )
    orch = StudyTeamOrchestrator(run_role, emit=_resolve_emit(parent_agent))
    report = orch.run(
        goal, specs, run_id=run_id, session_id=getattr(parent_agent, "session_id", None)
    )

    # Concise result for 小娜 (the main agent) to narrate to the student.
    return json.dumps(
        {
            "ok": report["ok"],
            "run_id": run_id,
            "drafts_total": report["drafts_total"],
            "roles": [
                {
                    "role_id": r["role_id"],
                    "display": r["display"],
                    "status": r["status"],
                    "drafts": len(r["produced"]),
                }
                for r in report["roles"]
            ],
            "violations": report["violations"],
            "note": "草稿已进入草稿箱，请在 STUDY 里审核后自行激活。",
        },
        ensure_ascii=False,
    )


# --------------------------------------------------------------------------- #
# Schema + registration
# --------------------------------------------------------------------------- #

CONVENE_STUDY_TEAM_SCHEMA = {
    "name": "convene_study_team",
    "description": (
        "召集小娜的学习智能体编队（画像师/讲解官/出题官/守门人）协同为学生生成"
        "个性化学习资源。多个角色子智能体按 DAG 协作，各自把产物写入草稿箱（draft），"
        "由守门人把关；激活仍由学生在 STUDY 完成。用于'把某章/某课做成复习资料/题库'"
        "这类需要多类资源协同产出的请求。"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "goal": {
                "type": "string",
                "description": "本次编队的总目标，例如'把《装饰器与闭包》做成复习资料并配套练习'。",
            },
            "roles": {
                "type": "array",
                "items": {
                    "type": "string",
                    "enum": ["profiler", "lecturer", "quizmaster", "guardian"],
                },
                "description": "可选：指定参与的角色子集；省略则用默认编队（守门人始终参与）。",
            },
        },
        "required": ["goal"],
    },
}


from tools.registry import registry  # noqa: E402

registry.register(
    name="convene_study_team",
    toolset="orchestration",
    schema=CONVENE_STUDY_TEAM_SCHEMA,
    # Real dispatch is intercepted in run_agent._invoke_tool to inject
    # parent_agent (see _AGENT_LOOP_TOOLS); this handler is a safety net.
    handler=lambda args, **kw: convene_study_team(
        goal=args.get("goal"),
        roles=args.get("roles"),
        parent_agent=kw.get("parent_agent"),
    ),
    emoji="🧩",
)
