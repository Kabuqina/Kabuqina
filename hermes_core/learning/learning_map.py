"""Versioned Course learning-map and shared-location projection.

The map is derived from already-owned Study truth: a confirmed primary material
outline, captured knowledge cores, and active quiz questions with explicit core
links.  It never invents a relationship and never copies textbook body text.
Only two small reserved ``learning_items`` are persisted: the projection hash /
revision and the learner's shared location.  They therefore travel through the
existing Study backup and restore pipeline without a second database.
"""

from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Mapping

from learning.flashcards import FlashcardService
from learning.learning_context import LearningExecutionContext
from learning.learning_store import LearningConflictError
from learning.quizzes import QuizService


MAP_META_ITEM_ID = "__course_learning_map_v1__"
MAP_META_ITEM_TYPE = "course_learning_map_meta"
LOCATION_ITEM_ID = "__course_location_v1__"
LOCATION_ITEM_TYPE = "course_location"
LOCATION_PAGES = frozenset({"plan", "learn", "practice"})
LEARNING_PLAN_ITEM_TYPE = "learning_plan_item"
MAX_OUTLINE_NODES = 600
MAX_KNOWLEDGE_CORES = 500
MAX_EXERCISE_LINKS = 2_000


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _text(value: Any, maximum: int = 2_000) -> str:
    return value.strip()[:maximum] if isinstance(value, str) else ""


def _payload(artifact: Mapping[str, Any]) -> Mapping[str, Any]:
    envelope = artifact.get("envelope")
    payload = envelope.get("payload") if isinstance(envelope, Mapping) else None
    return payload if isinstance(payload, Mapping) else {}


