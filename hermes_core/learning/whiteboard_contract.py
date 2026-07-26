# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Exact dependency-free contracts for S-2 whiteboard state."""

from __future__ import annotations

import copy
import hashlib
import json
import re
from typing import Any, Mapping


WHITEBOARD_SCHEMA_VERSION = 1
MAX_WHITEBOARD_ELEMENTS = 256
MAX_ELEMENT_CONTENT_CODEPOINTS = 2_000
MAX_SCENE_CONTENT_CODEPOINTS = 32_000
MAX_SCENE_BYTES = 240 * 1024
MAX_WHITEBOARD_ENVELOPE_BYTES = 256 * 1024
MAX_WHITEBOARD_SOURCE_REFS = 32
MAX_WHITEBOARD_SNAPSHOTS_PER_ACTIVITY = 8
MAX_WHITEBOARD_ACTIVITY_BYTES = 3 * 1024 * 1024
MAX_WHITEBOARD_SPACE_BYTES = 4 * 1024 * 1024
MAX_WHITEBOARD_OWNER_BYTES = 8 * 1024 * 1024
MAX_WORKING_IDEMPOTENCY_RECORDS = 64

WHITEBOARD_ELEMENT_TYPES = frozenset(
    {"text", "math", "line", "arrow", "rectangle", "ellipse"}
)
WHITEBOARD_TONES = frozenset({"ink", "accent", "muted", "warning"})
WHITEBOARD_STROKE_WIDTHS = frozenset({1, 2, 3, 4})

_OPAQUE_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_EXTERNAL_OR_EXECUTABLE_RE = re.compile(
    r"(?:\b(?:https?|file|data|blob|javascript):|"
    r"<\s*/?\s*(?:svg|iframe|script|style|img|object|embed|link|meta)\b|"
    r"\bon[a-z]+\s*=|\burl\s*\(|@import|"
    r"\\(?:href|url|htmlClass|htmlId|htmlStyle|includegraphics)\b)",
    re.IGNORECASE,
)

_COMMON_FIELDS = frozenset(
    {"element_id", "type", "x", "y", "tone", "stroke_width"}
)
_BOX_FIELDS = frozenset({"width", "height"})
_CONTENT_FIELDS = frozenset({"content"})
_END_FIELDS = frozenset({"end_x", "end_y"})


class WhiteboardContractError(ValueError):
    """Whiteboard input violated an exact bounded contract."""


