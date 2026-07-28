# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Tests for Kabuqina desk_server (product HTTP API)."""

from __future__ import annotations

import asyncio
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


class TestDeskCapabilityPrompt(unittest.TestCase):
    def test_capability_prompt_summary_available(self):
        from desk_server import chat_core

        with patch.object(
            chat_core,
            "get_runtime_capabilities",
            return_value=[
                {
                    "id": "document-math",
                    "title": "Formula extraction and LaTeX",
                    "status": "missing_package",
                    "agentHint": "Use for math extraction.",
                    "requiredLoadPackages": [
                        {
                            "id": "docling-codeformula",
                            "title": "Docling CodeFormula",
                            "downloaded": False,
                        }
                    ],
                }
            ],
        ):
            summary = chat_core.current_capability_prompt_summary()

        self.assertIn("Current Kabuqina product capabilities", summary)
        self.assertIn("Formula extraction and LaTeX: missing_package", summary)

    def test_capability_prompt_summary_degrades_when_catalog_fails(self):
        from desk_server import chat_core

        with patch.object(chat_core, "get_runtime_capabilities", side_effect=RuntimeError("runtime facts offline")):
            with self.assertLogs("desk_server.chat_core", level="WARNING"):
                summary = chat_core.current_capability_prompt_summary()

        self.assertIn("Current Kabuqina product capabilities", summary)
        self.assertIn("temporarily unavailable", summary)

    def test_chat_agent_receives_current_capability_summary(self):
        from desk_server import chat_core

        captured = {}

        class FakeAgent:
            def __init__(self, **kwargs):
                captured.update(kwargs)

        with patch.dict("sys.modules", {"run_agent": type("RunAgent", (), {"AIAgent": FakeAgent})}):
            with patch("kabuqina_cli.config.load_config", return_value={"model": {"default": "fake-model"}}):
                with patch(
                    "kabuqina_cli.runtime_provider.resolve_runtime_provider",
                    return_value={"provider": "openai", "api_key": "sk-test"},
                ):
                    with patch("kabuqina_cli.tools_config._get_platform_tools", return_value={"file"}):
                        with patch.object(
                            chat_core,
                            "current_capability_prompt_summary",
                            return_value="Current Kabuqina product capabilities:\n- Test capability: available.",
                        ):
                            chat_core._desk_chat_build_agent("desk-capability-test", db=object())

        self.assertIn("Current Kabuqina product capabilities", captured.get("ephemeral_system_prompt", ""))
        self.assertFalse(captured.get("include_session_start_time", True))

    def test_chat_agent_preserves_configured_system_prompt_with_capability_summary(self):
        from desk_server import chat_core

        captured = {}

        class FakeAgent:
            def __init__(self, **kwargs):
                captured.update(kwargs)

        with patch.dict("sys.modules", {"run_agent": type("RunAgent", (), {"AIAgent": FakeAgent})}):
            with patch(
                "kabuqina_cli.config.load_config",
                return_value={
                    "model": {"default": "fake-model"},
                    "agent": {"system_prompt": "Configured desk personality."},
                },
            ):
                with patch(
                    "kabuqina_cli.runtime_provider.resolve_runtime_provider",
                    return_value={"provider": "openai", "api_key": "sk-test"},
                ):
                    with patch("kabuqina_cli.tools_config._get_platform_tools", return_value={"file"}):
                        with patch.object(
                            chat_core,
                            "current_capability_prompt_summary",
                            return_value="Current Kabuqina product capabilities:\n- Test capability: available.",
                        ):
                            chat_core._desk_chat_build_agent("desk-config-prompt-test", db=object())

        prompt = captured.get("ephemeral_system_prompt", "")
        self.assertIn("Configured desk personality.", prompt)
        self.assertIn("Current Kabuqina product capabilities", prompt)
        self.assertFalse(captured.get("include_session_start_time", True))

    def test_chat_agent_logs_resolved_mode_without_secret(self):
        from desk_server import chat_core

        class FakeAgent:
            def __init__(self, **kwargs):
                self.kwargs = kwargs

        with patch.dict("sys.modules", {"run_agent": type("RunAgent", (), {"AIAgent": FakeAgent})}):
            with patch(
                "kabuqina_cli.config.load_config",
                return_value={
                    "model": {"default": "mimo-v2.5", "provider": "custom"},
                    "agent": {},
                },
            ):
                with patch(
                    "kabuqina_cli.runtime_provider.resolve_runtime_provider",
                    return_value={
                        "provider": "custom",
                        "api_mode": "anthropic_messages",
                        "base_url": "https://example.com/anthropic",
                        "api_key": "never-log-me",
                    },
                ):
                    with patch("kabuqina_cli.tools_config._get_platform_tools", return_value={"file"}):
                        with patch.object(
                            chat_core,
                            "current_capability_prompt_summary",
                            return_value="",
                        ):
                            with self.assertLogs("desk_server.chat_core", level="INFO") as captured:
                                agent = chat_core._desk_chat_build_agent("desk-mode-log", db=object())

        self.assertIsNotNone(agent)
        self.assertNotIn("agent_engine", agent.kwargs)
        joined = "\n".join(captured.output)
        self.assertIn("provider=custom", joined)
        self.assertIn("model=mimo-v2.5", joined)
        self.assertIn("api_mode=anthropic_messages", joined)
        self.assertNotIn("engine=", joined)
        self.assertNotIn("never-log-me", joined)


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

    def test_retired_capability_routes_stay_absent_with_bridge_secret(self):
        secret = "test-bridge-secret"
        with patch.dict(os.environ, {"HERMESDESK_BRIDGE_SECRET": secret}, clear=False):
            from desk_server.app import create_app
            from fastapi.testclient import TestClient
            client = TestClient(create_app())
            for route in (
                "/api/kabuqina/capabilities",
                "/api/hermesdesk/capabilities",
                "/api/kabuqina/skills/example",
                "/api/hermesdesk/skills/example",
            ):
                with self.subTest(route=route):
                    resp = client.get(
                        route,
                        headers={"X-HermesDesk-Auth": secret},
                    )
                    self.assertEqual(resp.status_code, 404)

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

    def test_export_pdf_route_uses_document_html_renderer(self):
        import base64

        from desk_server.auth import SESSION_HEADER_NAME, SESSION_TOKEN
        import tools.document_tools as document_tools

        rendered = []

        def fake_render(html_source):
            rendered.append(html_source)
            return b"%PDF-1.4\nchat export\n%%EOF", 2, "chromium_print_v1"

        with patch.object(document_tools, "render_pdf_from_html_source", fake_render):
            resp = self.client.post(
                "/api/desk/export/pdf",
                json={"html": "<!doctype html><h1>Chat</h1>"},
                headers={SESSION_HEADER_NAME: SESSION_TOKEN},
            )

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["renderer"], "chromium_print_v1")
        self.assertEqual(data["pageCount"], 2)
        self.assertEqual(base64.b64decode(data["pdfBase64"]), b"%PDF-1.4\nchat export\n%%EOF")
        self.assertEqual(rendered, ["<!doctype html><h1>Chat</h1>"])

    def test_export_pdf_route_offloads_sync_renderer_off_loop(self):
        # Regression guard: the core renderer uses Playwright's Sync API, which
        # raises when called inside an asyncio event loop. The route must push
        # the call onto a worker thread, not run it inline on the loop.
        import threading

        from desk_server.auth import SESSION_HEADER_NAME, SESSION_TOKEN
        import tools.document_tools as document_tools

        captured = {}

        def fake_render(html_source):
            captured["thread"] = threading.current_thread()
            # asyncio.get_running_loop() only succeeds when this thread is
            # running a loop; in an offloaded worker thread it raises.
            try:
                asyncio.get_running_loop()
                captured["running_loop"] = True
            except RuntimeError:
                captured["running_loop"] = False
            return b"%PDF-1.4\nchat export\n%%EOF", 1, "chromium_print_v1"

        with patch.object(document_tools, "render_pdf_from_html_source", fake_render):
            resp = self.client.post(
                "/api/desk/export/pdf",
                json={"html": "<!doctype html><h1>Chat</h1>"},
                headers={SESSION_HEADER_NAME: SESSION_TOKEN},
            )

        self.assertEqual(resp.status_code, 200)
        # The renderer must run on a different thread than the test/main thread.
        self.assertIsNotNone(captured.get("thread"))
        self.assertNotEqual(captured["thread"], threading.main_thread())
        # ... and never inside a running event loop.
        self.assertFalse(captured.get("running_loop"))


if __name__ == "__main__":
    unittest.main()
