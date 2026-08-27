# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import hashlib
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image


_ROOT = Path(__file__).resolve().parents[2]
for candidate in (_ROOT / "hermes_core", _ROOT / "python" / "src"):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))


def _transcription(capture_id: str, purpose: str, *, question_match: str = "same"):
    return {
        "schema_version": 1,
        "capture_id": capture_id,
        "purpose": purpose,
        "question_text": "Solve x + 1 = 3",
        "student_work": "x = 3 - 1",
        "lines": [
            {
                "line_no": 1,
                "text": "x = 3 - 1",
                "region": {"x": 0.1, "y": 0.2, "width": 0.7, "height": 0.1},
                "annotations": [],
            }
        ],
        "unreadable_regions": [],
        "confidence_band": "high",
        "question_match": question_match,
        "provider": "untrusted",
        "model": "untrusted",
    }


class FakeVisionPort:
    provider = "fake-provider"
    model = "fake-model-v1"

    def __init__(self, *, malformed: bool = False, question_match: str = "same"):
        self.calls = 0
        self.malformed = malformed
        self.question_match = question_match

    async def transcribe(self, _path, *, capture_id, purpose, question_context=""):
        self.calls += 1
        if self.malformed:
            return {"analysis": "free text is forbidden"}
        return _transcription(
            capture_id, purpose, question_match=self.question_match
        )


class FakeReasoningPort:
    def __init__(self):
        self.calls = 0

    async def generate(self, *, kind, mode="", **_kwargs):
        self.calls += 1
        if kind == "review":
            return {
                "deviation_start": "x = 3",
                "basis": "1 was not subtracted from both sides",
                "uncertain_items": [],
            }
        if mode == "full_answer":
            return {
                "mode": "full_answer",
                "answer": "x = 2",
                "knowledge_points": ["inverse operations"],
                "skipped_items": [],
            }
        return {"mode": "next_step", "hint": "Subtract 1 from both sides."}


class StudyCaptureVisionConfigTests(unittest.TestCase):
    def test_independent_vision_factory_requires_and_uses_private_key(self):
        from desk_server.routes.study_capture_routes import _vision_port

        with patch.dict(
            os.environ,
            {
                "KABUQINA_VISION_CONFIGURED": "1",
                "KABUQINA_VISION_PROVIDER": "custom",
                "KABUQINA_VISION_MODEL": "vision-v1",
                "KABUQINA_VISION_API_BASE_URL": "https://vision.example/v1",
                "KABUQINA_VISION_API_KEY": "vision-private",
            },
            clear=False,
        ):
            port = _vision_port()
        self.assertEqual(port.provider, "custom")
        self.assertEqual(port.model, "vision-v1")
        self.assertEqual(port.base_url, "https://vision.example/v1")
        self.assertEqual(port._api_key, "vision-private")


