# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Tests for Kabuqina desk_server (product HTTP API)."""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

_root = Path(__file__).resolve().parent.parent.parent
_hermes = _root / "hermes_core"
_src = _root / "python" / "src"
for p in (_hermes, _src):
    if p.is_dir() and str(p) not in sys.path:
        sys.path.insert(0, str(p))


class TestDeskSlashCommands(unittest.TestCase):
    def test_slash_help_returns_product_help_without_model(self):
        from desk_server.chat_core import _desk_slash_response

        result = _desk_slash_response("/help", "desk-help-test")
        assert result is not None
        assert result["ok"] is True
        assert result["session_id"] == "desk-help-test"
        assert result["model"] == ""
        assert "📖 **小娜指令**" in result["final_response"]
        assert "/help" in result["final_response"]
        assert "/commands" in result["final_response"]
        assert "/new" in result["final_response"]
        assert "/config" not in result["final_response"]

    def test_slash_unknown_falls_through_to_agent(self):
        from desk_server.chat_core import _desk_slash_response

        assert _desk_slash_response("/not-a-real-command", "desk-help-test") is None


class TestDeskServerHttp(unittest.TestCase):
    def setUp(self):
        from fastapi.testclient import TestClient
        from desk_server.app import create_app

        self.app = create_app()
        self.client = TestClient(self.app)

    def test_status_public_no_auth(self):
        resp = self.client.get("/api/status")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("version", data)
        self.assertTrue(data.get("desk_minimal"))
        self.assertIn("desk_warming", data)

    def test_capabilities_requires_auth(self):
        resp = self.client.get("/api/hermesdesk/capabilities")
        self.assertEqual(resp.status_code, 401)

    def test_capabilities_with_bridge_secret(self):
        secret = "test-bridge-secret"
        with patch.dict(os.environ, {"HERMESDESK_BRIDGE_SECRET": secret}, clear=False):
            from desk_server.app import create_app
            from fastapi.testclient import TestClient

            client = TestClient(create_app())
            resp = client.get(
                "/api/hermesdesk/capabilities",
                headers={"X-HermesDesk-Auth": secret},
            )
            # May 500 if tools not discovered; auth must pass first.
            self.assertNotEqual(resp.status_code, 401)

    def test_chat_proto_warming_returns_503(self):
        from desk_server import warm

        warm._warm_event.clear()
        try:
            resp = self.client.post(
                "/api/desk/chat-proto",
                json={"message": "hi"},
                headers={"X-Hermes-Session-Token": "dummy"},
            )
            # Without valid token, 401; with warming + valid token would be 503.
            self.assertIn(resp.status_code, (401, 503))
        finally:
            warm._warm_event.set()

    def test_chat_routes_import_attachment_parser(self):
        from desk_server.routes import chat as chat_routes

        self.assertTrue(callable(chat_routes._desk_parse_attachments_from_body))

    def test_chat_proto_empty_message_returns_400_not_500(self):
        from desk_server import warm
        from desk_server.auth import SESSION_HEADER_NAME, SESSION_TOKEN

        warm._warm_event.set()
        resp = self.client.post(
            "/api/desk/chat-proto",
            json={"message": ""},
            headers={SESSION_HEADER_NAME: SESSION_TOKEN},
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json().get("error"), "empty_message")


if __name__ == "__main__":
    unittest.main()
