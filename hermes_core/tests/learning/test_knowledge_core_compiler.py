import pytest

from learning.flashcards import FlashcardService
from learning.knowledge_core_compiler import (
    CompilationStop,
    MAX_PAGES_PER_COMPILATION,
    MAX_PAGES_PER_WINDOW,
    plan_compilation,
    read_source_windows,
    validate_candidates,
    write_draft,
)
from learning.learning_context import LearningExecutionContext
from learning.learning_map import LearningMapService
from learning.learning_store import LearningStore


@pytest.fixture()
def ctx(tmp_path):
    store = LearningStore(tmp_path / "learning.db")
    context = LearningExecutionContext(store, "owner-compiler")
    context.create_space(title="Python", space_id="course-1")
    yield context
    store.close()


def _resource(ctx, *, locator="p. 1", next_locator="p. 80"):
    artifact = ctx.put_artifact(
        kind="resource_pack",
        title="Python.pdf",
        payload={
            "resources": [
                {
                    "title": "Python.pdf",
                    "purpose": "Primary source",
                    "credibility": "Learner-owned",
                }
            ],
            "outline": [
                {"id": "section-1", "title": "Variables", "locator": locator},
                {"id": "section-2", "title": "Functions", "locator": next_locator},
            ],
        },
        source_refs=[
            {
                "origin": "imported",
                "structure_status": "reliable",
                "structure_origin": "embedded_pdf_outline",
                "source_label": "Python.pdf",
                "pages": 120,
            }
        ],
        review={"mode": "semantic", "status": "passed"},
    )
    ctx.set_artifact_status(artifact["artifact_id"], "active")
    return artifact["artifact_id"]


def _request(ctx, *, node="section-1", key="request-1"):
    revision = LearningMapService(ctx).get_map()["revision"]
    return {
        "space_id": "course-1",
        "outline_node_id": node,
        "trigger": "start_learning",
        "expected_map_revision": revision,
        "idempotency_key": key,
    }


def _candidate(windows):
    return {
        "candidates": [
            {
                "title": "变量绑定解决什么问题？",
                "keyStatement": "变量把名称绑定到对象，使后续表达式可以引用该对象。",
                "sourceWindowIds": [windows[0]["id"]],
                "sourceExcerptFingerprints": [windows[0]["contentFingerprint"]],
                "conceptKey": "variable-binding",
                "order": 0,
            }
        ]
    }


def test_scope_requires_real_locator_and_caps_windows_at_12_and_48_pages(ctx):
    artifact_id = _resource(ctx)
    plan = plan_compilation(ctx, _request(ctx))
    calls = []

    def reader(requested_artifact, start, end):
        calls.append((requested_artifact, start, end))
        return {
            "artifactId": requested_artifact,
            "title": "Python.pdf",
            "pageStart": start,
            "pageEnd": end,
            "content": f"pages {start}-{end}: variables and bindings",
        }

    windows = read_source_windows(plan, reader)

    assert all(end - start + 1 <= MAX_PAGES_PER_WINDOW for _, start, end in calls)
    assert sum(end - start + 1 for _, start, end in calls) == MAX_PAGES_PER_COMPILATION
    assert {item[0] for item in calls} == {artifact_id}
    assert calls == [
        (artifact_id, 1, 12),
        (artifact_id, 13, 24),
        (artifact_id, 25, 36),
        (artifact_id, 37, 48),
    ]


def test_missing_locator_stops_without_title_search(ctx):
    _resource(ctx, locator="Chapter one", next_locator="p. 20")
    with pytest.raises(CompilationStop) as caught:
        plan_compilation(ctx, _request(ctx))
    assert caught.value.reason_code == "outline_locator_missing"


def test_unknown_window_and_duplicate_concept_are_rejected(ctx):
    _resource(ctx)
    plan = plan_compilation(ctx, _request(ctx))
    windows = read_source_windows(
        plan,
        lambda artifact, start, end: {
            "title": "Python.pdf",
            "pageStart": start,
            "pageEnd": end,
            "content": "trusted text",
        },
    )
    invalid = _candidate(windows)
    invalid["candidates"][0]["sourceWindowIds"] = ["window-invented"]
    with pytest.raises(ValueError, match="unknown"):
        validate_candidates(invalid, windows)
    duplicate = _candidate(windows)
    duplicate["candidates"].append(
        {**duplicate["candidates"][0], "title": "Renamed", "order": 1}
    )
    with pytest.raises(ValueError, match="duplicate"):
        validate_candidates(duplicate, windows)


