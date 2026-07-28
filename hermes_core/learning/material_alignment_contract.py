"""Deterministic contract for auditable multi-material alignment proposals.

The agent may propose relationships, but it may not activate them.  One payload
contains the complete batch decision (course grouping, one real skeleton per
group, section/range mappings, roles, and explicit unaligned material) so review
cannot leave half of a proposal active.
"""

from __future__ import annotations

import copy
from collections.abc import Mapping
from typing import Any


SCHEMA_VERSION = 1
MATERIAL_ROLES = frozenset({"explanation", "practice", "assessment", "reference"})
MAX_MATERIALS = 50
MAX_GROUPS = 50
MAX_SECTIONS_PER_MATERIAL = 300
MAX_ATTACHMENTS_PER_GROUP = 49
MAX_MAPPINGS_PER_ATTACHMENT = 500
MAX_UNALIGNED_PER_ATTACHMENT = 500
MAX_TEXT = 2_000


class MaterialAlignmentContractError(ValueError):
    pass


def _object(value: Any, label: str, fields: set[str]) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise MaterialAlignmentContractError(f"{label} must be an object")
    unknown = set(value) - fields
    missing = fields - set(value)
    if missing:
        raise MaterialAlignmentContractError(
            f"{label} is missing field: {sorted(missing)[0]}"
        )
    if unknown:
        raise MaterialAlignmentContractError(
            f"{label} has unknown field: {sorted(unknown)[0]}"
        )
    return value


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise MaterialAlignmentContractError(f"{label} must be non-empty text")
    text = value.strip()
    if len(text) > MAX_TEXT:
        raise MaterialAlignmentContractError(f"{label} is too long")
    return text


def _list(value: Any, label: str, *, minimum: int = 0, maximum: int) -> list[Any]:
    if not isinstance(value, list) or not minimum <= len(value) <= maximum:
        raise MaterialAlignmentContractError(
            f"{label} must contain {minimum}-{maximum} items"
        )
    return value


def _role(value: Any, label: str) -> str:
    role = _text(value, label)
    if role not in MATERIAL_ROLES:
        raise MaterialAlignmentContractError(
            f"{label} must be one of {sorted(MATERIAL_ROLES)}"
        )
    return role


def _material(raw: Any, index: int) -> dict[str, Any]:
    label = f"materials[{index}]"
    value = _object(
        raw,
        label,
        {"material_id", "title", "source_ref", "structure"},
    )
    sections = []
    for section_index, raw_section in enumerate(
        _list(
            value["structure"],
            f"{label}.structure",
            maximum=MAX_SECTIONS_PER_MATERIAL,
        )
    ):
        section_label = f"{label}.structure[{section_index}]"
        section = _object(
            raw_section, section_label, {"section_id", "title", "locator"}
        )
        sections.append(
            {
                "section_id": _text(section["section_id"], f"{section_label}.section_id"),
                "title": _text(section["title"], f"{section_label}.title"),
                "locator": _text(section["locator"], f"{section_label}.locator"),
            }
        )
    section_ids = [item["section_id"] for item in sections]
    if len(section_ids) != len(set(section_ids)):
        raise MaterialAlignmentContractError(f"{label}.structure has duplicate section_id")
    return {
        "material_id": _text(value["material_id"], f"{label}.material_id"),
        "title": _text(value["title"], f"{label}.title"),
        "source_ref": _text(value["source_ref"], f"{label}.source_ref"),
        "structure": sections,
    }


def _skeleton(raw: Any, label: str) -> dict[str, str]:
    value = _object(raw, label, {"material_id", "reason", "role", "role_reason"})
    return {
        "material_id": _text(value["material_id"], f"{label}.material_id"),
        "reason": _text(value["reason"], f"{label}.reason"),
        "role": _role(value["role"], f"{label}.role"),
        "role_reason": _text(value["role_reason"], f"{label}.role_reason"),
    }


def _attachment(raw: Any, label: str) -> dict[str, Any]:
    value = _object(
        raw,
        label,
        {"material_id", "role", "role_reason", "mappings", "unaligned"},
    )
    mappings = []
    for index, raw_mapping in enumerate(
        _list(
            value["mappings"],
            f"{label}.mappings",
            maximum=MAX_MAPPINGS_PER_ATTACHMENT,
        )
    ):
        mapping_label = f"{label}.mappings[{index}]"
        mapping = _object(
            raw_mapping,
            mapping_label,
            {"source_locator", "target_section_id", "reason"},
        )
        mappings.append(
            {
                "source_locator": _text(
                    mapping["source_locator"], f"{mapping_label}.source_locator"
                ),
                "target_section_id": _text(
                    mapping["target_section_id"],
                    f"{mapping_label}.target_section_id",
                ),
                "reason": _text(mapping["reason"], f"{mapping_label}.reason"),
            }
        )
    unaligned = []
    for index, raw_gap in enumerate(
        _list(
            value["unaligned"],
            f"{label}.unaligned",
            maximum=MAX_UNALIGNED_PER_ATTACHMENT,
        )
    ):
        gap_label = f"{label}.unaligned[{index}]"
        gap = _object(raw_gap, gap_label, {"source_locator", "reason"})
        unaligned.append(
            {
                "source_locator": _text(
                    gap["source_locator"], f"{gap_label}.source_locator"
                ),
                "reason": _text(gap["reason"], f"{gap_label}.reason"),
            }
        )
    if not mappings and not unaligned:
        raise MaterialAlignmentContractError(
            f"{label} must declare mappings or explicit unaligned ranges"
        )
    return {
        "material_id": _text(value["material_id"], f"{label}.material_id"),
        "role": _role(value["role"], f"{label}.role"),
        "role_reason": _text(value["role_reason"], f"{label}.role_reason"),
        "mappings": mappings,
        "unaligned": unaligned,
    }


