"""Minimal M1 ``learning`` toolset for the STUDY learning foundation.

A non-default, opt-in toolset (registered via the ToolRegistry exactly like
``goal_internal`` — never added to core/default tool lists). Runtime identity is
injected through the ``learning_context_scope`` ContextVar, so **no tool schema
carries ``owner_id``**: the owner and current space come only from the active
:class:`LearningExecutionContext`.

M1 surface: list/create/select course space, build the Learning Index, create a
typed draft, and list drafts/active artifacts. Trust-boundary operations
(activate / reject / archive) are deliberately NOT exposed as model tools — they
belong to trusted UI/API or deterministic Gateway commands (M2+).
"""

from __future__ import annotations

from typing import Any, Dict

from tools.registry import registry, tool_error, tool_result
from learning.learning_contract import KINDS, ContractError
from learning.learning_context import require_active_learning_context
from learning.learning_index import LearningIndex
from learning.output_writer import OutputWriter

# Statuses a model may enumerate — never the terminal rejected/archived states.
_MODEL_VISIBLE_STATUSES = ("draft", "active")

_KIND_ENUM = sorted(KINDS)


# --------------------------------------------------------------------------- #
# Schemas — none declare owner_id.
# --------------------------------------------------------------------------- #

SPACE_LIST_SCHEMA = {
    "name": "learning_space_list",
    "description": "List the current owner's course/learning spaces.",
    "parameters": {"type": "object", "additionalProperties": False, "properties": {}},
}

SPACE_CREATE_SCHEMA = {
    "name": "learning_space_create",
    "description": "Create a course/learning space and make it current.",
    "parameters": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "title": {"type": "string", "maxLength": 300},
            "space_id": {"type": "string", "maxLength": 200},
        },
        "required": ["title"],
    },
}

SPACE_SELECT_SCHEMA = {
    "name": "learning_space_select",
    "description": "Select the current course/learning space by id.",
    "parameters": {
        "type": "object",
        "additionalProperties": False,
        "properties": {"space_id": {"type": "string", "maxLength": 200}},
        "required": ["space_id"],
    },
}

INDEX_BUILD_SCHEMA = {
    "name": "learning_index_build",
    "description": (
        "Build the deterministic Learning Index snapshot for the current space "
        "(active artifacts + activities only). Read this before planning."
    ),
    "parameters": {"type": "object", "additionalProperties": False, "properties": {}},
}

DRAFT_CREATE_SCHEMA = {
    "name": "learning_draft_create",
    "description": (
        "Create a typed learning artifact as a draft for later review. AI content "
        "is always saved as draft; it is never auto-activated."
    ),
    "parameters": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "kind": {"type": "string", "enum": _KIND_ENUM},
            "title": {"type": "string", "maxLength": 300},
            "payload": {"type": "object"},
            "source_refs": {"type": "array", "maxItems": 200},
        },
        "required": ["kind", "title", "payload"],
    },
}

ARTIFACT_LIST_SCHEMA = {
    "name": "learning_artifact_list",
    "description": "List draft/active artifacts in the current space.",
    "parameters": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "status": {"type": "string", "enum": list(_MODEL_VISIBLE_STATUSES)},
            "kind": {"type": "string", "enum": _KIND_ENUM},
        },
    },
}

LEARNING_TOOL_SCHEMAS = [
    SPACE_LIST_SCHEMA,
    SPACE_CREATE_SCHEMA,
    SPACE_SELECT_SCHEMA,
    INDEX_BUILD_SCHEMA,
    DRAFT_CREATE_SCHEMA,
    ARTIFACT_LIST_SCHEMA,
]


# --------------------------------------------------------------------------- #
# Handlers — owner/space come only from the active context.
# --------------------------------------------------------------------------- #

def _artifact_ref(a: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "artifact_id": a["artifact_id"],
        "kind": a["kind"],
        "title": a["title"],
        "version": a["version"],
        "status": a["status"],
        "review": a["review"],
    }


def _handle_space_list(args: dict, **_kwargs) -> str:
    try:
        ctx = require_active_learning_context()
    except LookupError as exc:
        return tool_error(str(exc))
    spaces = [
        {
            "space_id": s["space_id"],
            "title": s["title"],
            "status": s["status"],
            "is_current": bool(s["is_current"]),
        }
        for s in ctx.list_spaces()
    ]
    return tool_result(success=True, spaces=spaces)


