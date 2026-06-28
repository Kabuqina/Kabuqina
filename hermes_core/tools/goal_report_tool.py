"""Internal, iteration-scoped report tool for bounded goal workers."""

from __future__ import annotations

from cron.goal_report import GoalReportError, record_active_goal_report
from tools.registry import registry, tool_error, tool_result


GOAL_REPORT_SCHEMA = {
    "name": "goal_report",
    "description": (
        "Submit the single structured report for this Goal Task iteration. "
        "Never include secrets, credentials, hidden reasoning, or raw document bodies."
    ),
    "parameters": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "status": {
                "type": "string",
                "enum": ["progress", "candidate_done", "blocked"],
            },
            "summary": {"type": "string", "maxLength": 4000},
            "artifacts": {
                "type": "array",
                "maxItems": 200,
                "items": {"type": "string"},
            },
            "evidence": {"type": "object"},
            "next_step": {"type": ["string", "null"], "maxLength": 4000},
            "external_side_effects": {
                "type": "array",
                "maxItems": 200,
                "items": {"type": "string"},
            },
        },
        "required": [
            "status",
            "summary",
            "artifacts",
            "evidence",
            "next_step",
            "external_side_effects",
        ],
    },
}


def _handle_goal_report(args: dict, **_kwargs) -> str:
    try:
        collector = record_active_goal_report(args)
    except GoalReportError as exc:
        return tool_error(str(exc))
    return tool_result(
        success=True,
        job_id=collector.job_id,
        iteration=collector.iteration,
    )


registry.register(
    name="goal_report",
    toolset="goal_internal",
    schema=GOAL_REPORT_SCHEMA,
    handler=_handle_goal_report,
    description="Submit one bounded-goal iteration report.",
    emoji="🎯",
)