def test_compiler_writes_reviewable_draft_and_map_changes_only_after_activation(ctx):
    _resource(ctx, next_locator="p. 5")
    plan = plan_compilation(ctx, _request(ctx))
    windows = read_source_windows(
        plan,
        lambda artifact, start, end: {
            "title": "Python.pdf",
            "pageStart": start,
            "pageEnd": end,
            "content": "Variables bind names to objects.",
        },
    )
    candidates = validate_candidates(_candidate(windows), windows)
    before = LearningMapService(ctx).get_map()

    draft = write_draft(ctx, plan, windows, candidates)
    replay = write_draft(ctx, plan, windows, candidates)

    assert replay["artifact_id"] == draft["artifact_id"]
    assert replay["reused"] is True
    artifact = ctx.get_artifact(draft["artifact_id"])
    assert artifact["status"] == "draft"
    assert artifact["review"]["mode"] == "semantic"
    assert LearningMapService(ctx).get_map()["knowledgeCores"] == before["knowledgeCores"]

    ctx.set_artifact_review(draft["artifact_id"], "passed", review_mode="semantic")
    FlashcardService(ctx).activate_deck(draft["artifact_id"])
    cores = LearningMapService(ctx).get_map()["knowledgeCores"]
    assert len(cores) == 1
    assert cores[0]["outlineNodeId"] == "section-1"
    assert cores[0]["sourceRefs"][0]["locator"] == "pp. 1-4"


def test_active_core_prevents_duplicate_compilation(ctx):
    _resource(ctx, next_locator="p. 3")
    request = _request(ctx)
    plan = plan_compilation(ctx, request)
    windows = read_source_windows(
        plan,
        lambda artifact, start, end: {
            "title": "Python.pdf",
            "pageStart": start,
            "pageEnd": end,
            "content": "Variables bind names.",
        },
    )
    draft = write_draft(ctx, plan, windows, validate_candidates(_candidate(windows), windows))
    ctx.set_artifact_review(draft["artifact_id"], "passed", review_mode="semantic")
    FlashcardService(ctx).activate_deck(draft["artifact_id"])
    request["expected_map_revision"] = LearningMapService(ctx).get_map()["revision"]

    with pytest.raises(CompilationStop) as caught:
        plan_compilation(ctx, request)
    assert caught.value.reason_code == "active_core_exists"


def test_only_active_alignment_can_add_bounded_auxiliary_windows(ctx):
    for material_id, title in (
        ("primary-book", "Primary.pdf"),
        ("reference-book", "Reference.pdf"),
    ):
        resource = ctx.put_artifact(
            kind="resource_pack",
            title=title,
            payload={
                "resources": [{"title": title, "purpose": "Source"}],
                "outline": [],
            },
            source_refs=[
                {
                    "origin": "imported",
                    "material_id": material_id,
                    "structure_status": "reliable",
                    "structure_origin": "embedded_pdf_outline",
                    "source_label": title,
                    "pages": 120,
                }
            ],
            review={"mode": "semantic", "status": "passed"},
        )
        ctx.set_artifact_status(resource["artifact_id"], "active")
    alignment = ctx.put_artifact(
        kind="material_alignment",
        title="Python aligned sources",
        payload={
            "schema_version": 1,
            "batch_id": "batch-python",
            "materials": [
                {
                    "material_id": "primary-book",
                    "title": "Primary.pdf",
                    "source_ref": "read:primary",
                    "structure": [
                        {
                            "section_id": "section-1",
                            "title": "Variables",
                            "locator": "p. 1",
                        },
                        {
                            "section_id": "section-2",
                            "title": "Functions",
                            "locator": "p. 80",
                        },
                    ],
                },
                {
                    "material_id": "reference-book",
                    "title": "Reference.pdf",
                    "source_ref": "read:reference",
                    "structure": [],
                },
            ],
            "course_groups": [
                {
                    "group_id": "python",
                    "proposed_title": "Python",
                    "rationale": "The reference explains the same concepts.",
                    "material_ids": ["primary-book", "reference-book"],
                    "skeleton": {
                        "material_id": "primary-book",
                        "reason": "Primary has the adopted outline.",
                        "role": "explanation",
                        "role_reason": "Primary teaching source.",
                    },
                    "attachments": [
                        {
                            "material_id": "reference-book",
                            "role": "reference",
                            "role_reason": "Adds a second explanation.",
                            "mappings": [
                                {
                                    "source_locator": "p. 50",
                                    "target_section_id": "section-1",
                                    "reason": "Covers variable binding.",
                                }
                            ],
                            "unaligned": [],
                        }
                    ],
                }
            ],
            "ungrouped": [],
        },
        review={"mode": "semantic", "status": "passed"},
    )
    ctx.set_artifact_status(alignment["artifact_id"], "active")
    plan = plan_compilation(ctx, _request(ctx))
    calls = []

    def reader(artifact_id, start, end):
        calls.append((artifact_id, start, end))
        return {
            "title": "source",
            "pageStart": start,
            "pageEnd": end,
            "content": f"{artifact_id}:{start}-{end}",
        }

    windows = read_source_windows(plan, reader)

    assert len({artifact_id for artifact_id, _, _ in calls}) == 2
    assert sum(end - start + 1 for _, start, end in calls) == 48
    assert [window["sourceRole"] for window in windows] == [
        "primary",
        "primary",
        "primary",
        "reference",
    ]
