"""Tests for tools/learning_tools.py — the minimal M1 ``learning`` toolset.

Invariants: ``owner_id`` never appears in a tool schema (owner is injected from
the active context, never from tool args); trust-boundary operations
(activate/reject/archive) are NOT exposed as model tools; every tool reads the
runtime context from the ContextVar scope and fails cleanly when absent.
"""

import json

import pytest

from tools.registry import registry
from learning.learning_store import LearningStore
from learning.learning_context import (
    LearningExecutionContext,
    learning_context_scope,
)
import tools.learning_tools as lt


EXPECTED_TOOLS = {
    "learning_space_list",
    "learning_space_create",
    "learning_space_select",
    "learning_index_build",
    "learning_draft_create",
    "learning_material_alignment_propose",
    "learning_artifact_list",
}

FORBIDDEN_TOOLS = {
    "learning_activate",
    "learning_reject",
    "learning_archive",
    "learning_artifact_activate",
}


@pytest.fixture()
def ctx(tmp_path):
    store = LearningStore(db_path=tmp_path / "learning.db")
    context = LearningExecutionContext(store, owner_id="owner-A")
    yield context
    store.close()


def _result(raw):
    return json.loads(raw)


# --------------------------------------------------------------------------- #
# Registration + schema invariants
# --------------------------------------------------------------------------- #

def test_learning_toolset_registered():
    names = set(registry.get_tool_names_for_toolset("learning"))
    assert EXPECTED_TOOLS <= names


def test_trust_boundary_ops_not_exposed():
    names = set(registry.get_tool_names_for_toolset("learning"))
    assert names.isdisjoint(FORBIDDEN_TOOLS)


def test_no_owner_id_in_any_schema():
    for schema in lt.LEARNING_TOOL_SCHEMAS:
        props = schema.get("parameters", {}).get("properties", {})
        assert "owner_id" not in props, schema["name"]


# --------------------------------------------------------------------------- #
# Behaviour under an active context
# --------------------------------------------------------------------------- #

def test_space_create_and_list(ctx):
    with learning_context_scope(ctx):
        created = _result(lt._handle_space_create({"title": "Algebra"}))
        assert created["success"] is True
        listed = _result(lt._handle_space_list({}))
    titles = [s["title"] for s in listed["spaces"]]
    assert "Algebra" in titles


def test_space_select(ctx):
    with learning_context_scope(ctx):
        ctx.create_space(title="Algebra", space_id="s1")
        ctx.create_space(title="Biology", space_id="s2")
        out = _result(lt._handle_space_select({"space_id": "s1"}))
        assert out["success"] is True and out["space_id"] == "s1"
        assert ctx.current_space() == "s1"


def test_draft_create_persists_draft(ctx):
    with learning_context_scope(ctx):
        ctx.create_space(title="Algebra", space_id="s1")
        out = _result(
            lt._handle_draft_create(
                {
                    "kind": "flashcard_deck",
                    "title": "Chapter 1",
                    "payload": {"cards": [{"front": "q", "back": "a"}]},
                }
            )
        )
        assert out["success"] is True
        assert out["status"] == "draft"
        got = ctx.get_artifact(out["artifact_id"])
        assert got["status"] == "draft"


def test_material_alignment_tool_creates_one_reviewable_batch_draft(ctx):
    with learning_context_scope(ctx):
        ctx.create_space(title="Calculus", space_id="s1")
        out = _result(
            lt._handle_material_alignment_propose(
                {
                    "title": "Calculus material alignment",
                    "materials": [
                        {
                            "material_id": "textbook",
                            "title": "Textbook",
                            "source_ref": "read:textbook",
                            "structure": [
                                {
                                    "section_id": "2.3",
                                    "title": "Limits",
                                    "locator": "§2.3",
                                }
                            ],
                        },
                        {
                            "material_id": "workbook",
                            "title": "Workbook",
                            "source_ref": "read:workbook",
                            "structure": [],
                        },
                    ],
                    "course_groups": [
                        {
                            "proposed_title": "Calculus",
                            "rationale": "Both materials concern calculus.",
                            "skeleton": {
                                "material_id": "textbook",
                                "reason": "It has real numbered chapters.",
                                "role": "explanation",
                                "role_reason": "It explains the subject.",
                            },
                            "attachments": [
                                {
                                    "material_id": "workbook",
                                    "role": "practice",
                                    "role_reason": "It contains exercises.",
                                    "mappings": [
                                        {
                                            "source_locator": "p.41",
                                            "target_section_id": "2.3",
                                            "reason": "The exercises practice limits.",
                                        }
                                    ],
                                    "unaligned": [],
                                }
                            ],
                        }
                    ],
                    "ungrouped": [],
                }
            )
        )
        artifact = ctx.get_artifact(out["artifact_id"])
    assert out["success"] is True
    assert out["status"] == "draft"
    assert out["review"] == "pending"
    assert artifact["kind"] == "material_alignment"
    assert artifact["status"] == "draft"
    assert artifact["envelope"]["payload"]["course_groups"][0][
        "material_ids"
    ] == ["textbook", "workbook"]
    assert len(artifact["envelope"]["source_refs"]) == 2