def canonical_json_bytes(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise WhiteboardContractError("whiteboard value is not canonical JSON") from exc


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def require_opaque_id(value: Any, label: str) -> str:
    if not isinstance(value, str) or not _OPAQUE_ID_RE.fullmatch(value):
        raise WhiteboardContractError(f"{label} must be a bounded opaque id")
    return value


def require_sha256(value: Any, label: str) -> str:
    if not isinstance(value, str) or not _SHA256_RE.fullmatch(value):
        raise WhiteboardContractError(f"{label} must be lowercase SHA-256")
    return value


def _require_exact(value: Any, fields: frozenset[str], label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != fields:
        raise WhiteboardContractError(f"{label} fields are invalid")
    return dict(value)


def _require_integer(value: Any, label: str, minimum: int, maximum: int) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise WhiteboardContractError(
            f"{label} must be an integer in {minimum}..{maximum}"
        )
    return value


def _validate_content(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise WhiteboardContractError(f"{label} must be non-empty text")
    if len(value) > MAX_ELEMENT_CONTENT_CODEPOINTS:
        raise WhiteboardContractError(
            f"{label} exceeds {MAX_ELEMENT_CONTENT_CODEPOINTS} codepoints"
        )
    if any(ord(char) < 32 and char not in "\t\n\r" for char in value):
        raise WhiteboardContractError(f"{label} contains control characters")
    if _EXTERNAL_OR_EXECUTABLE_RE.search(value):
        raise WhiteboardContractError(f"{label} contains external or executable content")
    return value


def validate_whiteboard_element(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise WhiteboardContractError("whiteboard element must be an object")
    element_type = value.get("type")
    if element_type not in WHITEBOARD_ELEMENT_TYPES:
        raise WhiteboardContractError("whiteboard element type is invalid")
    if element_type in {"text", "math"}:
        fields = _COMMON_FIELDS | _BOX_FIELDS | _CONTENT_FIELDS
    elif element_type in {"rectangle", "ellipse"}:
        fields = _COMMON_FIELDS | _BOX_FIELDS
    else:
        fields = _COMMON_FIELDS | _END_FIELDS
    element = _require_exact(value, fields, "whiteboard element")
    require_opaque_id(element["element_id"], "element_id")
    _require_integer(element["x"], "x", -10_000, 10_000)
    _require_integer(element["y"], "y", -10_000, 10_000)
    if element["tone"] not in WHITEBOARD_TONES:
        raise WhiteboardContractError("whiteboard tone is invalid")
    if element["stroke_width"] not in WHITEBOARD_STROKE_WIDTHS:
        raise WhiteboardContractError("whiteboard stroke_width is invalid")
    if element_type in {"text", "math", "rectangle", "ellipse"}:
        _require_integer(element["width"], "width", 1, 20_000)
        _require_integer(element["height"], "height", 1, 20_000)
    if element_type in {"text", "math"}:
        _validate_content(element["content"], "whiteboard content")
    if element_type in {"line", "arrow"}:
        _require_integer(element["end_x"], "end_x", -10_000, 10_000)
        _require_integer(element["end_y"], "end_y", -10_000, 10_000)
    return copy.deepcopy(element)


def validate_whiteboard_scene(value: Any) -> dict[str, Any]:
    scene = _require_exact(
        value, frozenset({"schema_version", "elements"}), "whiteboard scene"
    )
    if scene["schema_version"] != WHITEBOARD_SCHEMA_VERSION:
        raise WhiteboardContractError("whiteboard scene version is invalid")
    elements = scene["elements"]
    if not isinstance(elements, list) or len(elements) > MAX_WHITEBOARD_ELEMENTS:
        raise WhiteboardContractError(
            f"whiteboard scene exceeds {MAX_WHITEBOARD_ELEMENTS} elements"
        )
    normalized: list[dict[str, Any]] = []
    element_ids: set[str] = set()
    total_content = 0
    for raw in elements:
        element = validate_whiteboard_element(raw)
        element_id = element["element_id"]
        if element_id in element_ids:
            raise WhiteboardContractError("whiteboard element ids must be unique")
        element_ids.add(element_id)
        total_content += len(element.get("content", ""))
        if total_content > MAX_SCENE_CONTENT_CODEPOINTS:
            raise WhiteboardContractError(
                f"whiteboard content exceeds {MAX_SCENE_CONTENT_CODEPOINTS} codepoints"
            )
        normalized.append(element)
    result = {"schema_version": WHITEBOARD_SCHEMA_VERSION, "elements": normalized}
    if len(canonical_json_bytes(result)) > MAX_SCENE_BYTES:
        raise WhiteboardContractError(
            f"whiteboard scene exceeds {MAX_SCENE_BYTES} canonical bytes"
        )
    return result


def validate_whiteboard_snapshot_payload(value: Any) -> dict[str, Any]:
    payload = _require_exact(
        value,
        frozenset(
            {
                "schema_version",
                "activity_id",
                "lineage_id",
                "revision",
                "parent_artifact_id",
                "scene",
                "scene_sha256",
            }
        ),
        "whiteboard snapshot",
    )
    if payload["schema_version"] != WHITEBOARD_SCHEMA_VERSION:
        raise WhiteboardContractError("whiteboard snapshot version is invalid")
    require_opaque_id(payload["activity_id"], "activity_id")
    require_opaque_id(payload["lineage_id"], "lineage_id")
    _require_integer(payload["revision"], "revision", 1, 2_147_483_647)
    parent = payload["parent_artifact_id"]
    if parent is not None:
        require_opaque_id(parent, "parent_artifact_id")
    scene = validate_whiteboard_scene(payload["scene"])
    scene_sha256 = require_sha256(payload["scene_sha256"], "scene_sha256")
    if scene_sha256 != canonical_sha256(scene):
        raise WhiteboardContractError("whiteboard scene hash does not match scene")
    return {
        "schema_version": WHITEBOARD_SCHEMA_VERSION,
        "activity_id": payload["activity_id"],
        "lineage_id": payload["lineage_id"],
        "revision": payload["revision"],
        "parent_artifact_id": parent,
        "scene": scene,
        "scene_sha256": scene_sha256,
    }


def validate_whiteboard_working_state(value: Any) -> dict[str, Any]:
    state = _require_exact(
        value,
        frozenset(
            {
                "schema_version",
                "activity_id",
                "lineage_id",
                "revision",
                "scene",
                "scene_sha256",
                "request_ledger",
            }
        ),
        "whiteboard working state",
    )
    if state["schema_version"] != WHITEBOARD_SCHEMA_VERSION:
        raise WhiteboardContractError("whiteboard working state version is invalid")
    require_opaque_id(state["activity_id"], "activity_id")
    require_opaque_id(state["lineage_id"], "lineage_id")
    revision = _require_integer(
        state["revision"], "revision", 1, 2_147_483_647
    )
    scene = validate_whiteboard_scene(state["scene"])
    scene_sha256 = require_sha256(state["scene_sha256"], "scene_sha256")
    if scene_sha256 != canonical_sha256(scene):
        raise WhiteboardContractError("whiteboard working scene hash does not match")
    raw_ledger = state["request_ledger"]
    if (
        not isinstance(raw_ledger, list)
        or not raw_ledger
        or len(raw_ledger) > MAX_WORKING_IDEMPOTENCY_RECORDS
    ):
        raise WhiteboardContractError("whiteboard request ledger is invalid")
    ledger: list[dict[str, Any]] = []
    identities: set[tuple[str, str]] = set()
    last_result_revision = 0
    fields = frozenset(
        {
            "operation",
            "idempotency_key",
            "request_sha256",
            "source_artifact_id",
            "result_revision",
            "result_scene_sha256",
        }
    )
    for raw in raw_ledger:
        record = _require_exact(raw, fields, "whiteboard request record")
        if record["operation"] not in {"save", "restore"}:
            raise WhiteboardContractError("whiteboard request operation is invalid")
        key = require_opaque_id(record["idempotency_key"], "idempotency_key")
        identity = (record["operation"], key)
        if identity in identities:
            raise WhiteboardContractError("whiteboard request identity is duplicated")
        identities.add(identity)
        require_sha256(record["request_sha256"], "request_sha256")
        source_artifact_id = record["source_artifact_id"]
        if record["operation"] == "save":
            if source_artifact_id is not None:
                raise WhiteboardContractError(
                    "whiteboard save record must not have a source artifact"
                )
        else:
            source_artifact_id = require_opaque_id(
                source_artifact_id, "source_artifact_id"
            )
        result_revision = _require_integer(
            record["result_revision"], "result_revision", 1, revision
        )
        if result_revision <= last_result_revision:
            raise WhiteboardContractError(
                "whiteboard request revisions must be strictly increasing"
            )
        last_result_revision = result_revision
        require_sha256(record["result_scene_sha256"], "result_scene_sha256")
        ledger.append(
            {
                "operation": record["operation"],
                "idempotency_key": key,
                "request_sha256": record["request_sha256"],
                "source_artifact_id": source_artifact_id,
                "result_revision": result_revision,
                "result_scene_sha256": record["result_scene_sha256"],
            }
        )
    return {
        "schema_version": WHITEBOARD_SCHEMA_VERSION,
        "activity_id": state["activity_id"],
        "lineage_id": state["lineage_id"],
        "revision": revision,
        "scene": scene,
        "scene_sha256": scene_sha256,
        "request_ledger": ledger,
    }


def whiteboard_working_item_id(owner_id: str, space_id: str, activity_id: str) -> str:
    require_opaque_id(owner_id, "owner_id")
    require_opaque_id(space_id, "space_id")
    require_opaque_id(activity_id, "activity_id")
    digest = hashlib.sha256(
        canonical_json_bytes([space_id, activity_id])
    ).hexdigest()
    return f"wbw_{digest[:48]}"


__all__ = [
    "MAX_SCENE_BYTES",
    "MAX_WHITEBOARD_ACTIVITY_BYTES",
    "MAX_WHITEBOARD_ENVELOPE_BYTES",
    "MAX_WHITEBOARD_OWNER_BYTES",
    "MAX_WHITEBOARD_SNAPSHOTS_PER_ACTIVITY",
    "MAX_WHITEBOARD_SOURCE_REFS",
    "MAX_WHITEBOARD_SPACE_BYTES",
    "MAX_WORKING_IDEMPOTENCY_RECORDS",
    "WHITEBOARD_SCHEMA_VERSION",
    "WhiteboardContractError",
    "canonical_json_bytes",
    "canonical_sha256",
    "require_opaque_id",
    "require_sha256",
    "validate_whiteboard_element",
    "validate_whiteboard_scene",
    "validate_whiteboard_snapshot_payload",
    "validate_whiteboard_working_state",
    "whiteboard_working_item_id",
]
