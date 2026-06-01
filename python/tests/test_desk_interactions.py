# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Tests for reusable desk agent interaction requests."""

from __future__ import annotations

import sys
import threading
import time
import unittest
from pathlib import Path

_root = Path(__file__).resolve().parent.parent.parent
_src = _root / "python" / "src"
_hermes = _root / "hermes_core"
for p in (_hermes, _src):
    if p.is_dir() and str(p) not in sys.path:
        sys.path.insert(0, str(p))


class TestDeskInteractions(unittest.TestCase):
    def test_request_waits_for_response_and_emits_payload(self):
        from desk_server.interactions import DeskInteractionManager

        manager = DeskInteractionManager(timeout_seconds=2)
        emitted = []
        result_holder = {}

        def ask() -> None:
            result_holder["result"] = manager.request(
                session_id="s1",
                kind="outline_review",
                question="确认 PPT 大纲",
                choices=["通过", "补充要求", "自行编辑"],
                artifact={"type": "ppt_outline", "content": "# Title"},
                emit=emitted.append,
            )

        thread = threading.Thread(target=ask)
        thread.start()

        deadline = time.time() + 1
        while not emitted and time.time() < deadline:
            time.sleep(0.01)

        self.assertEqual(len(emitted), 1)
        payload = emitted[0]
        self.assertEqual(payload["type"], "interaction.request")
        self.assertEqual(payload["session_id"], "s1")
        interaction = payload["interaction"]
        self.assertEqual(interaction["kind"], "outline_review")
        self.assertEqual(interaction["question"], "确认 PPT 大纲")
        self.assertEqual(interaction["choices"], ["通过", "补充要求", "自行编辑"])
        self.assertEqual(interaction["artifact"]["content"], "# Title")

        ok = manager.respond(
            session_id="s1",
            interaction_id=interaction["id"],
            action="edit",
            text="# Edited",
        )

        self.assertTrue(ok)
        thread.join(timeout=1)
        self.assertFalse(thread.is_alive())
        self.assertEqual(result_holder["result"]["action"], "edit")
        self.assertEqual(result_holder["result"]["text"], "# Edited")

    def test_request_times_out_with_structured_result(self):
        from desk_server.interactions import DeskInteractionManager

        manager = DeskInteractionManager(timeout_seconds=0.01)
        result = manager.request(
            session_id="s1",
            kind="text",
            question="补充要求？",
            choices=None,
            artifact=None,
            emit=lambda payload: None,
        )

        self.assertEqual(result["action"], "timeout")
        self.assertIn("timed out", result["text"])

    def test_prepare_active_agent_wires_clarify_to_interaction_events(self):
        from desk_server.chat_core import _desk_prepare_active_agent, _desk_unregister_active
        from desk_server.interactions import interaction_manager

        class Agent:
            max_iterations = 90

        agent = Agent()
        emitted = []
        result_holder = {}

        _desk_prepare_active_agent("s-clarify", agent, progress_event_callback=emitted.append)
        try:
            thread = threading.Thread(
                target=lambda: result_holder.setdefault(
                    "result",
                    agent.clarify_callback("选一个模板", ["课程汇报", "课设答辩"]),
                )
            )
            thread.start()

            deadline = time.time() + 1
            while not emitted and time.time() < deadline:
                time.sleep(0.01)

            self.assertEqual(emitted[0]["type"], "interaction.request")
            interaction = emitted[0]["interaction"]
            self.assertEqual(interaction["kind"], "choice")
            self.assertEqual(interaction["choices"], ["课程汇报", "课设答辩"])

            self.assertTrue(
                interaction_manager.respond(
                    session_id="s-clarify",
                    interaction_id=interaction["id"],
                    action="choose",
                    text="课设答辩",
                )
            )
            thread.join(timeout=1)
            self.assertEqual(result_holder["result"], "课设答辩")
        finally:
            _desk_unregister_active("s-clarify")

    def test_interaction_response_route_rejects_unknown_request(self):
        import os
        from fastapi.testclient import TestClient
        from unittest.mock import patch

        secret = "test-bridge-secret"
        with patch.dict(os.environ, {"HERMESDESK_BRIDGE_SECRET": secret}, clear=False):
            from desk_server.app import create_app

            client = TestClient(create_app())
            resp = client.post(
                "/api/desk/interaction-response",
                json={
                    "session_id": "missing",
                    "interaction_id": "missing",
                    "action": "approve",
                },
                headers={"X-HermesDesk-Auth": secret},
            )

        self.assertEqual(resp.status_code, 404)
        self.assertEqual(resp.json()["error"], "interaction_not_found")


if __name__ == "__main__":
    unittest.main()
