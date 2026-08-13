from __future__ import annotations

from datetime import datetime, timezone

import pytest

from learning.learning_context import LearningExecutionContext
from learning.learning_plans import (
    LEARNING_PLAN_ITEM_TYPE,
    PLAN_ITEM_COMPLETE_ACTIVITY,
    PLAN_ITEM_SKIP_ACTIVITY,
    LearningPlanService,
)
from learning.learning_store import LearningStore
from learning.output_writer import OutputWriter


NOW = datetime(2026, 7, 10, 8, 30, tzinfo=timezone.utc)


@pytest.fixture()
def ctx(tmp_path):
    store = LearningStore(db_path=tmp_path / "learning.db")
    context = LearningExecutionContext(store, owner_id="owner-A")
    context.create_space(title="Algebra", space_id="s1")
    resource = context.put_artifact(
        kind="resource_pack",
        title="Algebra source",
        payload={
            "resources": [{"title": "Algebra.pdf", "purpose": "Primary"}],
            "outline": [
                {
                    "id": "chapter-basics",
                    "title": "Basics",
                    "locator": "ch. 1",
                    "children": [
                        {
                            "id": "section-factors",
                            "title": "Factors",
                            "locator": "§1.1",
                        }
                    ],
                }
            ],
        },
        source_refs=[
            {
                "origin": "imported",
                "structure_status": "reliable",
                "structure_origin": "embedded_pdf_outline",
                "source_label": "Algebra.pdf",
            }
        ],
        review={"mode": "semantic", "status": "passed"},
    )
    context.set_artifact_status(resource["artifact_id"], "active")
    try:
        yield context
    finally:
        store.close()


def _draft(ctx, title="Plan"):
    return OutputWriter(ctx).write_artifact(
        kind="learning_plan",
        title=title,
        payload={
            "goals": ["Master factoring"],
            "phases": [
                {
                    "title": "Refresh basics",
                    "tasks": [
                        {
                            "title": "Review factor pairs",
                            "order": 1,
                            "done_when": "Can list pairs",
                            "mode": "learn",
                            "outline_node_id": "section-factors",
                        },
                        {
                            "title": "Do mixed drill",
                            "order": 2,
                            "done_when": "Score at least 80%",
                            "mode": "practice",
                            "outline_node_id": "section-factors",
                        },
                    ],
                }
            ],
        },
    )["artifact_id"]


def _service(ctx):
    return LearningPlanService(ctx, now=lambda: NOW)


def test_activate_plan_archives_previous_and_materializes_stable_items(ctx):
    service = _service(ctx)
    first = _draft(ctx, "First")
    second = _draft(ctx, "Second")

    service.activate_plan(first)
    result = service.activate_plan(second)

    assert result == {"artifact_id": second, "status": "active", "materialized": 2}
    assert [row["artifact_id"] for row in service.list_plans(status="active")] == [second]
    assert [row["artifact_id"] for row in ctx.list_artifacts(kind="learning_plan", status="archived")] == [first]
    items = service.list_plan_items(artifact_id=second)
    assert [item["item_id"] for item in items] == [f"{second}-0000", f"{second}-0001"]
    assert [item["title"] for item in items] == ["Review factor pairs", "Do mixed drill"]
    assert [item["mode"] for item in items] == ["learn", "practice"]
    assert items[0]["outlineNodeId"] == "section-factors"
    assert all(item["status"] == "open" for item in items)
    assert service.activate_plan(second)["materialized"] == 0


def test_complete_and_skip_record_one_real_activity_each(ctx):
    service = _service(ctx)
    artifact_id = _draft(ctx)
    service.activate_plan(artifact_id)
    items = service.list_plan_items(artifact_id=artifact_id)

    completed = service.complete_item(items[0]["item_id"], note="done")
    skipped = service.skip_item(items[1]["item_id"], note="already know it")

    assert completed["status"] == "completed"
    assert completed["completedAt"] == NOW.isoformat()
    assert skipped["status"] == "skipped"
    assert skipped["skippedAt"] == NOW.isoformat()
    assert [row["activity_type"] for row in ctx.list_activities()] == [PLAN_ITEM_COMPLETE_ACTIVITY, PLAN_ITEM_SKIP_ACTIVITY]
    with pytest.raises(ValueError, match="already completed"):
        service.complete_item(items[0]["item_id"])
    assert len(ctx.list_activities()) == 2


def test_archived_plan_items_cannot_be_changed(ctx):
    service = _service(ctx)
    first = _draft(ctx, "First")
    second = _draft(ctx, "Second")
    service.activate_plan(first)
    old_item = service.list_plan_items(artifact_id=first)[0]
    service.activate_plan(second)

    with pytest.raises(ValueError, match="not active"):
        service.skip_item(old_item["item_id"])


def test_reject_plan_does_not_materialize_items(ctx):
    service = _service(ctx)
    artifact_id = _draft(ctx)

    assert service.reject_plan(artifact_id)["status"] == "rejected"
    assert ctx.list_items(item_type=LEARNING_PLAN_ITEM_TYPE) == []