def _handle_space_create(args: dict, **_kwargs) -> str:
    try:
        ctx = require_active_learning_context()
    except LookupError as exc:
        return tool_error(str(exc))
    try:
        sid = ctx.create_space(
            title=args["title"], space_id=args.get("space_id")
        )
    except (ValueError, KeyError) as exc:
        return tool_error(str(exc))
    return tool_result(success=True, space_id=sid)


def _handle_space_select(args: dict, **_kwargs) -> str:
    try:
        ctx = require_active_learning_context()
    except LookupError as exc:
        return tool_error(str(exc))
    try:
        ctx.select_space(args["space_id"])
    except (ValueError, KeyError) as exc:
        return tool_error(str(exc))
    return tool_result(success=True, space_id=args["space_id"])


def _handle_index_build(args: dict, **_kwargs) -> str:
    try:
        ctx = require_active_learning_context()
    except LookupError as exc:
        return tool_error(str(exc))
    try:
        snapshot = LearningIndex(ctx).build()
    except ValueError as exc:
        return tool_error(str(exc))
    return tool_result(success=True, index=snapshot)


def _handle_draft_create(args: dict, **_kwargs) -> str:
    try:
        ctx = require_active_learning_context()
    except LookupError as exc:
        return tool_error(str(exc))
    writer = OutputWriter(ctx)
    try:
        res = writer.write_artifact(
            kind=args["kind"],
            title=args["title"],
            payload=args["payload"],
            source_refs=args.get("source_refs"),
        )
    except (ContractError, ValueError, KeyError) as exc:
        return tool_error(str(exc))
    return tool_result(
        success=True,
        artifact_id=res["artifact_id"],
        version=res["version"],
        status="draft",
    )


def _handle_artifact_list(args: dict, **_kwargs) -> str:
    try:
        ctx = require_active_learning_context()
    except LookupError as exc:
        return tool_error(str(exc))
    kind = args.get("kind")
    status = args.get("status")
    if status is not None:
        rows = ctx.list_artifacts(kind=kind, status=status)
    else:
        # Model-facing default: drafts + active only (never rejected/archived).
        rows = []
        for st in _MODEL_VISIBLE_STATUSES:
            rows.extend(ctx.list_artifacts(kind=kind, status=st))
    return tool_result(success=True, artifacts=[_artifact_ref(a) for a in rows])


# --------------------------------------------------------------------------- #
# Registration — opt-in toolset "learning" (not a default/core toolset).
# Explicit top-level registry.register(...) calls so tool auto-discovery
# (which only inspects module-body statements) picks the module up.
# --------------------------------------------------------------------------- #

registry.register(
    name="learning_space_list",
    toolset="learning",
    schema=SPACE_LIST_SCHEMA,
    handler=_handle_space_list,
    description=SPACE_LIST_SCHEMA["description"],
    emoji="📚",
)
registry.register(
    name="learning_space_create",
    toolset="learning",
    schema=SPACE_CREATE_SCHEMA,
    handler=_handle_space_create,
    description=SPACE_CREATE_SCHEMA["description"],
    emoji="📚",
)
registry.register(
    name="learning_space_select",
    toolset="learning",
    schema=SPACE_SELECT_SCHEMA,
    handler=_handle_space_select,
    description=SPACE_SELECT_SCHEMA["description"],
    emoji="📚",
)
registry.register(
    name="learning_index_build",
    toolset="learning",
    schema=INDEX_BUILD_SCHEMA,
    handler=_handle_index_build,
    description=INDEX_BUILD_SCHEMA["description"],
    emoji="🗂️",
)
registry.register(
    name="learning_draft_create",
    toolset="learning",
    schema=DRAFT_CREATE_SCHEMA,
    handler=_handle_draft_create,
    description=DRAFT_CREATE_SCHEMA["description"],
    emoji="📝",
)
registry.register(
    name="learning_artifact_list",
    toolset="learning",
    schema=ARTIFACT_LIST_SCHEMA,
    handler=_handle_artifact_list,
    description=ARTIFACT_LIST_SCHEMA["description"],
    emoji="📚",
)
