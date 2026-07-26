# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""S-2 exact whiteboard scene and envelope contracts."""

from __future__ import annotations

import pytest

from learning.learning_contract import ContractError, validate_envelope
from learning.whiteboard_contract import (
    MAX_ELEMENT_CONTENT_CODEPOINTS,
    MAX_SCENE_CONTENT_CODEPOINTS,
    MAX_WHITEBOARD_ELEMENTS,
    WhiteboardContractError,
    canonical_sha256,
    validate_whiteboard_scene,
    validate_whiteboard_snapshot_payload,
    whiteboard_working_item_id,
)


def _element(element_type: str, element_id: str = "e1") -> dict:
    common = {
        "element_id": element_id,
        "type": element_type,
        "x": 10,
        "y": -10,
        "tone": "ink",
        "stroke_width": 1,
    }
    if element_type in {"text", "math"}:
        return {**common, "width": 120, "height": 40, "content": "x + y = 3"}
    if element_type in {"rectangle", "ellipse"}:
        return {**common, "width": 120, "height": 40}
    return {**common, "end_x": 100, "end_y": 200}


def _scene(*elements: dict) -> dict:
    return {"schema_version": 1, "elements": list(elements)}


def _payload(scene: dict, **overrides) -> dict:
    value = {
        "schema_version": 1,
        "activity_id": "activity-1",
        "lineage_id": "lineage-1",
        "revision": 1,
        "parent_artifact_id": None,
        "scene": scene,
        "scene_sha256": canonical_sha256(scene),
    }
    value.update(overrides)
    return value


@pytest.mark.parametrize(
    "element_type", ["text", "math", "line", "arrow", "rectangle", "ellipse"]
)
def test_all_frozen_element_shapes_round_trip(element_type):
    scene = _scene(_element(element_type))

    assert validate_whiteboard_scene(scene) == scene


@pytest.mark.parametrize(
    ("element_type", "forbidden"),
    [
        ("line", {"width": 20}),
        ("arrow", {"content": "no"}),
        ("rectangle", {"end_x": 20}),
        ("ellipse", {"content": "no"}),
        ("text", {"end_y": 20}),
        ("math", {"plugin": "no"}),
    ],
)
def test_discriminated_elements_reject_unknown_or_cross_shape_fields(
    element_type, forbidden
):
    with pytest.raises(WhiteboardContractError, match="fields"):
        validate_whiteboard_scene(_scene({**_element(element_type), **forbidden}))


@pytest.mark.parametrize(
    "content",
    [
        "https://example.invalid/image.png",
        "data:image/png;base64,AAAA",
        "<svg><path d='M0 0'/></svg>",
        "<iframe src='x'></iframe>",
        "javascript:alert(1)",
        "onclick = run()",
        "url(file:///secret)",
        r"\href{https://example.invalid}{x}",
        "bad\x00control",
    ],
)
def test_text_and_math_reject_external_executable_or_control_content(content):
    with pytest.raises(WhiteboardContractError):
        validate_whiteboard_scene(_scene({**_element("text"), "content": content}))


def test_scene_limits_count_ids_geometry_and_total_content():
    too_many = [_element("line", f"e{i}") for i in range(MAX_WHITEBOARD_ELEMENTS + 1)]
    with pytest.raises(WhiteboardContractError, match="elements"):
        validate_whiteboard_scene(_scene(*too_many))
    with pytest.raises(WhiteboardContractError, match="unique"):
        validate_whiteboard_scene(_scene(_element("line"), _element("arrow")))
    with pytest.raises(WhiteboardContractError, match="x must"):
        validate_whiteboard_scene(_scene({**_element("line"), "x": 10.5}))
    with pytest.raises(WhiteboardContractError, match="content exceeds"):
        validate_whiteboard_scene(
            _scene(
                *[
                    {
                        **_element("text", f"e{i}"),
                        "content": "学" * MAX_ELEMENT_CONTENT_CODEPOINTS,
                    }
                    for i in range(MAX_SCENE_CONTENT_CODEPOINTS // MAX_ELEMENT_CONTENT_CODEPOINTS + 1)
                ]
            )
        )


def test_snapshot_hash_exact_fields_and_parent_are_enforced():
    scene = _scene(_element("math"))
    assert validate_whiteboard_snapshot_payload(_payload(scene))["scene"] == scene

    with pytest.raises(WhiteboardContractError, match="hash"):
        validate_whiteboard_snapshot_payload(
            _payload(scene, scene_sha256="0" * 64)
        )
    with pytest.raises(WhiteboardContractError, match="fields"):
        validate_whiteboard_snapshot_payload({**_payload(scene), "html": "<b>x</b>"})
    with pytest.raises(WhiteboardContractError, match="parent_artifact_id"):
        validate_whiteboard_snapshot_payload(_payload(scene, parent_artifact_id="bad id"))


def test_learning_envelope_adds_exact_whiteboard_kind_and_32_ref_cap():
    scene = _scene(_element("text"))
    envelope = {
        "version": 1,
        "kind": "whiteboard_snapshot",
        "space_id": "space-1",
        "title": "Whiteboard snapshot 1",
        "source_refs": [{"origin": "whiteboard"}],
        "payload": _payload(scene),
        "review": {"mode": "deterministic", "status": "passed"},
    }

    assert validate_envelope(envelope).to_dict() == envelope
    with pytest.raises(ContractError, match="source_refs exceeds"):
        validate_envelope(
            {**envelope, "source_refs": ["source"] * 33}
        )


def test_working_item_identity_is_owner_space_activity_scoped_and_stable():
    first = whiteboard_working_item_id("owner-1", "space-1", "activity-1")

    assert first == whiteboard_working_item_id("owner-1", "space-1", "activity-1")
    assert first != whiteboard_working_item_id("owner-1", "space-2", "activity-1")
    assert first.startswith("wbw_")
