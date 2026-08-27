# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Strict v1 contracts for photographed Study work.

This module is dependency-light and has no provider, HTTP, desktop, or store
imports. Provider output is untrusted: unknown fields, omitted fields, invalid
coordinates, and unbounded text all fail closed before any Study semantics use
the transcription.
"""

from __future__ import annotations

import copy
import re
import unicodedata
from collections.abc import Mapping
from typing import Any


SCHEMA_VERSION = 1
CAPTURE_PURPOSES = frozenset({"stuck", "review", "printed_source"})
CAPTURE_SOURCES = frozenset({"camera", "upload"})
CAPTURE_STATUSES = frozenset(
    {"temporary", "normalized", "transcribed", "drafted", "confirmed", "abandoned"}
)
CONFIDENCE_BANDS = frozenset({"high", "medium", "low"})
QUESTION_MATCHES = frozenset({"same", "different", "unknown"})
ASSISTANCE_MODES = frozenset({"next_step", "full_answer"})

MAX_TEXT = 12_000
MAX_LINE_TEXT = 2_000
MAX_LINES = 200
MAX_ANNOTATIONS = 20
MAX_UNREADABLE_REGIONS = 50
_OPAQUE_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")


class StudyCaptureContractError(ValueError):
    """A capture or transcription payload violates its exact wire contract."""


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or not all(isinstance(key, str) for key in value):
        raise StudyCaptureContractError(f"{field} must be an object")
    return value


def _exact(value: Mapping[str, Any], fields: set[str], field: str) -> None:
    if set(value) != fields:
        raise StudyCaptureContractError(f"{field} fields are invalid")


def _text(
    value: Any,
    field: str,
    *,
    maximum: int = MAX_TEXT,
    required: bool = True,
) -> str:
    if not isinstance(value, str):
        raise StudyCaptureContractError(f"{field} must be text")
    normalized = unicodedata.normalize("NFC", value).strip()
    if (required and not normalized) or len(normalized) > maximum:
        raise StudyCaptureContractError(f"{field} is invalid")
    return normalized


def _opaque_id(value: Any, field: str) -> str:
    if not isinstance(value, str) or not _OPAQUE_ID_RE.fullmatch(value):
        raise StudyCaptureContractError(f"{field} is invalid")
    return unicodedata.normalize("NFC", value)


def _enum(value: Any, allowed: frozenset[str], field: str) -> str:
    if not isinstance(value, str) or value not in allowed:
        raise StudyCaptureContractError(f"{field} is invalid")
    return value


def _positive_int(value: Any, field: str, *, maximum: int = 100_000) -> int:
    if type(value) is not int or not 1 <= value <= maximum:
        raise StudyCaptureContractError(f"{field} is invalid")
    return value


def _unit(value: Any, field: str) -> float:
    if type(value) not in (int, float):
        raise StudyCaptureContractError(f"{field} must be numeric")
    normalized = float(value)
    if not 0.0 <= normalized <= 1.0:
        raise StudyCaptureContractError(f"{field} is outside 0..1")
    return normalized


def _region(value: Any, field: str) -> dict[str, float]:
    raw = _mapping(value, field)
    _exact(raw, {"x", "y", "width", "height"}, field)
    result = {
        "x": _unit(raw["x"], f"{field}.x"),
        "y": _unit(raw["y"], f"{field}.y"),
        "width": _unit(raw["width"], f"{field}.width"),
        "height": _unit(raw["height"], f"{field}.height"),
    }
    if result["width"] <= 0 or result["height"] <= 0:
        raise StudyCaptureContractError(f"{field} dimensions are invalid")
    if result["x"] + result["width"] > 1.0 + 1e-9:
        raise StudyCaptureContractError(f"{field} exceeds image width")
    if result["y"] + result["height"] > 1.0 + 1e-9:
        raise StudyCaptureContractError(f"{field} exceeds image height")
    return result


def validate_capture_session(value: Any) -> dict[str, Any]:
    raw = _mapping(value, "capture")
    _exact(
        raw,
        {
            "schema_version",
            "capture_id",
            "space_id",
            "purpose",
            "source_kind",
            "status",
            "revision",
            "preview",
        },
        "capture",
    )
    if raw["schema_version"] != SCHEMA_VERSION:
        raise StudyCaptureContractError("capture schema_version is unsupported")
    preview = _mapping(raw["preview"], "capture.preview")
    _exact(preview, {"width", "height"}, "capture.preview")
    return copy.deepcopy(
        {
            "schema_version": SCHEMA_VERSION,
            "capture_id": _opaque_id(raw["capture_id"], "capture.capture_id"),
            "space_id": _opaque_id(raw["space_id"], "capture.space_id"),
            "purpose": _enum(raw["purpose"], CAPTURE_PURPOSES, "capture.purpose"),
            "source_kind": _enum(
                raw["source_kind"], CAPTURE_SOURCES, "capture.source_kind"
            ),
            "status": _enum(raw["status"], CAPTURE_STATUSES, "capture.status"),
            "revision": _positive_int(raw["revision"], "capture.revision"),
            "preview": {
                "width": _positive_int(preview["width"], "capture.preview.width", maximum=50_000),
                "height": _positive_int(
                    preview["height"], "capture.preview.height", maximum=50_000
                ),
            },
        }
    )


def validate_capture_transform(value: Any) -> dict[str, Any]:
    raw = _mapping(value, "transform")
    _exact(
        raw,
        {
            "schema_version",
            "capture_id",
            "expected_revision",
            "crop",
            "rotation",
            "grayscale",
            "max_edge",
        },
        "transform",
    )
    if raw["schema_version"] != SCHEMA_VERSION:
        raise StudyCaptureContractError("transform schema_version is unsupported")
    rotation = raw["rotation"]
    if type(rotation) is not int or rotation not in {0, 90, 180, 270}:
        raise StudyCaptureContractError("transform.rotation is invalid")
    if type(raw["grayscale"]) is not bool:
        raise StudyCaptureContractError("transform.grayscale must be boolean")
    max_edge = _positive_int(raw["max_edge"], "transform.max_edge", maximum=4096)
    if max_edge < 256:
        raise StudyCaptureContractError("transform.max_edge is invalid")
    return {
        "schema_version": SCHEMA_VERSION,
        "capture_id": _opaque_id(raw["capture_id"], "transform.capture_id"),
        "expected_revision": _positive_int(
            raw["expected_revision"], "transform.expected_revision"
        ),
        "crop": _region(raw["crop"], "transform.crop"),
        "rotation": rotation,
        "grayscale": raw["grayscale"],
        "max_edge": max_edge,
    }


def _line(value: Any, index: int) -> dict[str, Any]:
    field = f"transcription.lines[{index}]"
    raw = _mapping(value, field)
    _exact(raw, {"line_no", "text", "region", "annotations"}, field)
    line_no = _positive_int(raw["line_no"], f"{field}.line_no", maximum=MAX_LINES)
    annotations = raw["annotations"]
    if not isinstance(annotations, list) or len(annotations) > MAX_ANNOTATIONS:
        raise StudyCaptureContractError(f"{field}.annotations is invalid")
    return {
        "line_no": line_no,
        "text": _text(raw["text"], f"{field}.text", maximum=MAX_LINE_TEXT),
        "region": _region(raw["region"], f"{field}.region"),
        "annotations": [
            _text(item, f"{field}.annotations[{annotation_index}]", maximum=300)
            for annotation_index, item in enumerate(annotations)
        ],
    }


def _unreadable_region(value: Any, index: int) -> dict[str, Any]:
    field = f"transcription.unreadable_regions[{index}]"
    raw = _mapping(value, field)
    _exact(raw, {"region", "reason", "critical"}, field)
    if type(raw["critical"]) is not bool:
        raise StudyCaptureContractError(f"{field}.critical must be boolean")
    return {
        "region": _region(raw["region"], f"{field}.region"),
        "reason": _text(raw["reason"], f"{field}.reason", maximum=500),
        "critical": raw["critical"],
    }


def validate_study_transcription(value: Any) -> dict[str, Any]:
    raw = _mapping(value, "transcription")
    _exact(
        raw,
        {
            "schema_version",
            "capture_id",
            "purpose",
            "question_text",
            "student_work",
            "lines",
            "unreadable_regions",
            "confidence_band",
            "question_match",
            "provider",
            "model",
        },
        "transcription",
    )
    if raw["schema_version"] != SCHEMA_VERSION:
        raise StudyCaptureContractError("transcription schema_version is unsupported")
    raw_lines = raw["lines"]
    if not isinstance(raw_lines, list) or len(raw_lines) > MAX_LINES:
        raise StudyCaptureContractError("transcription.lines is invalid")
    lines = [_line(item, index) for index, item in enumerate(raw_lines)]
    line_numbers = [item["line_no"] for item in lines]
    if line_numbers != sorted(line_numbers) or len(line_numbers) != len(set(line_numbers)):
        raise StudyCaptureContractError("transcription line order is invalid")
    raw_unreadable = raw["unreadable_regions"]
    if not isinstance(raw_unreadable, list) or len(raw_unreadable) > MAX_UNREADABLE_REGIONS:
        raise StudyCaptureContractError("transcription.unreadable_regions is invalid")
    unreadable = [
        _unreadable_region(item, index) for index, item in enumerate(raw_unreadable)
    ]
    confidence = _enum(
        raw["confidence_band"], CONFIDENCE_BANDS, "transcription.confidence_band"
    )
    if any(item["critical"] for item in unreadable) and confidence == "high":
        raise StudyCaptureContractError(
            "critical unreadable regions cannot have high confidence"
        )
    question_text = _text(
        raw["question_text"], "transcription.question_text", required=False
    )
    student_work = _text(
        raw["student_work"], "transcription.student_work", required=False
    )
    if not question_text and not student_work and not lines and not unreadable:
        raise StudyCaptureContractError("transcription contains no observable content")
    return copy.deepcopy(
        {
            "schema_version": SCHEMA_VERSION,
            "capture_id": _opaque_id(
                raw["capture_id"], "transcription.capture_id"
            ),
            "purpose": _enum(raw["purpose"], CAPTURE_PURPOSES, "transcription.purpose"),
            "question_text": question_text,
            "student_work": student_work,
            "lines": lines,
            "unreadable_regions": unreadable,
            "confidence_band": confidence,
            "question_match": _enum(
                raw["question_match"], QUESTION_MATCHES, "transcription.question_match"
            ),
            "provider": _text(raw["provider"], "transcription.provider", maximum=100),
            "model": _text(raw["model"], "transcription.model", maximum=300),
        }
    )


def _bounded_text_list(value: Any, field: str, *, maximum: int) -> list[str]:
    if not isinstance(value, list) or len(value) > maximum:
        raise StudyCaptureContractError(f"{field} is invalid")
    return [
        _text(item, f"{field}[{index}]", maximum=1_000)
        for index, item in enumerate(value)
    ]


def validate_study_assistance(value: Any) -> dict[str, Any]:
    raw = _mapping(value, "assistance")
    mode = _enum(raw.get("mode"), ASSISTANCE_MODES, "assistance.mode")
    if mode == "next_step":
        _exact(raw, {"mode", "hint"}, "assistance")
        return {
            "mode": mode,
            "hint": _text(raw["hint"], "assistance.hint", maximum=2_000),
        }
    _exact(
        raw,
        {"mode", "answer", "knowledge_points", "skipped_items"},
        "assistance",
    )
    return {
        "mode": mode,
        "answer": _text(raw["answer"], "assistance.answer"),
        "knowledge_points": _bounded_text_list(
            raw["knowledge_points"], "assistance.knowledge_points", maximum=50
        ),
        "skipped_items": _bounded_text_list(
            raw["skipped_items"], "assistance.skipped_items", maximum=50
        ),
    }


def validate_study_review_draft(value: Any) -> dict[str, Any]:
    raw = _mapping(value, "review")
    _exact(raw, {"deviation_start", "basis", "uncertain_items"}, "review")
    return {
        "deviation_start": _text(
            raw["deviation_start"], "review.deviation_start", maximum=4_000
        ),
        "basis": _text(raw["basis"], "review.basis", maximum=6_000),
        "uncertain_items": _bounded_text_list(
            raw["uncertain_items"], "review.uncertain_items", maximum=50
        ),
    }


__all__ = [
    "ASSISTANCE_MODES",
    "CAPTURE_PURPOSES",
    "CAPTURE_SOURCES",
    "CAPTURE_STATUSES",
    "CONFIDENCE_BANDS",
    "QUESTION_MATCHES",
    "SCHEMA_VERSION",
    "StudyCaptureContractError",
    "validate_capture_session",
    "validate_capture_transform",
    "validate_study_assistance",
    "validate_study_review_draft",
    "validate_study_transcription",
]
