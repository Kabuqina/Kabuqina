"""Frozen host-only Goal Task definition for the first desktop pilot.

The UI must not assemble verifier JSON or broaden tool access itself.  This
module owns the one Pilot 1 template and still delegates all persistence and
validation to :func:`cron.jobs.create_job`.
"""

from __future__ import annotations

from typing import Any, Dict

__all__ = ["pilot_manifest_goal_kwargs", "create_pilot_manifest_goal"]


def pilot_manifest_goal_kwargs(workdir: str) -> Dict[str, Any]:
    """Return a fresh, frozen Pilot 1 ``create_job`` argument dictionary."""
    return {
        "name": "Learning material inventory",
        "prompt": (
            "Inspect at most one new or changed supported file, then update "
            "learning-materials.json with its normalized relative path, SHA-256, "
            "and byte size. Do not write outside the selected workspace."
        ),
        "schedule": "every 10m",
        "deliver": "local",
        "mode": "goal",
        "goal": "Keep learning-materials.json complete for supported files in materials/",
        "workdir": workdir,
        "enabled_toolsets": ["file"],
        "verifier": {
            "kind": "manifest_complete",
            "config": {
                "manifest": "learning-materials.json",
                "roots": ["materials"],
                "extensions": [".pdf", ".docx", ".pptx"],
            },
        },
        "limits": {
            "max_runs": 40,
            "max_cost_usd": "5.00",
            "max_wall_seconds": 14_400,
            "deadline": None,
            "no_progress_limit": 3,
            "max_infrastructure_failures": 3,
        },
        "approval_mode": "ask_before_external_side_effect",
        "progress_delivery_every": 5,
    }


def create_pilot_manifest_goal(workdir: str) -> Dict[str, Any]:
    """Create one host-profile Pilot 1 Goal Task through core validation."""
    from cron.jobs import create_job

    return create_job(**pilot_manifest_goal_kwargs(workdir))
