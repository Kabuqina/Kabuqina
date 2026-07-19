from __future__ import annotations

import pytest

from learning.knowledge_graph import KnowledgeGraphService
from learning.learning_context import LearningExecutionContext
from learning.learning_store import LearningStore
from learning.output_writer import OutputWriter


@pytest.fixture()
def graph_env(tmp_path):
    store = LearningStore(db_path=tmp_path / "learning.db")
    ctx = LearningExecutionContext(store, owner_id="desktop:local")
    ctx.create_space(title="Computer Science", space_id="cs")
    try:
        yield ctx
    finally:
        store.close()


def _write_base(ctx, title, concepts):
    return OutputWriter(ctx).write_artifact(
        kind="knowledge_base",
        title=title,
        payload={"course": "Computer Science", "concepts": concepts},
    )["artifact_id"]


def test_graph_projects_only_active_bases_with_cross_module_relations(graph_env):
    foundations = _write_base(
        graph_env,
        "Foundations",
        [
            {"term": "Data structures", "explanation": "Ways to organize data.", "module": "Programming"},
            {
                "term": "Algorithms",
                "explanation": "Finite problem-solving procedures.",
                "module": "Programming",
                "prerequisites": ["Data structures"],
            },
        ],
    )
    ai = _write_base(
        graph_env,
        "Artificial Intelligence",
        [
            {
                "term": "Search",
                "explanation": "Explore a state space.",
                "module": "AI",
                "prerequisites": ["Algorithms"],
                "related": ["Data structures"],
                "content_markdown": "## Search\n\nUse a frontier.",
            }
        ],
    )
    _write_base(
        graph_env,
        "Unreviewed",
        [{"term": "Draft fact", "explanation": "Must stay hidden."}],
    )
    graph_env.set_artifact_status(foundations, "active")
    graph_env.set_artifact_status(ai, "active")

    graph = KnowledgeGraphService(graph_env).build()

    assert [node["label"] for node in graph["nodes"]] == [
        "Data structures",
        "Algorithms",
        "Search",
    ]
    assert [edge["kind"] for edge in graph["edges"]] == [
        "prerequisite",
        "prerequisite",
        "related",
    ]
    assert graph["edges"][1]["source"].endswith(":1")
    assert graph["edges"][1]["target"].endswith(":0")


def test_concept_detail_requires_active_owner_scoped_knowledge(graph_env):
    artifact_id = _write_base(
        graph_env,
        "AI",
        [
            {
                "term": "Search",
                "explanation": "Explore states.",
                "content_markdown": "# Search\n\nExplore states.",
                "source_section": "Chapter 3 / State-space search",
                "source_locator": "ai-notes.pdf, p. 41",
                "review_prompt": "Why does a frontier determine search order?",
                "prerequisites": ["Algorithms"],
            }
        ],
    )
    service = KnowledgeGraphService(graph_env)
    with pytest.raises(KeyError):
        service.get_concept(artifact_id, 0)
    graph_env.set_artifact_status(artifact_id, "active")

    detail = service.get_concept(artifact_id, 0)

    assert detail["term"] == "Search"
    assert detail["content_markdown"].startswith("# Search")
    assert detail["source_section"] == "Chapter 3 / State-space search"
    assert detail["source_locator"] == "ai-notes.pdf, p. 41"
    assert detail["review_prompt"].startswith("Why does a frontier")
    with pytest.raises(KeyError):
        service.get_concept(artifact_id, 9)


def test_legacy_concept_detail_defaults_atomic_review_metadata(graph_env):
    artifact_id = _write_base(
        graph_env,
        "Legacy",
        [{"term": "Array", "explanation": "A contiguous sequence."}],
    )
    graph_env.set_artifact_status(artifact_id, "active")

    detail = KnowledgeGraphService(graph_env).get_concept(artifact_id, 0)

    assert detail["source_section"] == ""
    assert detail["source_locator"] == ""
    assert detail["review_prompt"] == ""
