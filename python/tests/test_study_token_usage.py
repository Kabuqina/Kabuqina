# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest

ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT / "python" / "src"
CORE_DIR = ROOT / "hermes_core"
for path in (SRC_DIR, CORE_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from learning.learning_context import LearningExecutionContext  # noqa: E402
from learning.learning_store import LearningStore  # noqa: E402
from learning.tutor_runtime_store import TutorRuntimeStore  # noqa: E402


OWNER = "desktop:token-test-owner"
SECRET = "token-route-secret"


@pytest.fixture()
def token_client(tmp_path):
    from fastapi.testclient import TestClient
    from desk_server.app import create_app

    learning_db = tmp_path / "learning.db"
    with patch.dict(os.environ, {"HERMESDESK_BRIDGE_SECRET": SECRET}, clear=False):
        with patch("learning.learning_store.default_learning_db_path", return_value=learning_db):
            with patch("learning_owner.desktop_owner_id", return_value=OWNER):
                store = LearningStore(db_path=learning_db)
                try:
                    LearningExecutionContext(store, owner_id=OWNER).create_space(
                        title="Algebra", space_id="space-1"
                    )
                finally:
                    store.close()
                yield TestClient(create_app())


def _headers():
    return {"X-HermesDesk-Auth": SECRET}


def test_token_usage_returns_zero_for_new_owner(token_client):
    response = token_client.get(
        "/api/desk/study/token-usage?window=week", headers=_headers()
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["window"] == "week"
    assert payload["totals"]["totalTokens"] == 0
    assert payload["totals"]["incomplete"] is False
    assert payload["courses"] == []


def test_token_usage_groups_models_by_course_without_hiding_null_measurements(token_client):
    rows = [
        {
            "space_id": "space-1",
            "provider_id": "deepseek",
            "model_id": "deepseek-chat",
            "succeeded_attempts": 2,
            "input_measured_attempts": 1,
            "output_measured_attempts": 2,
            "input_tokens": 100,
            "output_tokens": 40,
        },
        {
            "space_id": "space-1",
            "provider_id": "zai",
            "model_id": "glm-5",
            "succeeded_attempts": 1,
            "input_measured_attempts": 1,
            "output_measured_attempts": 1,
            "input_tokens": 20,
            "output_tokens": 10,
        },
    ]
    fixed_now = datetime(2026, 7, 27, 18, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    with patch.object(TutorRuntimeStore, "aggregate_token_usage", return_value=rows):
        with patch("kabuqina_time.now", return_value=fixed_now):
            response = token_client.get(
                "/api/desk/study/token-usage?window=month", headers=_headers()
            )

    assert response.status_code == 200
    payload = response.json()
    assert payload["startsAt"] == "2026-06-30T16:00:00Z"
    assert payload["endsAt"] == "2026-07-27T10:00:00Z"
    assert payload["totals"]["inputTokens"] == 120
    assert payload["totals"]["outputTokens"] == 50
    assert payload["totals"]["totalTokens"] == 170
    assert payload["totals"]["incomplete"] is True
    assert payload["courses"][0]["title"] == "Algebra"
    assert [model["modelId"] for model in payload["courses"][0]["models"]] == [
        "deepseek-chat",
        "glm-5",
    ]


def test_token_usage_rejects_unknown_window(token_client):
    response = token_client.get(
        "/api/desk/study/token-usage?window=year", headers=_headers()
    )
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "study_invalid_request"
