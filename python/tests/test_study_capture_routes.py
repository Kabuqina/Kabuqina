# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Tests for trusted STUDY kq-kp flashcard capture routes."""

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


def test_flashcards_list_empty_when_no_space_exists(client):
    resp = client.get("/api/desk/study/flashcards")

    assert resp.status_code == 422


def test_flashcard_capture_auto_creates_space_and_lists_card(client):
    resp = client.post(
        "/api/desk/study/flashcards/capture",
        json={
            "front": "Bayes theorem",
            "back": "Posterior = prior x likelihood / evidence.",
            "hint": "",
            "tags": ["知识点"],
            "source": {
                "origin": "kq-kp",
                "session_id": "session-1",
                "source_label": "lesson 2",
                "confidence": "confirmed",
                "gist": "Posterior formula",
                "ignored": "nope",
            },
        },
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["duplicate"] is False
    assert data["artifact_id"]
    assert data["item_id"] == f"{data['artifact_id']}-0000"

    space_id = client.get("/api/desk/study/spaces").json()["currentSpaceId"]
    cards_resp = client.get(f"/api/desk/study/flashcards?space_id={space_id}")
    assert cards_resp.status_code == 200
    cards = cards_resp.json()["cards"]
    assert len(cards) == 1
    assert cards[0]["item_id"] == data["item_id"]
    assert cards[0]["front"] == "Bayes theorem"
    assert cards[0]["back"] == "Posterior = prior x likelihood / evidence."


def test_flashcard_capture_is_idempotent_by_front(client):
    first = client.post(
        "/api/desk/study/flashcards/capture",
        json={"front": " Bayes ", "back": "A"},
    ).json()
    second_resp = client.post(
        "/api/desk/study/flashcards/capture",
        json={"front": "bayes", "back": "B"},
    )

    assert second_resp.status_code == 200
    assert second_resp.json() == {"duplicate": True, "item_id": first["item_id"]}
    space_id = client.get("/api/desk/study/spaces").json()["currentSpaceId"]
    assert len(client.get(f"/api/desk/study/flashcards?space_id={space_id}").json()["cards"]) == 1


@pytest.mark.parametrize("payload", [{"front": "", "back": "A"}, {"front": "Q", "back": ""}])
def test_flashcard_capture_missing_front_or_back_returns_400(client, payload):
    resp = client.post("/api/desk/study/flashcards/capture", json=payload)

    assert resp.status_code == 400