def validate_material_alignment_payload(payload: Any) -> dict[str, Any]:
    """Return a normalized owned payload or raise before persistence."""
    root = _object(
        payload,
        "material_alignment",
        {"schema_version", "batch_id", "materials", "course_groups", "ungrouped"},
    )
    if root["schema_version"] != SCHEMA_VERSION:
        raise MaterialAlignmentContractError(
            f"material_alignment.schema_version must be {SCHEMA_VERSION}"
        )
    materials = [
        _material(raw, index)
        for index, raw in enumerate(
            _list(
                root["materials"],
                "material_alignment.materials",
                minimum=2,
                maximum=MAX_MATERIALS,
            )
        )
    ]
    material_ids = [item["material_id"] for item in materials]
    if len(material_ids) != len(set(material_ids)):
        raise MaterialAlignmentContractError("material ids must be unique")
    material_by_id = {item["material_id"]: item for item in materials}

    groups = []
    assigned: set[str] = set()
    group_ids: set[str] = set()
    for group_index, raw_group in enumerate(
        _list(
            root["course_groups"],
            "material_alignment.course_groups",
            minimum=1,
            maximum=MAX_GROUPS,
        )
    ):
        label = f"material_alignment.course_groups[{group_index}]"
        group = _object(
            raw_group,
            label,
            {"group_id", "proposed_title", "rationale", "material_ids", "skeleton", "attachments"},
        )
        group_id = _text(group["group_id"], f"{label}.group_id")
        if group_id in group_ids:
            raise MaterialAlignmentContractError("course group ids must be unique")
        group_ids.add(group_id)
        skeleton = _skeleton(group["skeleton"], f"{label}.skeleton")
        attachments = [
            _attachment(item, f"{label}.attachments[{index}]")
            for index, item in enumerate(
                _list(
                    group["attachments"],
                    f"{label}.attachments",
                    maximum=MAX_ATTACHMENTS_PER_GROUP,
                )
            )
        ]
        declared_ids = [
            _text(item, f"{label}.material_ids")
            for item in _list(
                group["material_ids"],
                f"{label}.material_ids",
                minimum=1,
                maximum=MAX_MATERIALS,
            )
        ]
        member_ids = [skeleton["material_id"], *[item["material_id"] for item in attachments]]
        if len(member_ids) != len(set(member_ids)):
            raise MaterialAlignmentContractError(f"{label} assigns a material more than once")
        if set(declared_ids) != set(member_ids) or len(declared_ids) != len(member_ids):
            raise MaterialAlignmentContractError(
                f"{label}.material_ids must exactly match skeleton plus attachments"
            )
        unknown = set(member_ids) - set(material_by_id)
        if unknown:
            raise MaterialAlignmentContractError(
                f"{label} references unknown material: {sorted(unknown)[0]}"
            )
        overlap = assigned.intersection(member_ids)
        if overlap:
            raise MaterialAlignmentContractError(
                f"material assigned to multiple course groups: {sorted(overlap)[0]}"
            )
        assigned.update(member_ids)
        skeleton_sections = material_by_id[skeleton["material_id"]]["structure"]
        if not skeleton_sections:
            raise MaterialAlignmentContractError(
                f"{label}.skeleton must reference a material with real extracted structure"
            )
        target_ids = {item["section_id"] for item in skeleton_sections}
        for attachment in attachments:
            for mapping in attachment["mappings"]:
                if mapping["target_section_id"] not in target_ids:
                    raise MaterialAlignmentContractError(
                        f"{label} mapping targets a section absent from the skeleton"
                    )
        groups.append(
            {
                "group_id": group_id,
                "proposed_title": _text(
                    group["proposed_title"], f"{label}.proposed_title"
                ),
                "rationale": _text(group["rationale"], f"{label}.rationale"),
                "material_ids": declared_ids,
                "skeleton": skeleton,
                "attachments": attachments,
            }
        )

    ungrouped = []
    ungrouped_ids: set[str] = set()
    for index, raw_item in enumerate(
        _list(
            root["ungrouped"],
            "material_alignment.ungrouped",
            maximum=MAX_MATERIALS,
        )
    ):
        label = f"material_alignment.ungrouped[{index}]"
        item = _object(raw_item, label, {"material_id", "reason"})
        material_id = _text(item["material_id"], f"{label}.material_id")
        if material_id not in material_by_id:
            raise MaterialAlignmentContractError(
                f"{label} references unknown material"
            )
        if material_id in assigned or material_id in ungrouped_ids:
            raise MaterialAlignmentContractError(
                f"material assigned more than once: {material_id}"
            )
        ungrouped_ids.add(material_id)
        ungrouped.append(
            {
                "material_id": material_id,
                "reason": _text(item["reason"], f"{label}.reason"),
            }
        )

    missing = set(material_ids) - assigned - ungrouped_ids
    if missing:
        raise MaterialAlignmentContractError(
            f"every material must be grouped or explicitly ungrouped: {sorted(missing)[0]}"
        )
    return copy.deepcopy(
        {
            "schema_version": SCHEMA_VERSION,
            "batch_id": _text(root["batch_id"], "material_alignment.batch_id"),
            "materials": materials,
            "course_groups": groups,
            "ungrouped": ungrouped,
        }
    )


__all__ = [
    "MATERIAL_ROLES",
    "MaterialAlignmentContractError",
    "validate_material_alignment_payload",
]
