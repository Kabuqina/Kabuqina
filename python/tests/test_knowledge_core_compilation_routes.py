# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Desktop contracts for the S3I knowledge-core compilation runtime."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[2]
for path in (ROOT / "python" / "src", ROOT / "hermes_core"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from desk_server.knowledge_core_compile_runner import (  # noqa: E402
    KnowledgeCoreCompileRunner,
    _model_compile,
)
from learning.learning_context import LearningExecutionContext  # noqa: E402
from learning.knowledge_core_compilation_store import (  # noqa: E402
    KnowledgeCoreCompilationStore,
)
from learning.learning_map import LearningMapService  # noqa: E402
from learning.learning_plans import LearningPlanService  # noqa: E402
from learning.learning_store import LearningStore  # noqa: E402
from learning.output_writer import OutputWriter  # noqa: E402


OWNER = "desktop:compiler-route-owner"
SECRET = "compiler-route-secret"


def _seed_course(
    db_path: Path, *, locator: str = "p. 1"
) -> tuple[int, str]:
    store = LearningStore(db_path)
    try:
        context = LearningExecutionContext(store, OWNER)
        context.create_space(title="Python", space_id="course-python")
        resource = context.put_artifact(
            kind="resource_pack",
            title="Python.pdf",
            payload={
                "resources": [
                    {"title": "Python.pdf", "purpose": "Primary source"}
                ],
                "outline": [
                    {
                        "id": "variables",
                        "title": "Variables",
                        "locator": locator,
                    },
                    {
                        "id": "functions",
                        "title": "Functions",
                        "locator": "p. 4",
                    },
                    {
                        "id": "classes",
                        "title": "Classes",
                        "locator": "p. 8",
                    },
                ],
            },
            source_refs=[
                {
                    "origin": "imported",
                    "structure_status": "reliable",
                    "structure_origin": "embedded_pdf_outline",
                    "source_label": "Python.pdf",
                    "pages": 20,
                }
            ],
            review={"mode": "semantic", "status": "passed"},
        )
        context.set_artifact_status(resource["artifact_id"], "active")
        return LearningMapService(context).get_map()["revision"], resource[
            "artifact_id"
        ]
    finally:
        store.close()


def _request(revision: int, *, key: str = "compile-variables") -> dict:
    return {
        "spaceId": "course-python",
        "outlineNodeId": "variables",
        "trigger": "start_learning",
        "expectedMapRevision": revision,
        "idempotencyKey": key,
    }


def _model(_plan, windows, _repair_error):
    return {
        "candidates": [
            {
                "title": "变量绑定",
                "keyStatement": "变量把名称绑定到对象。",
                "sourceWindowIds": [windows[0]["id"]],
                "sourceExcerptFingerprints": [
                    windows[0]["contentFingerprint"]
                ],
                "conceptKey": "variable-binding",
                "order": 0,
            }
        ]
    }


def _wait_for(runner, run_id: str, statuses: set[str]) -> dict:
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        run = runner.get("course-python", run_id)
        if run and run["status"] in statuses:
            return run
        time.sleep(0.02)
    raise AssertionError(f"run {run_id} did not reach {statuses}")


def test_production_model_turn_is_tool_free_history_free_and_sessionless():
    captured = {}

    class FakeAgent:
        def __init__(self):
            self.tools = ["unsafe"]
            self.valid_tool_names = {"unsafe"}
            self.enabled_toolsets = ["unsafe"]
            self.ephemeral_system_prompt = "desktop prompt"
            self._cached_system_prompt = None

        def run_conversation(self, **kwargs):
            captured["turn"] = kwargs
            captured["agent"] = self
            return object()

        def close(self):
            captured["closed"] = True

    def build(session_id, db, *, warmup=False):
        captured["build"] = (session_id, db, warmup)
        return FakeAgent()

    with patch(
        "desk_server.chat_core._desk_chat_build_agent", side_effect=build
    ), patch(
        "desk_server.chat_core._desk_extract_reply_text",
        return_value='{"candidates":[]}',
    ):
        assert _model_compile(
            {"outline_node": {}, "outline_path": []}, [], ""
        ) == {"candidates": []}

    assert captured["build"][1:] == (None, True)
    assert captured["turn"]["conversation_history"] == []
    assert captured["agent"].tools == []
    assert captured["agent"].valid_tool_names == set()
    assert captured["agent"].ephemeral_system_prompt is None
    assert "non-dialog knowledge-core compiler" in (
        captured["agent"]._cached_system_prompt
    )
    assert captured["closed"] is True


def test_runner_writes_draft_without_chat_session_or_learning_activity(tmp_path):
    db_path = tmp_path / "learning.db"
    revision, _resource_id = _seed_course(db_path)
    runner = KnowledgeCoreCompileRunner(
        learning_db_path=db_path,
        owner_id=OWNER,
        model_compiler=_model,
        max_workers=1,
    )
    try:
        with patch(
            "desk_server.routes.study_routes._read_material_artifact_window",
            return_value={
                "title": "Python.pdf",
                "pageStart": 1,
                "pageEnd": 3,
                "content": "Variables bind names to objects.",
            },
        ), patch(
            "study_semantic_reviewer.review_artifact_with_model",
            return_value=True,
        ):
            run = runner.enqueue(
                {
                    "space_id": "course-python",
                    "outline_node_id": "variables",
                    "trigger": "start_learning",
                    "expected_map_revision": revision,
                    "idempotency_key": "compile-variables",
                },
                priority=10,
            )
            completed = _wait_for(
                runner, run["run_id"], {"draft_ready", "failed"}
            )
        assert completed["status"] == "draft_ready"
        store = LearningStore(db_path)
        try:
            context = LearningExecutionContext(store, OWNER, "course-python")
            artifact = context.get_artifact(completed["draft_artifact_id"])
            assert artifact["status"] == "draft"
            assert artifact["review"]["status"] == "passed"
            assert context.list_activities() == []
            assert (
                LearningMapService(context).get_map()["knowledgeCores"] == []
            )
        finally:
            store.close()
    finally:
        runner.close()


def test_http_create_list_get_retry_and_cancel_contract(tmp_path):
    from desk_server.app import create_app

    db_path = tmp_path / "learning.db"
    revision, _resource_id = _seed_course(db_path, locator="Chapter 1")
    runner = KnowledgeCoreCompileRunner(
        learning_db_path=db_path,
        owner_id=OWNER,
        model_compiler=_model,
        max_workers=1,
    )
    headers = {"X-HermesDesk-Auth": SECRET}
    try:
        with patch.dict(
            os.environ, {"HERMESDESK_BRIDGE_SECRET": SECRET}, clear=False
        ), patch(
            "learning.learning_store.default_learning_db_path",
            return_value=db_path,
        ), patch(
            "learning_owner.desktop_owner_id", return_value=OWNER
        ), patch(
            "desk_server.routes.knowledge_core_compilation_routes."
            "get_knowledge_core_compile_runner",
            return_value=runner,
        ):
            client = TestClient(create_app())
            created = client.post(
                "/api/desk/study/knowledge-core-compilations",
                json=_request(revision),
                headers=headers,
            )
            assert created.status_code == 202
            body = created.json()
            assert body["status"] == "needs_source"
            assert body["reasonCode"] == "outline_locator_missing"

            listed = client.get(
                "/api/desk/study/knowledge-core-compilations"
                "?space_id=course-python&outline_node_id=variables",
                headers=headers,
            )
            assert listed.status_code == 200
            assert listed.json()["items"][0]["runId"] == body["runId"]

            detail = client.get(
                "/api/desk/study/knowledge-core-compilations/"
                f"{body['runId']}?space_id=course-python",
                headers=headers,
            )
            assert detail.status_code == 200
            assert detail.json()["sourceWindows"] == []

            cancelled = client.post(
                "/api/desk/study/knowledge-core-compilations/"
                f"{body['runId']}/cancel",
                json={"spaceId": "course-python"},
                headers=headers,
            )
            assert cancelled.status_code == 200
            assert cancelled.json()["status"] == "needs_source"

            retried = client.post(
                "/api/desk/study/knowledge-core-compilations/"
                f"{body['runId']}/retry",
                json={"spaceId": "course-python"},
                headers=headers,
            )
            assert retried.status_code == 202
            assert retried.json()["status"] == "needs_source"
            assert retried.json()["runId"] != body["runId"]
    finally:
        runner.close()


def test_plan_activation_enqueues_only_current_and_next_learn_items(tmp_path):
    from desk_server.app import create_app

    db_path = tmp_path / "learning.db"
    _seed_course(db_path)
    store = LearningStore(db_path)
    try:
        context = LearningExecutionContext(store, OWNER, "course-python")
        plan_id = OutputWriter(context).write_artifact(
            kind="learning_plan",
            title="Python plan",
            payload={
                "phases": [
                    {
                        "title": "Core",
                        "tasks": [
                            {
                                "title": "Variables",
                                "mode": "learn",
                                "outline_node_id": "variables",
                            },
                            {
                                "title": "Functions",
                                "mode": "learn",
                                "outline_node_id": "functions",
                            },
                            {
                                "title": "Classes",
                                "mode": "learn",
                                "outline_node_id": "classes",
                            },
                            {"title": "Practice", "mode": "practice"},
                        ],
                    }
                ]
            },
        )["artifact_id"]
    finally:
        store.close()

    class CaptureRunner:
        def __init__(self):
            self.requests = []
            self.cancelled_with = None

        def cancel_stale_prefetch(self, space_id, item_ids):
            self.cancelled_with = (space_id, set(item_ids))
            return []

        def enqueue(self, request, *, priority=0):
            self.requests.append((dict(request), priority))
            return {
                "run_id": f"run-{len(self.requests)}",
                "outline_node_id": request["outline_node_id"],
                "status": "queued",
            }

    runner = CaptureRunner()
    headers = {"X-HermesDesk-Auth": SECRET}
    with patch.dict(
        os.environ, {"HERMESDESK_BRIDGE_SECRET": SECRET}, clear=False
    ), patch(
        "learning.learning_store.default_learning_db_path", return_value=db_path
    ), patch(
        "learning_owner.desktop_owner_id", return_value=OWNER
    ), patch(
        "desk_server.knowledge_core_compile_runner."
        "get_knowledge_core_compile_runner",
        return_value=runner,
    ):
        client = TestClient(create_app())
        response = client.post(
            f"/api/desk/study/artifacts/{plan_id}/activate",
            headers=headers,
        )
        progressed = client.post(
            f"/api/desk/study/learning-plans/items/{plan_id}-0000/complete",
            json={"space_id": "course-python", "note": "done"},
            headers=headers,
        )

    assert response.status_code == 200
    assert [request["trigger"] for request, _ in runner.requests[:2]] == [
        "plan_activated",
        "prefetch",
    ]
    assert [priority for _, priority in runner.requests[:2]] == [10, 0]
    assert [
        request["outline_node_id"] for request, _ in runner.requests[:2]
    ] == [
        "variables",
        "functions",
    ]
    assert len(response.json()["compilationRuns"]) == 2
    assert runner.cancelled_with[0] == "course-python"
    assert len(runner.cancelled_with[1]) == 4
    assert progressed.status_code == 200
    assert [
        request["outline_node_id"] for request, _ in runner.requests[2:]
    ] == ["functions", "classes"]
    assert all(
        request["trigger"] == "prefetch"
        for request, _ in runner.requests[2:]
    )


def test_plan_replacement_cancels_only_not_started_stale_prefetch(tmp_path):
    db_path = tmp_path / "learning.db"
    _seed_course(db_path)
    runner = KnowledgeCoreCompileRunner(
        learning_db_path=db_path,
        owner_id=OWNER,
        model_compiler=_model,
        max_workers=1,
    )
    runtime = KnowledgeCoreCompilationStore(runner.runtime_db_path)
    try:
        stale, _ = runtime.create_or_reuse(
            OWNER,
            {
                "space_id": "course-python",
                "outline_node_id": "functions",
                "plan_item_id": "old-plan-0001",
                "trigger": "prefetch",
                "expected_map_revision": 1,
                "idempotency_key": "old-prefetch",
            },
            source_fingerprint="1" * 64,
            compilation_key="2" * 64,
        )
        current, _ = runtime.create_or_reuse(
            OWNER,
            {
                "space_id": "course-python",
                "outline_node_id": "variables",
                "plan_item_id": "new-plan-0000",
                "trigger": "plan_activated",
                "expected_map_revision": 1,
                "idempotency_key": "new-current",
            },
            source_fingerprint="3" * 64,
            compilation_key="4" * 64,
        )
    finally:
        runtime.close()
    try:
        cancelled = runner.cancel_stale_prefetch(
            "course-python", {"new-plan-0000"}
        )
        assert cancelled == [stale["run_id"]]
        assert runner.get("course-python", stale["run_id"])["status"] == (
            "cancelled"
        )
        assert runner.get("course-python", current["run_id"])["status"] == (
            "queued"
        )
    finally:
        runner.close()
