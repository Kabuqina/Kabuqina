# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Regression tests for the M2 flashcard merge over kq-kp capture."""

from __future__ import annotations

import sys
from contextlib import contextmanager
from pathlib import Path

import pytest

_root = Path(__file__).resolve().parent.parent.parent
_hermes = _root / "hermes_core"
_src = _root / "python" / "src"
for p in (_hermes, _src):
    if p.is_dir() and str(p) not in sys.path:
        sys.path.insert(0, str(p))


@pytest.fixture()
def client(tmp_path, monkeypatch):
    from desk_server.app import create_app
    from desk_server.auth import SESSION_HEADER_NAME, SESSION_TOKEN
    from desk_server.routes import study_routes
    from fastapi.testclient import TestClient
    from learning.learning_context import LearningExecutionContext, learning_context_scope
    from learning.learning_store import LearningStore as RealLearningStore

    db_path = tmp_path / "learning.db"

    class TmpLearningStore(RealLearningStore):
        def __init__(self):
            super().__init__(db_path=db_path)

    @contextmanager
    def test_desktop_scope(store, **_kwargs):
        ctx = LearningExecutionContext(store, owner_id="desktop:test")
        with learning_context_scope(ctx):
            yield ctx

    monkeypatch.setattr(study_routes, "LearningStore", TmpLearningStore)
    monkeypatch.setattr(study_routes, "desktop_learning_scope", test_desktop_scope)

    test_client = TestClient(create_app())
    test_client.headers.update({SESSION_HEADER_NAME: SESSION_TOKEN})
    return test_client


def test_legacy_flashcard_migration_skips_existing_capture_fronts(client):
    captured = client.post(
        "/api/desk/study/flashcards/capture",
        json={
            "front": " Bayes theorem ",
            "back": "Posterior = prior x likelihood / evidence.",
            "source": {"origin": "kq-kp"},
        },
    )
    assert captured.status_code == 200
    assert captured.json()["duplicate"] is False

    migrated = client.post(
        "/api/desk/study/migrations/flashcards",
        json={
            "deck": {
                "cards": [
                    {"front": "bayes theorem", "back": "duplicate legacy answer"},
                    {"front": "Gradient", "back": "Direction of steepest increase."},
                ]
            }
        },
    )

    assert migrated.status_code == 200
    assert migrated.json()["migrated"] is True
    assert migrated.json()["cards"] == 1

    space_id = client.get("/api/desk/study/spaces").json()["currentSpaceId"]
    cards = client.get(f"/api/desk/study/flashcards?space_id={space_id}").json()["cards"]
    fronts = [card["front"] for card in cards]
    assert sorted(fronts, key=str.casefold) == ["Bayes theorem", "Gradient"]
    assert sum(1 for front in fronts if front.casefold() == "bayes theorem") == 1
