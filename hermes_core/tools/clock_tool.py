#!/usr/bin/env python3
"""
Clock tool — timezone-aware current time without terminal access.

Uses ``kabuqina_time.now()`` (HERMES_TIMEZONE env → config.yaml → server local).
"""

from __future__ import annotations

import json
from typing import Any, Dict

from kabuqina_time import get_timezone, now as kabuqina_now


def get_current_time_tool() -> str:
    """Return the configured wall-clock time as JSON."""
    dt = kabuqina_now()
    tz = get_timezone()
    tz_name = str(tz) if tz is not None else "local"
    formatted = dt.strftime("%A, %B %d, %Y %I:%M %p")
    payload: Dict[str, Any] = {
        "timezone": tz_name,
        "iso8601": dt.isoformat(),
        "formatted": formatted,
        "weekday": dt.strftime("%A"),
        "date": dt.strftime("%Y-%m-%d"),
        "time_24h": dt.strftime("%H:%M:%S"),
        "unix": int(dt.timestamp()),
    }
    return json.dumps(payload, ensure_ascii=False)


def check_clock_requirements() -> bool:
    """Always available — no API keys or gateway dependency."""
    return True


GET_CURRENT_TIME_SCHEMA = {
    "name": "get_current_time",
    "description": (
        "Return the current date and time in the user's configured timezone. "
        "Use this whenever you need the live clock — never guess time from "
        "memory or from the 'Conversation started' line in the system prompt "
        "(that timestamp is fixed at session start). "
        "Prefer this over the terminal `date` command when terminal is unavailable."
    ),
    "parameters": {
        "type": "object",
        "properties": {},
        "required": [],
    },
}


from tools.registry import registry

registry.register(
    name="get_current_time",
    toolset="clock",
    schema=GET_CURRENT_TIME_SCHEMA,
    handler=lambda args, **kw: get_current_time_tool(),
    check_fn=check_clock_requirements,
    emoji="🕐",
)
