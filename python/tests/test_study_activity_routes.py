"""Desk Tutor lifecycle and BundleV2 route gates (stdlib discovery compatible)."""

from __future__ import annotations

from contextlib import ExitStack
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
for path in (ROOT / "python" / "src", ROOT / "hermes_core"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from learning.checkpoint_store import LearningCheckpointV1  # noqa: E402
from learning.learning_context import LearningExecutionContext  # noqa: E402
from learning.learning_data_service import CompositeLearningDataService  # noqa: E402
from learning.output_writer import OutputWriter  # noqa: E402
from learning.quizzes import QuizService  # noqa: E402
from learning.tutor_contract import validate_start_request  # noqa: E402
from agent.graph_engine.tutor_contracts import (  # noqa: E402
    TutorProviderPlanV1,
    TutorProviderResult,
    new_tutor_state,
)
from agent.graph_engine.tutor_engine import TutorActivityExecutor  # noqa: E402
from agent.graph_engine.tutor_ports import (  # noqa: E402
    TutorProviderBinding,
    TutorProviderUnavailableError,
)


OWNER = "desktop:activity-route-owner"
SECRET = "activity-route-secret"


class _Resolver:
    def __init__(self) -> None:
        self.binding = TutorProviderBinding(
            plan=TutorProviderPlanV1(
                provider_id="custom",
                model_id="model-1",
                api_mode="chat_completions",
                endpoint_identity="https://example.invalid/v1",
            ),
            api_key="test-secret",
        )

    def resolve_current(self):
        return self.binding

    def bind_saved(self, plan):
        if plan.plan_hash != self.binding.plan.plan_hash:
            raise TutorProviderUnavailableError()
        return self.binding


class _UnavailableResolver(_Resolver):
    def resolve_current(self):
        raise TutorProviderUnavailableError()


class _Provider:
    def __init__(self) -> None:
        self.calls = []

    def execute_once(self, reservation, request, *, timeout_s):
        self.calls.append((reservation, request, timeout_s))
        purpose = (
            "Initial explanation" if request.purpose == "explain" else "Remediation"
        )
        return TutorProviderResult(
            markdown=purpose,
            actual_input_tokens=10,
            actual_output_tokens=5,
            actual_latency_ms=20,
        )


class StudyActivityRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        from fastapi.testclient import TestClient
        from desk_server.app import create_app

        self._temp = tempfile.TemporaryDirectory()
        self.root = Path(self._temp.name)
        self.db_path = self.root / "learning.db"
        self._stack = ExitStack()
        self._stack.enter_context(
            patch.dict(
                os.environ,
                {"HERMESDESK_BRIDGE_SECRET": SECRET},
                clear=False,
            )
        )
        self._stack.enter_context(
            patch(
                "learning.learning_store.default_learning_db_path",
                return_value=self.db_path,
            )
        )
        self._stack.enter_context(
            patch("learning_owner.desktop_owner_id", return_value=OWNER)
        )
        self.provider = _Provider()
        self._stack.enter_context(
            patch(
                "desk_server.routes.study_activity_routes._build_tutor_executor",
                side_effect=self._build_executor,
            )
        )
        self.client = TestClient(create_app())

    def tearDown(self) -> None:
        self.client.close()
        self._stack.close()
        self._temp.cleanup()

    @staticmethod
    def headers() -> dict[str, str]:
        return {"X-HermesDesk-Auth": SECRET}

    def _service(self) -> CompositeLearningDataService:
        return CompositeLearningDataService.from_root(self.root)

    def _build_executor(self, runtime_store, learning_store):
        from learning.tutor_practice import TutorPracticeAdapter

        return TutorActivityExecutor(
            runtime_store,
            resolver=_Resolver(),
            provider_factory=lambda _binding: self.provider,
            practice_adapter_factory=lambda key: TutorPracticeAdapter(
                LearningExecutionContext(
                    learning_store,
                    owner_id=key.owner_id,
                    space_id=key.space_id,
                )
            ),
        )

    def _seed(self, *, activity_id: str = "activity-1"):
        service = self._service()
        try:
            ctx = LearningExecutionContext(service.learning_store, OWNER)
            ctx.create_space(title="Algebra", space_id="space-1")
            request = validate_start_request(
                {
                    "schema_version": 1,
                    "space_id": "space-1",
                    "activity_kind": "tutor",
                    "idempotency_key": f"start-{activity_id}",
                    "goal": "Learn quadratics",
                    "input_refs": [],
                },
                owner_id=OWNER,
                activity_id=activity_id,
            )
            service.runtime_store.create(
                request,
                LearningCheckpointV1(
                    request.key,
                    0,
                    "created",
                    {
                        "schema_version": 1,
                        "phase": "start",
                        "goal": request.goal,
                        "input_refs": [],
                    },
                ),
                label="Quadratics",
            )
            return request
        finally:
            service.close()

    def test_start_and_resume_execute_with_host_owner_and_reject_public_owner(self):
        body = {
            "schema_version": 1,
            "space_id": "space-1",
            "activity_kind": "tutor",
            "idempotency_key": "start-1",
            "goal": "Learn quadratics",
            "input_refs": [],
        }
        response = self.client.post(
            "/api/desk/study/activity-runs",
            json=body,
            headers=self.headers(),
        )
        self.assertEqual(response.status_code, 200)
        waiting = response.json()
        self.assertEqual(waiting["status"], "waiting_for_learner")
        self.assertNotIn("owner_id", str(waiting))
        self.assertEqual(len(self.provider.calls), 1)

        response = self.client.post(
            f"/api/desk/study/activity-runs/tutor/{waiting['activity_id']}/resume",
            json={
                "schema_version": 1,
                "space_id": "space-1",
                "expected_revision": waiting["revision"],
                "mode": "answer",
                "interrupt_id": waiting["interrupt"]["interrupt_id"],
                "answer": {"type": "choice", "selected": ["continue"]},
            },
            headers=self.headers(),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "completed")
        self.assertEqual(
            response.json()["terminal"]["completion_basis"],
            "participation_only",
        )
        self.assertEqual(len(self.provider.calls), 1)

        injected = dict(
            body, idempotency_key="start-injected", owner_id="desktop:attacker"
        )
        response = self.client.post(
            "/api/desk/study/activity-runs",
            json=injected,
            headers=self.headers(),
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["detail"]["code"],
            "study_activity_invalid_request",
        )

    def test_deterministic_practice_route_uses_learning_store_truth(self):
        artifact_id, item_id = self._seed_practice()
        response = self.client.post(
            "/api/desk/study/activity-runs",
            json={
                "schema_version": 1,
                "space_id": "space-1",
                "activity_kind": "tutor",
                "idempotency_key": "practice-start-1",
                "goal": "Practice trusted arithmetic",
                "input_refs": [],
                "tutor_mode": "deterministic_practice",
                "practice_ref": {
                    "artifact_id": artifact_id,
                    "item_id": item_id,
                },
            },
            headers=self.headers(),
        )
        self.assertEqual(response.status_code, 200, response.text)
        waiting = response.json()
        self.assertEqual(waiting["interrupt"]["prompt"]["template"], "practice-v1")

        response = self.client.post(
            f"/api/desk/study/activity-runs/tutor/{waiting['activity_id']}/resume",
            json={
                "schema_version": 1,
                "space_id": "space-1",
                "expected_revision": waiting["revision"],
                "mode": "answer",
                "interrupt_id": waiting["interrupt"]["interrupt_id"],
                "answer": {"type": "choice", "selected": ["1"]},
            },
            headers=self.headers(),
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["status"], "completed")
        self.assertEqual(
            response.json()["terminal"]["completion_basis"],
            "deterministic_correct",
        )
        self.assertEqual(len(self.provider.calls), 1)

    def test_unavailable_provider_returns_503_without_creating_run(self):
        def unavailable(runtime_store, _learning_store):
            return TutorActivityExecutor(runtime_store, resolver=_UnavailableResolver())

        with patch(
            "desk_server.routes.study_activity_routes._build_tutor_executor",
            side_effect=unavailable,
        ):
            response = self.client.post(
                "/api/desk/study/activity-runs",
                json={
                    "schema_version": 1,
                    "space_id": "space-1",
                    "activity_kind": "tutor",
                    "idempotency_key": "unavailable-1",
                    "goal": "Learn quadratics",
                    "input_refs": [],
                },
                headers=self.headers(),
            )
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["detail"]["code"], "study_activity_not_ready")
        service = self._service()
        try:
            self.assertEqual(service.runtime_store.list(OWNER, "space-1", "tutor"), [])
        finally:
            service.close()

    def _seed_practice(self):
        service = self._service()
        try:
            ctx = LearningExecutionContext(service.learning_store, OWNER)
            ctx.create_space(title="Algebra", space_id="space-1")
            artifact_id = OutputWriter(ctx).write_artifact(
                kind="quiz",
                title="Trusted quiz",
                payload={
                    "questions": [
                        {
                            "type": "choice",
                            "prompt": "2 + 2 = ?",
                            "options": ["3", "4"],
                            "answer": 1,
                        }
                    ]
                },
            )["artifact_id"]
            quiz = QuizService(ctx)
            quiz.activate_quiz(artifact_id)
            item_id = quiz.list_questions(artifact_id=artifact_id)[0]["item_id"]
            return artifact_id, item_id
        finally:
            service.close()

    def test_route_reconciliation_preserves_live_execution_then_interrupts_abandoned(
        self,
    ):
        from desk_server.routes import study_activity_routes

        execution_id = "texec_live-route"
        service = self._service()
        try:
            request = validate_start_request(
                {
                    "schema_version": 1,
                    "space_id": "space-1",
                    "activity_kind": "tutor",
                    "idempotency_key": "live-route-1",
                    "goal": "Learn quadratics",
                    "input_refs": [],
                },
                owner_id=OWNER,
                activity_id="activity-live",
            )
            plan = _Resolver().binding.plan
            state = new_tutor_state(
                request.key,
                goal=request.goal,
                input_refs=request.input_refs,
                provider_plan=plan,
            )
            service.runtime_store.create(
                request,
                LearningCheckpointV1(request.key, 0, "created", state),
                provider_plan_hash=plan.plan_hash,
            )
            service.runtime_store.claim_execution(
                request.key,
                expected_revision=0,
                execution_id=execution_id,
            )
        finally:
            service.close()

        study_activity_routes._execution_started(execution_id)
        try:
            live = self.client.get(
                "/api/desk/study/activity-runs/tutor/activity-live?space_id=space-1",
                headers=self.headers(),
            )
            self.assertEqual(live.status_code, 200)
            self.assertEqual(live.json()["status"], "running")
        finally:
            study_activity_routes._execution_finished(execution_id)

        abandoned = self.client.get(
            "/api/desk/study/activity-runs/tutor/activity-live?space_id=space-1",
            headers=self.headers(),
        )
        self.assertEqual(abandoned.status_code, 200)
        self.assertEqual(abandoned.json()["status"], "interrupted")
        self.assertEqual(
            abandoned.json()["revision"],
            live.json()["revision"] + 1,
        )

    def test_get_list_cancel_use_persisted_scoped_truth(self):
        self._seed()
        fetched = self.client.get(
            "/api/desk/study/activity-runs/tutor/activity-1?space_id=space-1",
            headers=self.headers(),
        )
        self.assertEqual(fetched.status_code, 200)
        self.assertEqual(fetched.json()["label"], "Quadratics")
        self.assertNotIn("owner_id", str(fetched.json()))
        self.assertNotIn("Learn quadratics", str(fetched.json()))

        listed = self.client.get(
            "/api/desk/study/activity-runs?space_id=space-1&activity_kind=tutor&limit=10",
            headers=self.headers(),
        )
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.json()["count"], 1)

        wrong_kind = self.client.get(
            "/api/desk/study/activity-runs/review/activity-1?space_id=space-1",
            headers=self.headers(),
        )
        self.assertEqual(wrong_kind.status_code, 404)

        cancelled = self.client.post(
            "/api/desk/study/activity-runs/tutor/activity-1/cancel",
            json={
                "schema_version": 1,
                "space_id": "space-1",
                "expected_revision": 0,
            },
            headers=self.headers(),
        )
        self.assertEqual(cancelled.status_code, 200)
        self.assertEqual(cancelled.json()["status"], "cancelled")
        self.assertEqual(cancelled.json()["terminal"]["reason_code"], "user_cancelled")

    def test_recover_unknown_pre_b03_checkpoint_fails_closed_without_claim(self):
        request = self._seed()
        response = self.client.post(
            "/api/desk/study/activity-runs/tutor/activity-1/resume",
            json={
                "schema_version": 1,
                "space_id": "space-1",
                "expected_revision": 0,
                "mode": "recover",
            },
            headers=self.headers(),
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["detail"]["code"], "study_activity_invalid_request"
        )
        service = self._service()
        try:
            self.assertEqual(service.runtime_store.load(request.key).revision, 0)
        finally:
            service.close()

    def test_bundle_v2_delete_import_and_prepare_downgrade_routes(self):
        self._seed()
        exported = self.client.get(
            "/api/desk/study/data/export", headers=self.headers()
        )
        self.assertEqual(exported.status_code, 200)
        bundle = exported.json()["bundle"]
        self.assertEqual(bundle["version"], 2)
        self.assertEqual(len(bundle["tutor_runtime"]["runs"]), 1)

        prepared = self.client.post(
            "/api/desk/study/data/prepare-downgrade",
            json={},
            headers=self.headers(),
        )
        self.assertEqual(prepared.status_code, 200)
        committed = self.client.post(
            "/api/desk/study/data/prepare-downgrade/commit",
            json={"bundle_sha256": prepared.json()["bundle_sha256"]},
            headers=self.headers(),
        )
        self.assertEqual(committed.status_code, 200)

        # Learning rows survive prepare-downgrade, while runtime-only merge
        # restores the Tutor fixture without replacing those rows.
        restored = self.client.post(
            "/api/desk/study/data/import",
            json={"bundle": bundle, "mode": "tutor_runtime_merge"},
            headers=self.headers(),
        )
        self.assertEqual(restored.status_code, 200)
        fetched = self.client.get(
            "/api/desk/study/activity-runs/tutor/activity-1?space_id=space-1",
            headers=self.headers(),
        )
        self.assertEqual(fetched.status_code, 200)


if __name__ == "__main__":
    unittest.main()