def _source_refs(artifact: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    envelope = artifact.get("envelope")
    refs = envelope.get("source_refs") if isinstance(envelope, Mapping) else None
    return [item for item in refs or [] if isinstance(item, Mapping)]


def _stable_node_id(
    raw: Any, *, artifact_id: str, path: tuple[int, ...], title: str, used: set[str]
) -> str:
    candidate = _text(raw, 200)
    if candidate and candidate not in used:
        used.add(candidate)
        return candidate
    seed = f"{artifact_id}|{'.'.join(map(str, path))}|{title}"
    candidate = f"outline-{hashlib.sha256(seed.encode('utf-8')).hexdigest()[:20]}"
    suffix = 1
    unique = candidate
    while unique in used:
        suffix += 1
        unique = f"{candidate}-{suffix}"
    used.add(unique)
    return unique


def _node_locator(node: Mapping[str, Any]) -> str:
    locator = _text(node.get("locator"), 500)
    if locator:
        return locator
    page = node.get("page")
    if type(page) is int and page >= 0:
        return f"page:{page}"
    evidence = node.get("evidence")
    if isinstance(evidence, Mapping):
        return _text(evidence.get("locator"), 500)
    return ""


def _flatten_outline(
    raw: Any,
    *,
    artifact_id: str,
    origin: str,
    source_ref: Mapping[str, Any],
    require_locator: bool,
    require_evidence: bool = False,
) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    result: list[dict[str, Any]] = []
    used: set[str] = set()
    has_nested = any(
        isinstance(node, Mapping) and isinstance(node.get("children"), list) and node["children"]
        for node in raw
    )

    def append_node(
        node: Mapping[str, Any], *, depth: int, parent_id: str | None, path: tuple[int, ...]
    ) -> str | None:
        if len(result) >= MAX_OUTLINE_NODES or depth > 3:
            return None
        title = _text(node.get("title"), 500)
        locator = _node_locator(node)
        evidence = node.get("evidence")
        has_evidence = (
            isinstance(evidence, Mapping)
            and bool(_text(evidence.get("source_ref"), 500))
            and bool(_text(evidence.get("locator"), 500))
        )
        if (
            not title
            or (require_locator and not locator)
            or (require_evidence and not has_evidence)
        ):
            return None
        node_id = _stable_node_id(
            node.get("id") or node.get("section_id"),
            artifact_id=artifact_id,
            path=path,
            title=title,
            used=used,
        )
        result.append(
            {
                "id": node_id,
                "parentId": parent_id,
                "title": title,
                "order": len(result),
                "depth": depth,
                "origin": origin,
                "sourceRef": copy.deepcopy(dict(source_ref)),
                "locator": locator,
            }
        )
        return node_id

    if has_nested:
        def visit(nodes: list[Any], depth: int, parent_id: str | None, prefix: tuple[int, ...]) -> None:
            if depth > 3:
                return
            for index, raw_node in enumerate(nodes):
                if not isinstance(raw_node, Mapping):
                    continue
                path = (*prefix, index)
                node_id = append_node(raw_node, depth=depth, parent_id=parent_id, path=path)
                children = raw_node.get("children")
                if node_id and isinstance(children, list):
                    visit(children, depth + 1, node_id, path)

        visit(raw, 1, None, ())
        return result

    stack: dict[int, str] = {}
    previous_depth = 1
    for index, raw_node in enumerate(raw):
        if not isinstance(raw_node, Mapping):
            continue
        declared = raw_node.get("depth", raw_node.get("level", 1))
        depth = declared if type(declared) is int else 1
        depth = min(3, max(1, depth, min(previous_depth + 1, 3))) if depth > previous_depth + 1 else min(3, max(1, depth))
        parent_id = stack.get(depth - 1) if depth > 1 else None
        if depth > 1 and parent_id is None:
            depth, parent_id = 1, None
        node_id = append_node(raw_node, depth=depth, parent_id=parent_id, path=(index,))
        if node_id:
            stack[depth] = node_id
            for old_depth in tuple(stack):
                if old_depth > depth:
                    stack.pop(old_depth, None)
            previous_depth = depth
    return result


class LearningMapService:
    """Build one deterministic Course map and own its shared location CAS."""

    def __init__(self, context: LearningExecutionContext) -> None:
        if not context.current_space():
            raise ValueError("learning map requires a selected course")
        self._ctx = context

    def _space_title(self) -> str:
        space_id = self._ctx.current_space()
        row = next(
            (item for item in self._ctx.list_spaces() if item.get("space_id") == space_id),
            None,
        )
        if row is None or row.get("kind", "course") != "course":
            raise ValueError("learning map requires a course space")
        return _text(row.get("title"), 500)

    def _alignment_outline(self) -> tuple[list[dict[str, Any]], str] | None:
        title = self._space_title().casefold()
        artifacts = sorted(
            self._ctx.list_artifacts(kind="material_alignment", status="active"),
            key=lambda item: (str(item.get("updated_at") or ""), str(item.get("artifact_id") or "")),
            reverse=True,
        )
        for artifact in artifacts:
            payload = _payload(artifact)
            materials = {
                _text(item.get("material_id"), 200): item
                for item in payload.get("materials") or []
                if isinstance(item, Mapping)
            }
            groups = [item for item in payload.get("course_groups") or [] if isinstance(item, Mapping)]
            matched = [item for item in groups if _text(item.get("proposed_title"), 500).casefold() == title]
            if len(groups) == 1:
                matched = groups
            if len(matched) != 1:
                continue
            skeleton = matched[0].get("skeleton")
            material_id = _text(skeleton.get("material_id"), 200) if isinstance(skeleton, Mapping) else ""
            material = materials.get(material_id)
            if not material:
                continue
            source_ref = {
                "artifactId": _text(artifact.get("artifact_id"), 200),
                "materialId": material_id,
                "sourceLabel": _text(material.get("title"), 500),
            }
            outline = _flatten_outline(
                material.get("structure"),
                artifact_id=source_ref["artifactId"],
                origin="extracted",
                source_ref=source_ref,
                require_locator=True,
            )
            if outline:
                return outline, "ready"
        return None

    def _resource_outline(self) -> tuple[list[dict[str, Any]], str]:
        artifacts = sorted(
            self._ctx.list_artifacts(kind="resource_pack", status="active"),
            key=lambda item: (str(item.get("updated_at") or ""), str(item.get("artifact_id") or "")),
            reverse=True,
        )
        observed_status = "missing"
        for artifact in artifacts:
            refs = _source_refs(artifact)
            ref = next(
                (
                    item for item in refs
                    if item.get("origin") == "imported" or item.get("structure_origin") == "inferred_confirmed"
                ),
                None,
            )
            if ref is None:
                continue
            structure_status = _text(ref.get("structure_status"), 40).casefold()
            structure_origin = _text(ref.get("structure_origin"), 80).casefold()
            inferred = structure_origin == "inferred_confirmed"
            if inferred and structure_status != "confirmed":
                observed_status = "weak"
                continue
            if not inferred and structure_status != "reliable":
                if structure_status == "weak":
                    observed_status = "weak"
                continue
            public_ref = {
                "artifactId": _text(artifact.get("artifact_id"), 200),
                "sourceLabel": _text(ref.get("source_label") or artifact.get("title"), 500),
            }
            outline = _flatten_outline(
                _payload(artifact).get("outline"),
                artifact_id=public_ref["artifactId"],
                origin="inferred_confirmed" if inferred else "extracted",
                source_ref=public_ref,
                require_locator=True,
                require_evidence=inferred,
            )
            if outline:
                return outline, "ready"
            observed_status = "weak"
        return [], observed_status

    def _outline(self) -> tuple[list[dict[str, Any]], str]:
        aligned = self._alignment_outline()
        return aligned if aligned is not None else self._resource_outline()

    def _knowledge_cores(
        self, outline_ids: set[str]
    ) -> list[dict[str, Any]]:
        cores: list[dict[str, Any]] = []
        seen: set[str] = set()
        for card in FlashcardService(self._ctx).list_cards():
            artifact = self._ctx.get_artifact(_text(card.get("artifact_id"), 200))
            if not artifact or artifact.get("status") != "active":
                continue
            card_refs = [
                item
                for item in (card.get("source_refs") or [])
                if isinstance(item, Mapping)
            ]
            source = next(
                (
                    item
                    for item in [*card_refs, *_source_refs(artifact)]
                    if item.get("origin") == "kq-kp"
                ),
                None,
            )
            if source is None:
                continue
            core_id = (
                _text(card.get("knowledge_core_id"), 200)
                or _text(source.get("knowledge_core_id"), 200)
                or _text(card.get("item_id"), 200)
            )
            if not core_id or core_id in seen:
                continue
            seen.add(core_id)
            outline_node_id = _text(
                card.get("outline_node_id")
                or source.get("outline_node_id")
                or source.get("outlineNodeId"),
                200,
            )
            declared_order = card.get("order", source.get("order"))
            cores.append(
                {
                    "id": core_id,
                    "itemId": _text(card.get("item_id"), 200),
                    "artifactId": _text(card.get("artifact_id"), 200),
                    "front": _text(card.get("front"), 600),
                    "gist": _text(card.get("back"), 1_200),
                    "captured": True,
                    "outlineNodeId": outline_node_id if outline_node_id in outline_ids else None,
                    "order": declared_order if type(declared_order) is int else len(cores),
                    "sourceRefs": copy.deepcopy(card_refs or [source]),
                }
            )
            if len(cores) >= MAX_KNOWLEDGE_CORES:
                break
        cores.sort(key=lambda item: (item["order"], item["id"]))
        for order, core in enumerate(cores):
            core["order"] = order
        return cores

    def _exercise_links(self, core_ids: set[str]) -> list[dict[str, Any]]:
        links: list[dict[str, Any]] = []
        origin_order = {"source": 0, "adapted": 1, "generated": 2}
        quizzes = QuizService(self._ctx)
        for artifact in quizzes.list_quizzes(status="active"):
            artifact_id = _text(artifact.get("artifact_id"), 200)
            for question in quizzes.list_questions(artifact_id=artifact_id):
                core_id = _text(question.get("knowledge_core_id"), 200)
                if not core_id or core_id not in core_ids:
                    continue
                origin = _text(question.get("origin"), 40).casefold() or "generated"
                links.append(
                    {
                        "knowledgeCoreId": core_id,
                        "quizArtifactId": artifact_id,
                        "exerciseId": _text(question.get("item_id"), 200),
                        "origin": origin,
                        "sourceRefs": copy.deepcopy(question.get("source_refs") or []),
                        "_originOrder": origin_order.get(origin, 3),
                    }
                )
                if len(links) >= MAX_EXERCISE_LINKS:
                    break
            if len(links) >= MAX_EXERCISE_LINKS:
                break
        links.sort(
            key=lambda item: (
                item["knowledgeCoreId"],
                item["_originOrder"],
                item["quizArtifactId"],
                item["exerciseId"],
            )
        )
        per_core: dict[str, int] = {}
        for item in links:
            item.pop("_originOrder", None)
            item["order"] = per_core.get(item["knowledgeCoreId"], 0)
            per_core[item["knowledgeCoreId"]] = item["order"] + 1
        return links

    def _reserved_state(self, item_type: str) -> dict[str, Any] | None:
        rows = self._ctx.list_items(item_type=item_type)
        return copy.deepcopy(rows[0]["state"]) if rows else None

    def _put_reserved(
        self, *, item_id: str, item_type: str, expected_revision: int, state: dict[str, Any]
    ) -> dict[str, Any]:
        return self._ctx.compare_and_put_item_state_revision(
            item_id=item_id,
            item_type=item_type,
            expected_revision=expected_revision,
            state=state,
        )

    def get_map(self) -> dict[str, Any]:
        outline, outline_status = self._outline()
        cores = self._knowledge_cores({item["id"] for item in outline})
        links = self._exercise_links({item["id"] for item in cores})
        content = {
            "outlineStatus": outline_status,
            "outlineNodes": outline,
            "knowledgeCores": cores,
            "exerciseLinks": links,
        }
        digest = hashlib.sha256(
            json.dumps(content, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        for _attempt in range(3):
            current = self._reserved_state(MAP_META_ITEM_TYPE)
            if current and current.get("contentHash") == digest:
                revision = int(current.get("revision") or 1)
                break
            expected = int(current.get("revision") or 0) if current else 0
            try:
                stored = self._put_reserved(
                    item_id=MAP_META_ITEM_ID,
                    item_type=MAP_META_ITEM_TYPE,
                    expected_revision=expected,
                    state={"revision": expected + 1, "contentHash": digest, "updatedAt": _now()},
                )
                revision = stored["revision"]
                break
            except LearningConflictError:
                continue
        else:
            raise LearningConflictError("learning_map_revision_race")
        result = {"revision": revision, **content}
        self._reconcile_location(result)
        return result

    def _plan_item(self, plan_item_id: str) -> tuple[dict[str, Any], dict[str, Any]] | None:
        rows = [
            row
            for row in self._ctx.list_items(item_type=LEARNING_PLAN_ITEM_TYPE)
            if row["item_id"] == plan_item_id
        ]
        if not rows:
            return None
        row = rows[0]
        artifact = self._ctx.get_artifact(str(row.get("artifact_id") or ""))
        return (row, artifact) if artifact else None

    def _location_invalid_reason(
        self,
        location: Mapping[str, Any],
        learning_map: Mapping[str, Any],
    ) -> str:
        core_ids = {item["id"] for item in learning_map["knowledgeCores"]}
        links = {
            (item["knowledgeCoreId"], item["exerciseId"])
            for item in learning_map["exerciseLinks"]
        }
        current_core = _text(location.get("knowledgeCoreId"), 200)
        if current_core and current_core not in core_ids:
            return "knowledge_core_removed"
        exercises = location.get("exerciseByCore")
        if isinstance(exercises, Mapping):
            for core_id, exercise_id in exercises.items():
                if (str(core_id), str(exercise_id)) not in links:
                    return "exercise_removed"
        plan_item_id = _text(location.get("planItemId"), 200)
        if plan_item_id:
            found = self._plan_item(plan_item_id)
            if not found:
                return "plan_item_removed"
            row, artifact = found
            state = dict(row.get("state") or {})
            if artifact.get("status") != "active" or state.get("status") != "open":
                return "plan_item_closed"
        return ""

    def _reconcile_location(self, learning_map: Mapping[str, Any]) -> None:
        current = self._reserved_state(LOCATION_ITEM_TYPE)
        if not current:
            return
        reason = self._location_invalid_reason(current, learning_map)
        same_map = current.get("mapRevision") == learning_map["revision"]
        same_stale = bool(current.get("stale")) == bool(reason)
        same_reason = (current.get("staleReason") or "") == reason
        if same_map and same_stale and same_reason:
            return
        expected = int(current.get("revision") or 0)
        next_state = {
            **current,
            "revision": expected + 1,
            "mapRevision": learning_map["revision"],
            "stale": bool(reason),
            "updatedAt": _now(),
        }
        if reason:
            next_state["staleReason"] = reason
        else:
            next_state.pop("staleReason", None)
        try:
            self._put_reserved(
                item_id=LOCATION_ITEM_ID,
                item_type=LOCATION_ITEM_TYPE,
                expected_revision=expected,
                state=next_state,
            )
        except LearningConflictError:
            # A concurrent location write wins. Its next GET will reconcile it
            # against the same map revision.
            return

    def get_location(self) -> dict[str, Any] | None:
        self.get_map()
        return self._reserved_state(LOCATION_ITEM_TYPE)

    def put_location(
        self,
        *,
        expected_revision: int,
        page: str,
        knowledge_core_id: str | None = None,
        exercise_id: str | None = None,
        plan_item_id: str | None = None,
        expected_map_revision: int | None = None,
    ) -> dict[str, Any]:
        if page not in LOCATION_PAGES:
            raise ValueError("page must be plan, learn, or practice")
        learning_map = self.get_map()
        if expected_map_revision is not None and expected_map_revision != learning_map["revision"]:
            raise LearningConflictError("stale_learning_map")
        cores = {item["id"]: item for item in learning_map["knowledgeCores"]}
        core_id = _text(knowledge_core_id, 200)
        if page != "plan" and not core_id:
            raise ValueError("learn and practice locations require knowledgeCoreId")
        if core_id and core_id not in cores:
            raise LearningConflictError("knowledge_core_unavailable")
        selected_exercise = _text(exercise_id, 200)
        link_pairs = {
            (item["knowledgeCoreId"], item["exerciseId"])
            for item in learning_map["exerciseLinks"]
        }
        if selected_exercise and (core_id, selected_exercise) not in link_pairs:
            raise LearningConflictError("exercise_not_linked_to_knowledge_core")
        selected_plan_item = _text(plan_item_id, 200)
        plan_outline = ""
        if selected_plan_item:
            found = self._plan_item(selected_plan_item)
            if not found:
                raise LearningConflictError("plan_item_unavailable")
            plan_row, plan_artifact = found
            plan_state = dict(plan_row.get("state") or {})
            if (
                plan_artifact.get("status") != "active"
                or plan_state.get("status") != "open"
            ):
                raise LearningConflictError("plan_item_unavailable")
            plan_outline = _text(plan_state.get("outlineNodeId"), 200)
            core_outline = _text(cores.get(core_id, {}).get("outlineNodeId"), 200)
            if plan_outline and core_outline and plan_outline != core_outline:
                outline_by_id = {
                    str(node.get("id") or ""): node
                    for node in learning_map["outlineNodes"]
                }
                cursor = outline_by_id.get(core_outline)
                within_scope = False
                while cursor:
                    parent_id = _text(cursor.get("parentId"), 200)
                    if parent_id == plan_outline:
                        within_scope = True
                        break
                    cursor = outline_by_id.get(parent_id)
                if not within_scope:
                    raise LearningConflictError("plan_item_knowledge_core_mismatch")

        current = self._reserved_state(LOCATION_ITEM_TYPE)
        current_revision = int(current.get("revision") or 0) if current else 0
        if current_revision != expected_revision:
            raise LearningConflictError("stale_revision")
        exercise_by_core = dict(current.get("exerciseByCore") or {}) if current else {}
        if selected_exercise:
            exercise_by_core[core_id] = selected_exercise
        remembered = exercise_by_core.get(core_id) if core_id else None
        core = cores.get(core_id)
        state: dict[str, Any] = {
            "revision": expected_revision + 1,
            "mapRevision": learning_map["revision"],
            "page": page,
            "knowledgeCoreId": core_id or None,
            "outlineNodeId": core.get("outlineNodeId") if core else None,
            "planItemId": selected_plan_item or None,
            "planOutlineNodeId": plan_outline or None,
            "exerciseId": selected_exercise or remembered,
            "exerciseByCore": exercise_by_core,
            "stale": False,
            "updatedAt": _now(),
        }
        return self._put_reserved(
            item_id=LOCATION_ITEM_ID,
            item_type=LOCATION_ITEM_TYPE,
            expected_revision=expected_revision,
            state=state,
        )


__all__ = [
    "LearningMapService",
    "LOCATION_ITEM_ID",
    "LOCATION_ITEM_TYPE",
    "MAP_META_ITEM_ID",
    "MAP_META_ITEM_TYPE",
]