def test_unknown_outline_binding_keeps_plan_in_draft(ctx):
    artifact_id = OutputWriter(ctx).write_artifact(
        kind="learning_plan",
        title="Invented scope",
        payload={
            "phases": [
                {
                    "title": "Phase",
                    "tasks": [
                        {
                            "title": "Task",
                            "mode": "learn",
                            "outline_node_id": "invented-section",
                        }
                    ],
                }
            ]
        },
    )["artifact_id"]

    with pytest.raises(ValueError, match="unavailable outline nodes"):
        _service(ctx).activate_plan(artifact_id)
    assert ctx.get_artifact(artifact_id)["status"] == "draft"


def test_unbound_tasks_keep_plan_in_draft(ctx):
    artifact_id = OutputWriter(ctx).write_artifact(
        kind="learning_plan",
        title="Partially bound plan",
        payload={
            "phases": [
                {
                    "title": "Phase",
                    "tasks": [
                        {
                            "title": "Read factors",
                            "mode": "learn",
                            "outline_node_id": "section-factors",
                        },
                        {"title": "Unscoped drill", "mode": "practice"},
                    ],
                }
            ]
        },
    )["artifact_id"]

    with pytest.raises(ValueError, match="require outline bindings"):
        _service(ctx).activate_plan(artifact_id)
    assert ctx.get_artifact(artifact_id)["status"] == "draft"


def test_camel_case_outline_binding_materializes_and_compiles(ctx):
    artifact_id = OutputWriter(ctx).write_artifact(
        kind="learning_plan",
        title="Legacy Web plan",
        payload={
            "phases": [
                {
                    "title": "Phase",
                    "tasks": [
                        {
                            "title": "Read factors",
                            "mode": "learn",
                            "outlineNodeId": "section-factors",
                        }
                    ],
                }
            ]
        },
    )["artifact_id"]
    service = _service(ctx)

    service.activate_plan(artifact_id)

    item = service.list_plan_items(artifact_id=artifact_id)[0]
    assert item["outlineNodeId"] == "section-factors"
    assert service.compilation_intents(artifact_id)[0]["outline_node_id"] == "section-factors"


def test_reconcile_restores_lost_binding_without_changing_progress(ctx):
    artifact_id = OutputWriter(ctx).write_artifact(
        kind="learning_plan",
        title="Legacy activated plan",
        payload={
            "phases": [
                {
                    "title": "Phase",
                    "tasks": [
                        {
                            "title": "Read factors",
                            "mode": "learn",
                            "outlineNodeId": "section-factors",
                        }
                    ],
                }
            ]
        },
    )["artifact_id"]
    service = _service(ctx)
    service.activate_plan(artifact_id)
    row = ctx.list_items(
        item_type=LEARNING_PLAN_ITEM_TYPE, artifact_id=artifact_id
    )[0]
    legacy_state = dict(row["state"])
    legacy_state.update(
        {
            "outlineNodeId": "",
            "status": "completed",
            "note": "learner progress must survive",
        }
    )
    ctx.update_item_state(row["item_id"], legacy_state)

    assert service.reconcile_plan_items(artifact_id) == {"created": 0, "repaired": 1}

    repaired = service.list_plan_items(artifact_id=artifact_id)[0]
    assert repaired["outlineNodeId"] == "section-factors"
    assert repaired["status"] == "completed"
    assert repaired["note"] == "learner progress must survive"


def test_reconcile_keeps_active_plan_readable_while_outline_is_unavailable(ctx):
    artifact_id = _draft(ctx, "Accepted before source re-index")
    service = _service(ctx)
    service.activate_plan(artifact_id)
    resource = ctx.list_artifacts(kind="resource_pack", status="active")[0]
    row = ctx.list_items(
        item_type=LEARNING_PLAN_ITEM_TYPE, artifact_id=artifact_id
    )[0]
    state = dict(row["state"])
    state["outlineNodeId"] = ""
    ctx.update_item_state(row["item_id"], state)

    ctx.set_artifact_status(resource["artifact_id"], "archived")

    assert service.reconcile_plan_items(artifact_id) == {"created": 0, "repaired": 0}
    degraded = service.list_plan_items(artifact_id=artifact_id)[0]
    assert degraded["outlineNodeId"] == ""
    assert degraded["status"] == "open"


def test_unknown_camel_case_outline_binding_keeps_plan_in_draft(ctx):
    artifact_id = OutputWriter(ctx).write_artifact(
        kind="learning_plan",
        title="Invented legacy scope",
        payload={
            "phases": [
                {
                    "title": "Phase",
                    "tasks": [
                        {
                            "title": "Task",
                            "outlineNodeId": "invented-section",
                        }
                    ],
                }
            ]
        },
    )["artifact_id"]

    with pytest.raises(ValueError, match="unavailable outline nodes"):
        _service(ctx).activate_plan(artifact_id)
    assert ctx.get_artifact(artifact_id)["status"] == "draft"
