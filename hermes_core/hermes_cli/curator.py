"""CLI helpers for ``hermes curator``."""

from __future__ import annotations

from typing import Any

from agent import curator as _curator
from tools import skill_usage


def _arg(args: Any, name: str, default: str = "") -> str:
    return str(getattr(args, name, default) or "").strip()


def _skill_arg(args: Any) -> str:
    return _arg(args, "skill") or _arg(args, "name")


def _refuse_non_agent_skill(skill: str, verb: str) -> int:
    print(f"Skill '{skill}' is bundled or hub-installed; cannot {verb}.")
    return 1


def _ensure_agent_skill(skill: str, verb: str) -> bool:
    if not skill:
        print(f"Usage: hermes curator {verb} <skill>")
        return False
    if not skill_usage.is_agent_created(skill):
        _refuse_non_agent_skill(skill, verb)
        return False
    if skill not in skill_usage.list_agent_created_skill_names():
        print(f"Skill '{skill}' not found.")
        return False
    return True


def _cmd_status(args: Any | None = None) -> int:
    state = _curator.load_state()
    print(f"enabled: {_curator.is_enabled()}")
    print(f"paused: {bool(state.get('paused'))}")
    print(f"last_run_at: {state.get('last_run_at') or '(never)'}")
    print(f"run_count: {state.get('run_count') or 0}")
    summary = state.get("last_run_summary")
    if summary:
        print(f"last_run_summary: {summary}")
    rows = skill_usage.agent_created_report()
    print(f"agent_created_skills: {len(rows)}")
    return 0


def _cmd_run(args: Any | None = None) -> int:
    result = _curator.run_curator_review(synchronous=True)
    print(result.get("summary") or result.get("status") or "curator run complete")
    return 0


def _cmd_pause(args: Any | None = None) -> int:
    _curator.set_paused(True)
    print("Curator paused.")
    return 0


def _cmd_resume(args: Any | None = None) -> int:
    _curator.set_paused(False)
    print("Curator resumed.")
    return 0


def _cmd_pin(args: Any) -> int:
    skill = _skill_arg(args)
    if not _ensure_agent_skill(skill, "pin"):
        return 1
    skill_usage.set_pinned(skill, True)
    print(f"Skill '{skill}' pinned.")
    return 0


def _cmd_unpin(args: Any) -> int:
    skill = _skill_arg(args)
    if not _ensure_agent_skill(skill, "unpin"):
        return 1
    skill_usage.set_pinned(skill, False)
    print(f"Skill '{skill}' unpinned.")
    return 0


def _cmd_restore(args: Any) -> int:
    skill = _skill_arg(args)
    if not skill:
        print("Usage: hermes curator restore <skill>")
        return 1
    ok, message = skill_usage.restore_skill(skill)
    print(message)
    return 0 if ok else 1


def dispatch(args: Any) -> int:
    subcommand = _arg(args, "subcommand") or _arg(args, "cmd") or "status"
    handlers = {
        "status": _cmd_status,
        "run": _cmd_run,
        "pause": _cmd_pause,
        "resume": _cmd_resume,
        "pin": _cmd_pin,
        "unpin": _cmd_unpin,
        "restore": _cmd_restore,
    }
    handler = handlers.get(subcommand)
    if handler is None:
        print(f"Unknown curator subcommand: {subcommand}")
        return 1
    return handler(args)
