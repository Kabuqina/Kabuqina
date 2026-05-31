"""Structured user interaction tools."""

from __future__ import annotations

import json
from typing import Any, Callable, Dict, List, Optional

from tools.registry import registry, tool_error


def review_outline_tool(
    question: str,
    outline: str,
    choices: Optional[List[str]] = None,
    callback: Optional[Callable[..., Any]] = None,
) -> str:
    question = (question or "请确认大纲").strip()
    outline = str(outline or "").strip()
    if not outline:
        return tool_error("outline is required")
    if callback is None:
        return tool_error("No interactive user callback is available.")

    offered = choices or ["通过", "补充要求", "自行编辑"]
    artifact = {"type": "ppt_outline", "content": outline}
    try:
        response = callback(question, offered, kind="outline_review", artifact=artifact)
    except TypeError:
        response = callback(f"{question}\n\n{outline}", offered)
    return json.dumps(
        {
            "ok": True,
            "question": question,
            "outline": outline,
            "choices_offered": offered,
            "user_response": response,
        },
        ensure_ascii=False,
    )


REVIEW_OUTLINE_SCHEMA: Dict[str, Any] = {
    "name": "review_outline",
    "description": (
        "Show a generated PPT outline to the user for confirmation before creating the deck. "
        "The user can approve, add requirements for regeneration, or edit the outline."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "question": {"type": "string"},
            "outline": {"type": "string"},
            "choices": {"type": "array", "items": {"type": "string"}, "maxItems": 4},
        },
        "required": ["question", "outline"],
    },
}


registry.register(
    name="review_outline",
    toolset="clarify",
    schema=REVIEW_OUTLINE_SCHEMA,
    handler=lambda args, **kw: review_outline_tool(
        question=args.get("question", ""),
        outline=args.get("outline", ""),
        choices=args.get("choices"),
        callback=kw.get("callback"),
    ),
    check_fn=lambda: True,
    emoji="🧾",
)