class StudyCapturePipelineTests(unittest.TestCase):
    def setUp(self):
        from desk_server.app import create_app
        from desk_server.auth import SESSION_HEADER_NAME, SESSION_TOKEN
        from fastapi.testclient import TestClient
        from learning.study_capture import StudyReasoningService
        from study_capture_media import StudyCaptureMediaStore

        self._temporary = tempfile.TemporaryDirectory()
        self.data_dir = Path(self._temporary.name)
        self.store = StudyCaptureMediaStore(self.data_dir)
        self.vision = FakeVisionPort()
        self.reasoning = FakeReasoningPort()
        self._patches = [
            patch.dict(
                os.environ,
                {"KABUQINA_HOME": str(self.data_dir / "kabuqina-home")},
            ),
            patch(
                "desk_server.routes.study_capture_routes._media_store",
                return_value=self.store,
            ),
            patch(
                "desk_server.routes.study_capture_routes._vision_port",
                side_effect=lambda: self.vision,
            ),
            patch(
                "desk_server.routes.study_capture_routes._reasoning_service",
                side_effect=lambda: StudyReasoningService(self.reasoning),
            ),
        ]
        for active in self._patches:
            active.start()
        from learning.learning_store import LearningStore
        from learning_owner import desktop_learning_scope

        learning_store = LearningStore()
        try:
            with desktop_learning_scope(learning_store) as context:
                context.create_space(title="Course", space_id="course-1")
        finally:
            learning_store.close()
        self.client = TestClient(create_app())
        self.client.headers.update({SESSION_HEADER_NAME: SESSION_TOKEN})

    def tearDown(self):
        self.client.close()
        for active in reversed(self._patches):
            active.stop()
        self._temporary.cleanup()

    def _stage(self, capture_id="capture-1", *, purpose="stuck"):
        directory = self.store.temp_root / capture_id
        directory.mkdir(parents=True, exist_ok=True)
        image_path = directory / "original.png"
        Image.new("RGB", (100, 80), color=(245, 245, 240)).save(image_path)
        payload = {
            "schema_version": 1,
            "capture_id": capture_id,
            "space_id": "course-1",
            "purpose": purpose,
            "source_kind": "upload",
            "staged_path": str(image_path),
            "mime_type": "image/png",
            "sha256": hashlib.sha256(image_path.read_bytes()).hexdigest(),
            "preview": {"width": 100, "height": 80},
        }
        response = self.client.post("/api/desk/study/captures/stage", json=payload)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def _normalize(self, capture_id="capture-1", expected_revision=1):
        response = self.client.post(
            f"/api/desk/study/captures/{capture_id}/normalize",
            json={
                "schema_version": 1,
                "capture_id": capture_id,
                "expected_revision": expected_revision,
                "crop": {"x": 0.1, "y": 0.1, "width": 0.8, "height": 0.8},
                "rotation": 90,
                "grayscale": False,
                "max_edge": 1280,
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_upload_to_transcription_is_cached_then_wrong_confirmation_manages_media(self):
        staged = self._stage()
        self.assertEqual(staged["status"], "temporary")
        normalized = self._normalize()
        self.assertEqual(normalized["status"], "normalized")
        self.assertEqual(normalized["revision"], 2)
        self.assertEqual(normalized["preview"], {"width": 64, "height": 80})

        first = self.client.post(
            "/api/desk/study/captures/capture-1/transcribe",
            json={"expected_revision": 2, "question_context": "Solve x + 1 = 3"},
        )
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(first.json()["provider"], "fake-provider")
        second = self.client.post(
            "/api/desk/study/captures/capture-1/transcribe",
            json={"expected_revision": 2},
        )
        self.assertEqual(second.json(), first.json())
        self.assertEqual(self.vision.calls, 1)

        hint = self.client.post(
            "/api/desk/study/captures/capture-1/assistance",
            json={"expected_revision": 3, "mode": "next_step"},
        )
        self.assertEqual(hint.status_code, 200, hint.text)
        self.assertEqual(set(hint.json()), {"mode", "hint"})
        review = self.client.post(
            "/api/desk/study/captures/capture-1/review",
            json={"expected_revision": 3},
        )
        self.assertEqual(review.status_code, 200, review.text)
        self.assertEqual(self.vision.calls, 1)

        edited = dict(first.json(), student_work="x = 2")
        drafted = self.client.post(
            "/api/desk/study/captures/capture-1/confirm",
            json={"expected_revision": 3, "transcription": edited},
        )
        self.assertEqual(drafted.status_code, 200, drafted.text)
        self.assertEqual(drafted.json()["status"], "drafted")
        self.assertTrue((self.store.temp_root / "capture-1").exists())

        decision_body = {
            "expected_revision": 4,
            "decision": "wrong",
            "wrongbook": {
                "correct_work": "x = 2",
                "knowledge_points": ["inverse operations"],
                "review": review.json(),
            },
        }
        confirmed = self.client.post(
            "/api/desk/study/captures/capture-1/confirm",
            json=decision_body,
        )
        self.assertEqual(confirmed.status_code, 200, confirmed.text)
        self.assertEqual(confirmed.json()["status"], "confirmed")
        self.assertEqual(confirmed.json()["wrongbook_entry"]["status"], "active")
        self.assertFalse((self.store.temp_root / "capture-1").exists())
        manifest = self.store.managed_root / "capture-1" / "manifest.json"
        self.assertTrue(manifest.is_file())
        self.assertEqual(len(list(manifest.parent.glob("*.jpg"))), 1)

        repeated_confirm = self.client.post(
            "/api/desk/study/captures/capture-1/confirm",
            json=decision_body,
        )
        self.assertEqual(repeated_confirm.status_code, 200, repeated_confirm.text)
        self.assertEqual(repeated_confirm.json(), confirmed.json())
        self.assertEqual(len(list(manifest.parent.glob("*.jpg"))), 1)

        repeated_stage = self._stage("capture-1")
        self.assertEqual(
            repeated_stage,
            {key: value for key, value in confirmed.json().items() if key != "wrongbook_entry"},
        )
        self.assertFalse((self.store.temp_root / "capture-1").exists())

        wrongbook = self.client.get(
            "/api/desk/study/wrongbook", params={"space_id": "course-1"}
        )
        self.assertEqual(wrongbook.status_code, 200, wrongbook.text)
        self.assertEqual(wrongbook.json()["count"], 1)
        evidence = wrongbook.json()["evidence"]
        self.assertEqual(len(evidence), 1)
        self.assertEqual(evidence[0]["activity_type"], "external_wrongbook.confirmed")
        retry = self.client.get(
            "/api/desk/study/practice-source",
            params={"space_id": "course-1", "activity_id": evidence[0]["activity_id"]},
        )
        self.assertEqual(retry.status_code, 200, retry.text)
        self.assertEqual(retry.json()["source"]["source_kind"], "external_wrongbook")

    def test_malformed_vision_fails_closed_and_removes_temporary_capture(self):
        self.vision = FakeVisionPort(malformed=True)
        self._stage("capture-bad")
        self._normalize("capture-bad")
        response = self.client.post(
            "/api/desk/study/captures/capture-bad/transcribe",
            json={"expected_revision": 2},
        )
        self.assertEqual(response.status_code, 422, response.text)
        self.assertEqual(response.json()["detail"]["code"], "vision_contract_invalid")
        self.assertFalse((self.store.temp_root / "capture-bad").exists())

    def test_question_mismatch_remains_explicit_in_transcription(self):
        self.vision = FakeVisionPort(question_match="different")
        self._stage("capture-other")
        self._normalize("capture-other")
        response = self.client.post(
            "/api/desk/study/captures/capture-other/transcribe",
            json={"expected_revision": 2, "question_context": "another question"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["question_match"], "different")
        assistance = self.client.post(
            "/api/desk/study/captures/capture-other/assistance",
            json={"expected_revision": 3, "mode": "next_step"},
        )
        self.assertEqual(assistance.status_code, 409, assistance.text)
        self.assertEqual(
            assistance.json()["detail"]["code"], "capture_question_mismatch"
        )

    def test_stage_rejects_path_outside_capture_directory(self):
        outside = self.data_dir / "outside.png"
        Image.new("RGB", (10, 10)).save(outside)
        response = self.client.post(
            "/api/desk/study/captures/stage",
            json={
                "schema_version": 1,
                "capture_id": "capture-escape",
                "space_id": "course-1",
                "purpose": "review",
                "source_kind": "upload",
                "staged_path": str(outside),
                "mime_type": "image/png",
                "sha256": hashlib.sha256(outside.read_bytes()).hexdigest(),
                "preview": {"width": 10, "height": 10},
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"]["code"], "capture_invalid_image")

        malformed = self.client.post(
            "/api/desk/study/captures/capture-escape/normalize", json=[]
        )
        self.assertEqual(malformed.status_code, 400, malformed.text)
        self.assertEqual(
            malformed.json()["detail"]["code"], "capture_invalid_image"
        )

    def test_correct_decision_does_not_create_managed_media(self):
        self._stage("capture-correct", purpose="review")
        self._normalize("capture-correct")
        self.client.post(
            "/api/desk/study/captures/capture-correct/transcribe",
            json={"expected_revision": 2},
        )
        response = self.client.post(
            "/api/desk/study/captures/capture-correct/confirm",
            json={"expected_revision": 3, "decision": "correct"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["status"], "abandoned")
        self.assertFalse((self.store.managed_root / "capture-correct").exists())


if __name__ == "__main__":
    unittest.main()
