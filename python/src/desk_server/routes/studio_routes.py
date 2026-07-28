# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Trusted desktop routes for Studio projects and explicit Study gathering."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Mapping
from urllib.parse import quote

from fastapi import APIRouter, HTTPException

from learning.learning_store import LearningStore
from learning_owner import desktop_learning_scope
from studio_store import StudioStore


router = APIRouter()

_KIND_PAGE = {
    "student_state": "flyleaf",
    "knowledge_base": "learn",
    "resource_pack": "learn",
    "tutoring_note": "learn",
    "flashcard_deck": "practice",
    "quiz": "practice",
    "evaluation": "evaluate",
    "learning_plan": "plan",
    "material_alignment": "learn",
}


def _error(exc: Exception) -> HTTPException:
    if isinstance(exc, KeyError):
        status, code = 404, "studio_not_found"
    elif isinstance(exc, (ValueError, TypeError)):
        status, code = 400, "studio_invalid_request"
    else:
        status, code = 500, "studio_internal_error"
    return HTTPException(status_code=status, detail={"code": code, "message": str(exc)})


def _body_text(
    body: Mapping[str, Any], key: str, *, maximum: int, allow_empty: bool = False
) -> str:
    value = body.get(key)
    if not isinstance(value, str):
        raise ValueError(f"{key} must be text")
    value = value.strip()
    if not allow_empty and not value:
        raise ValueError(f"{key} is required")
    if len(value) > maximum:
        raise ValueError(f"{key} is too long")
    return value


def _artifact_excerpt(artifact: Mapping[str, Any]) -> str:
    envelope = artifact.get("envelope")
    payload = envelope.get("payload") if isinstance(envelope, Mapping) else envelope
    if isinstance(payload, str):
        rendered = payload.strip()
    else:
        rendered = json.dumps(
            payload if payload is not None else {},
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )
    if len(rendered) <= 20_000:
        return rendered
    return rendered[:19_999].rstrip() + "…"


def _source_snapshot(
    *, artifact: Mapping[str, Any], space_id: str, space_title: str
) -> dict[str, Any]:
    kind = str(artifact.get("kind") or "study_artifact")
    base = f"/study/{quote(space_id, safe='')}"
    page = _KIND_PAGE.get(kind)
    return {
        "id": uuid.uuid4().hex,
        "kind": "study_artifact",
        "title": str(artifact.get("title") or "Study artifact"),
        "origin": f"{space_title} · {kind}",
        "excerpt": _artifact_excerpt(artifact),
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "revision": int(artifact.get("version") or 1),
        "returnTarget": f"{base}/{page}" if page else base,
        "fallbackTarget": base,
    }


def _resolve_study_sources(refs: list[Any]) -> list[dict[str, Any]]:
    if not refs:
        raise ValueError("at least one source is required")
    if len(refs) > 100:
        raise ValueError("too many sources")

    snapshots: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    store = LearningStore()
    try:
        for raw in refs:
            if not isinstance(raw, Mapping) or raw.get("kind") != "study_artifact":
                raise ValueError("only study_artifact sources are supported")
            space_id = _body_text(raw, "spaceId", maximum=200)
            artifact_id = _body_text(raw, "artifactId", maximum=200)
            identity = (space_id, artifact_id)
            if identity in seen:
                raise ValueError("duplicate Study source")
            seen.add(identity)

            with desktop_learning_scope(store, space_id=space_id) as ctx:
                space = next(
                    (item for item in ctx.list_spaces() if item.get("space_id") == space_id),
                    None,
                )
                if not space:
                    raise KeyError(f"learning space {space_id!r} not found")
                artifact = ctx.get_artifact(artifact_id)
                if not artifact:
                    raise KeyError(f"artifact {artifact_id!r} not found")
                if artifact.get("status") != "active":
                    raise ValueError("only active Study artifacts can be gathered")
                snapshots.append(
                    _source_snapshot(
                        artifact=artifact,
                        space_id=space_id,
                        space_title=str(space.get("title") or space_id),
                    )
                )
    finally:
        store.close()
    return snapshots


@router.get("/api/desk/studio/projects")
async def studio_projects():
    try:
        with StudioStore() as store:
            return {"projects": store.list_projects()}
    except Exception as exc:
        raise _error(exc) from exc


@router.post("/api/desk/studio/projects")
async def studio_create_project(body: dict[str, Any]):
    try:
        title = _body_text(body, "title", maximum=200)
        with StudioStore() as store:
            return store.create_project(title)
    except Exception as exc:
        raise _error(exc) from exc


@router.post("/api/desk/studio/projects/{project_id}/brief")
async def studio_save_brief(project_id: str, body: dict[str, Any]):
    try:
        brief = _body_text(body, "brief", maximum=20_000, allow_empty=True)
        with StudioStore() as store:
            return store.save_brief(project_id, brief)
    except Exception as exc:
        raise _error(exc) from exc


@router.delete("/api/desk/studio/projects/{project_id}")
async def studio_delete_project(project_id: str):
    """Delete Studio-owned state and tell Web which chat scope to detach.

    A project-scoped transcript is still a user's chat history.  Project deletion
    must not silently erase it; Web converts it back to an ordinary chat session by
    clearing the returned deterministic handoff id.
    """
    try:
        with StudioStore() as store:
            store.delete_project(project_id)
        return {
            "ok": True,
            "projectId": project_id,
            "detachedSessionId": f"studio:{project_id}",
            "chatHistoryDeleted": False,
        }
    except Exception as exc:
        raise _error(exc) from exc


@router.post("/api/desk/studio/projects/{project_id}/sources")
async def studio_gather_sources(project_id: str, body: dict[str, Any]):
    try:
        refs = body.get("refs")
        if not isinstance(refs, list):
            raise ValueError("refs must be a list")
        with StudioStore() as studio:
            if studio.get_project(project_id) is None:
                raise KeyError(f"studio project {project_id!r} not found")
            snapshots = _resolve_study_sources(refs)
            return studio.add_sources_atomic(project_id, snapshots)
    except Exception as exc:
        raise _error(exc) from exc
