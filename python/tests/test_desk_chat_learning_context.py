# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Desk chat must bind the STUDY learning context for real agent turns."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT / "python" / "src"
CORE_DIR = ROOT / "hermes_core"
for p in (SRC_DIR, CORE_DIR):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))


def test_desk_chat_run_binds_learning_context_and_emits_created_event(tmp_path):
    from desk_server.chat_core import _desk_chat_run_in_thread
    from learning.learning_context import require_active_learning_context
    from learning.output_writer import OutputWriter

    class FakeAgent:
        max_iterations = 3

        def run_conversation(self, **_kwargs):
            ctx = require_active_learning_context()
            ctx.create_space(title="Algebra", space_id="s1")
            OutputWriter(ctx).write_artifact(
                kind="flashcard_deck",
                title="Deck",
                payload={"cards": [{"front": "q", "back": "a"}]},
            )
            return {"final_response": "created"}

    events = []
    with patch("learning.learning_store.default_learning_db_path", return_value=tmp_path / "learning.db"):
        with patch("learning_owner.desktop_owner_id", return_value="desktop:test-owner"):
            payload = _desk_chat_run_in_thread(
                FakeAgent(),
                "make cards",
                [],
                "study-session",
                progress_event_callback=events.append,
            )

    assert payload["result"]["final_response"] == "created"
    created = [event for event in events if event.get("type") == "learning.output.created"]
    assert len(created) == 1
    assert created[0]["kind"] == "flashcard_deck"
    assert created[0]["status"] == "draft"
