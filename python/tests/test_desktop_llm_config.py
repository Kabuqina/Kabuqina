# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import copy
import logging
import os
import sys
import types
import unittest
from unittest.mock import patch

from overlays import desktop_llm_config


class DesktopLlmConfigApiModeTests(unittest.TestCase):
    def run_install(self, *, initial: dict, env: dict[str, str]) -> dict:
        saved: list[dict] = []
        fake_package = types.ModuleType("kabuqina_cli")
        fake_package.__path__ = []  # type: ignore[attr-defined]
        fake_config = types.ModuleType("kabuqina_cli.config")
        fake_config.load_config = lambda: copy.deepcopy(initial)  # type: ignore[attr-defined]
        fake_config.save_config = lambda value: saved.append(copy.deepcopy(value))  # type: ignore[attr-defined]

        with (
            patch.dict(
                sys.modules,
                {"kabuqina_cli": fake_package, "kabuqina_cli.config": fake_config},
            ),
            patch.dict(os.environ, env, clear=True),
        ):
            desktop_llm_config.install()

        self.assertEqual(len(saved), 1)
        return saved[0]

    def test_explicit_anthropic_mode_is_persisted(self) -> None:
        saved = self.run_install(
            initial={
                "model": {
                    "provider": "custom",
                    "api_mode": "chat_completions",
                    "max_tokens": 8192,
                }
            },
            env={
                "HERMESDESK_PROVIDER": "custom",
                "HERMESDESK_INFERENCE_PROVIDER": "custom",
                "HERMESDESK_MODEL": "mimo-v2.5",
                "HERMESDESK_API_BASE_URL": "https://example.com/anthropic",
                "HERMESDESK_API_MODE": "anthropic_messages",
            },
        )

        self.assertEqual(saved["model"]["api_mode"], "anthropic_messages")
        self.assertEqual(saved["model"]["max_tokens"], 8192)

    def test_explicit_chat_completions_mode_is_persisted(self) -> None:
        saved = self.run_install(
            initial={"model": {"provider": "custom"}},
            env={
                "HERMESDESK_PROVIDER": "custom",
                "HERMESDESK_INFERENCE_PROVIDER": "custom",
                "HERMESDESK_MODEL": "model",
                "HERMESDESK_API_BASE_URL": "https://example.com/v1",
                "HERMESDESK_API_MODE": "chat_completions",
            },
        )

        self.assertEqual(saved["model"]["api_mode"], "chat_completions")

    def test_automatic_removes_stale_explicit_mode(self) -> None:
        saved = self.run_install(
            initial={
                "model": {
                    "provider": "custom",
                    "api_mode": "anthropic_messages",
                }
            },
            env={
                "HERMESDESK_PROVIDER": "custom",
                "HERMESDESK_INFERENCE_PROVIDER": "custom",
                "HERMESDESK_MODEL": "model",
                "HERMESDESK_API_BASE_URL": "https://example.com/v1",
                "HERMESDESK_API_MODE": "",
            },
        )

        self.assertNotIn("api_mode", saved["model"])

    def test_deepseek_seed_honors_explicit_mode(self) -> None:
        saved = self.run_install(
            initial={
                "model": {
                    "provider": "deepseek",
                    "reasoning_config": {"enabled": True, "effort": "high"},
                }
            },
            env={
                "HERMESDESK_PROVIDER": "deepseek",
                "HERMESDESK_MODEL": "deepseek-v4-flash",
                "HERMESDESK_API_BASE_URL": "https://api.deepseek.com/v1",
                "HERMESDESK_API_MODE": "anthropic_messages",
            },
        )

        self.assertEqual(saved["model"]["api_mode"], "anthropic_messages")
        self.assertEqual(saved["model"]["provider"], "deepseek")

    def test_invalid_mode_falls_back_to_automatic_with_warning(self) -> None:
        with self.assertLogs("hermesdesk.model", level=logging.WARNING) as captured:
            saved = self.run_install(
                initial={
                    "model": {
                        "provider": "custom",
                        "api_mode": "anthropic_messages",
                    }
                },
                env={
                    "HERMESDESK_PROVIDER": "custom",
                    "HERMESDESK_INFERENCE_PROVIDER": "custom",
                    "HERMESDESK_MODEL": "model",
                    "HERMESDESK_API_BASE_URL": "https://example.com/v1",
                    "HERMESDESK_API_MODE": "not-a-mode",
                },
            )

        self.assertNotIn("api_mode", saved["model"])
        self.assertIn("using automatic detection", "\n".join(captured.output))


if __name__ == "__main__":
    unittest.main()