def test_index_build_tool(ctx):
    with learning_context_scope(ctx):
        ctx.create_space(title="Algebra", space_id="s1")
        out = _result(lt._handle_index_build({}))
        assert out["success"] is True
        assert out["index"]["space_id"] == "s1"
        assert out["index"]["index_version"] >= 1


def test_artifact_list_returns_draft_and_active(ctx):
    with learning_context_scope(ctx):
        ctx.create_space(title="Algebra", space_id="s1")
        d = _result(
            lt._handle_draft_create(
                {
                    "kind": "flashcard_deck",
                    "title": "draft",
                    "payload": {"cards": [{"front": "q", "back": "a"}]},
                }
            )
        )
        a = _result(
            lt._handle_draft_create(
                {
                    "kind": "flashcard_deck",
                    "title": "active",
                    "payload": {"cards": [{"front": "q", "back": "a"}]},
                }
            )
        )
        ctx.set_artifact_status(a["artifact_id"], "active")
        # archived should be excluded from the model-facing list
        arch = _result(
            lt._handle_draft_create(
                {
                    "kind": "flashcard_deck",
                    "title": "arch",
                    "payload": {"cards": [{"front": "q", "back": "a"}]},
                }
            )
        )
        ctx.set_artifact_status(arch["artifact_id"], "active")
        ctx.set_artifact_status(arch["artifact_id"], "archived")

        out = _result(lt._handle_artifact_list({}))
    ids = {x["artifact_id"] for x in out["artifacts"]}
    assert d["artifact_id"] in ids and a["artifact_id"] in ids
    assert arch["artifact_id"] not in ids


def test_artifact_list_without_selected_space_returns_error(ctx):
    with learning_context_scope(ctx):
        out = _result(lt._handle_artifact_list({}))
    assert out.get("success") is not True
    assert "error" in out or out.get("ok") is False


def test_bad_draft_payload_returns_error_not_crash(ctx):
    with learning_context_scope(ctx):
        ctx.create_space(title="Algebra", space_id="s1")
        out = _result(
            lt._handle_draft_create(
                {"kind": "flashcard_deck", "title": "x", "payload": {"cards": []}}
            )
        )
    assert out.get("success") is not True
    assert "error" in out or out.get("ok") is False


# --------------------------------------------------------------------------- #
# Owner comes only from the context
# --------------------------------------------------------------------------- #

def test_tools_require_active_context(ctx):
    # No scope bound → tools return a clean error, not a traceback.
    out = _result(lt._handle_space_list({}))
    assert out.get("success") is not True


def test_owner_isolation_across_contexts(tmp_path):
    store = LearningStore(db_path=tmp_path / "learning.db")
    try:
        a = LearningExecutionContext(store, owner_id="owner-A")
        with learning_context_scope(a):
            a.create_space(title="Algebra", space_id="s1")
            lt._handle_draft_create(
                {
                    "kind": "flashcard_deck",
                    "title": "A deck",
                    "payload": {"cards": [{"front": "q", "back": "a"}]},
                }
            )
        b = LearningExecutionContext(store, owner_id="owner-B", space_id="s1")
        with learning_context_scope(b):
            out = _result(lt._handle_artifact_list({}))
        assert out["artifacts"] == []
    finally:
        store.close()
