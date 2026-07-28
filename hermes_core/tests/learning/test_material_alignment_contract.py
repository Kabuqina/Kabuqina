from __future__ import annotations

import copy

import pytest

from learning.material_alignment_contract import (
    MATERIAL_ROLES,
    MaterialAlignmentContractError,
    validate_material_alignment_payload,
)


def _payload() -> dict:
    return {
        "schema_version": 1,
        "batch_id": "batch-1",
        "materials": [
            {
                "material_id": "textbook",
                "title": "Calculus textbook",
                "source_ref": "read:textbook",
                "structure": [
                    {"section_id": "2.3", "title": "Limits", "locator": "§2.3"},
                    {"section_id": "2.4", "title": "Continuity", "locator": "§2.4"},
                ],
            },
            {
                "material_id": "workbook",
                "title": "Calculus exercises",
                "source_ref": "read:workbook",
                "structure": [],
            },
        ],
        "course_groups": [
            {
                "group_id": "group-1",
                "proposed_title": "Calculus",
                "rationale": "Both files concern the same calculus course.",
                "material_ids": ["textbook", "workbook"],
                "skeleton": {
                    "material_id": "textbook",
                    "reason": "It exposes real numbered chapters and both files can be checked against them.",
                    "role": "explanation",
                    "role_reason": "It supplies the main explanations.",
                },
                "attachments": [
                    {
                        "material_id": "workbook",
                        "role": "practice",
                        "role_reason": "It is predominantly exercises.",
                        "mappings": [
                            {
                                "source_locator": "p.41",
                                "target_section_id": "2.3",
                                "reason": "The page explicitly drills limit calculations.",
                            }
                        ],
                        "unaligned": [
                            {
                                "source_locator": "appendix A",
                                "reason": "No matching skeleton section is present.",
                            }
                        ],
                    }
                ],
            }
        ],
        "ungrouped": [],
    }


def test_valid_alignment_keeps_auditable_roles_and_gaps():
    result = validate_material_alignment_payload(_payload())
    attachment = result["course_groups"][0]["attachments"][0]
    assert MATERIAL_ROLES == {"explanation", "practice", "assessment", "reference"}
    assert attachment["mappings"][0]["target_section_id"] == "2.3"
    assert attachment["unaligned"][0]["source_locator"] == "appendix A"


def test_every_material_must_be_grouped_or_explicitly_ungrouped():
    payload = _payload()
    payload["course_groups"][0]["material_ids"] = ["textbook"]
    payload["course_groups"][0]["attachments"] = []
    with pytest.raises(MaterialAlignmentContractError, match="grouped or explicitly ungrouped"):
        validate_material_alignment_payload(payload)


def test_mapping_cannot_target_an_invented_skeleton_section():
    payload = _payload()
    payload["course_groups"][0]["attachments"][0]["mappings"][0][
        "target_section_id"
    ] = "invented"
    with pytest.raises(MaterialAlignmentContractError, match="absent from the skeleton"):
        validate_material_alignment_payload(payload)


def test_skeleton_must_have_real_extracted_structure():
    payload = _payload()
    payload["materials"][0]["structure"] = []
    with pytest.raises(MaterialAlignmentContractError, match="real extracted structure"):
        validate_material_alignment_payload(payload)


def test_coverage_metrics_are_not_part_of_the_contract():
    payload = _payload()
    payload["coverage"] = 0.8
    with pytest.raises(MaterialAlignmentContractError, match="unknown field: coverage"):
        validate_material_alignment_payload(payload)


def test_separate_courses_are_separate_groups_not_one_synthetic_tree():
    payload = _payload()
    second = copy.deepcopy(payload["materials"][1])
    second["structure"] = [
        {"section_id": "bio-1", "title": "Cells", "locator": "Chapter 1"}
    ]
    payload["materials"][1] = second
    payload["course_groups"] = [
        {
            "group_id": "math",
            "proposed_title": "Calculus",
            "rationale": "The textbook is calculus.",
            "material_ids": ["textbook"],
            "skeleton": {
                "material_id": "textbook",
                "reason": "It has calculus chapters.",
                "role": "explanation",
                "role_reason": "It explains calculus.",
            },
            "attachments": [],
        },
        {
            "group_id": "biology",
            "proposed_title": "Biology",
            "rationale": "The other file is biology, not calculus.",
            "material_ids": ["workbook"],
            "skeleton": {
                "material_id": "workbook",
                "reason": "It has a real biology chapter.",
                "role": "explanation",
                "role_reason": "It explains biology.",
            },
            "attachments": [],
        },
    ]
    result = validate_material_alignment_payload(payload)
    assert [group["proposed_title"] for group in result["course_groups"]] == [
        "Calculus",
        "Biology",
    ]
