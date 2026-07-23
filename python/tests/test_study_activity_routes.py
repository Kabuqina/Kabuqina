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
from learning.tutor_contract import validate_start_request  # noqa: E402


OWNER = "desktop:activity-route-owner"
SECRET = "activity-route-secret"


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

    def test_start_is_503_and_rejects_public_owner_without_writing(self):
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
        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json()["detail"]["code"], "study_activity_not_ready"
        )

        injected = dict(body, owner_id="desktop:attacker")
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
        service = self._service()
        try:
            self.assertEqual(
                service.runtime_store.list(OWNER, "space-1", "tutor"), []
            )
        finally:
            service.close()

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
        self.assertEqual(
            cancelled.json()["terminal"]["reason_code"], "user_cancelled"
        )

    def test_resume_is_503_and_does_not_advance_imported_fixture(self):
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
        self.assertEqual(response.status_code, 503)
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
