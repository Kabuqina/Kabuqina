"""Tests for the models.dev-preferred merge behavior in provider_model_ids
and list_authenticated_providers.

These guard the contract:

  * For providers in ``_MODELS_DEV_PREFERRED`` (deepseek,
    xiaomi, and smaller inference providers), both the CLI model
    picker path (``provider_model_ids``) and the gateway ``/model`` picker
    path (``list_authenticated_providers``) merge fresh models.dev entries
    on top of the curated static list.
  * OpenRouter and Nous Portal are NEVER merged — they keep their curated
    (OpenRouter) or live-Portal (Nous) semantics.
  * If models.dev is unreachable (offline / CI), the curated list is the
    fallback — no crash, no empty list.

Merging is what lets new models appear in ``/model`` without a Hermes release.
"""

import os
from unittest.mock import patch

import pytest

from hermes_cli.models import (
    _MODELS_DEV_PREFERRED,
    _merge_with_models_dev,
    provider_model_ids,
)


class TestMergeHelper:
    def test_merge_empty_mdev_returns_curated(self):
        """When models.dev returns nothing, curated list is preserved verbatim."""
        with patch("agent.models_dev.list_agentic_models", return_value=[]):
            out = _merge_with_models_dev("deepseek", ["deepseek-v4-pro", "deepseek-chat"])
        assert out == ["deepseek-v4-pro", "deepseek-chat"]

    def test_merge_mdev_raises_returns_curated(self):
        """Offline / broken models.dev must not break the catalog path."""
        def boom(_provider):
            raise RuntimeError("network down")

        with patch("agent.models_dev.list_agentic_models", side_effect=boom):
            out = _merge_with_models_dev("deepseek", ["deepseek-v4-pro"])
        assert out == ["deepseek-v4-pro"]

    def test_merge_mdev_first_then_curated_extras(self):
        """models.dev entries come first; curated-only entries are appended."""
        mdev = ["deepseek-v4.1-pro", "deepseek-v4-pro", "deepseek-chat"]
        curated = ["deepseek-chat", "deepseek-reasoner", "deepseek-v4-pro"]
        with patch("agent.models_dev.list_agentic_models", return_value=mdev):
            out = _merge_with_models_dev("deepseek", curated)
        # models.dev entries first (in order), then curated-only entries
        assert out == ["deepseek-v4.1-pro", "deepseek-v4-pro", "deepseek-chat", "deepseek-reasoner"]

    def test_merge_case_insensitive_dedup(self):
        """Dedup is case-insensitive but preserves the first occurrence's casing."""
        mdev = ["MiniMax-M2.7"]
        curated = ["minimax-m2.7", "minimax-m2.5"]
        with patch("agent.models_dev.list_agentic_models", return_value=mdev):
            out = _merge_with_models_dev("minimax", curated)
        # models.dev casing wins since it came first
        assert out == ["MiniMax-M2.7", "minimax-m2.5"]


class TestProviderModelIdsPreferred:
    def test_deepseek_is_preferred(self):
        assert "deepseek" in _MODELS_DEV_PREFERRED

    def test_deepseek_includes_fresh_models_dev_entries(self):
        """provider_model_ids('deepseek') adds models.dev entries on top."""
        mdev = ["deepseek-v4.1-pro", "deepseek-v4-pro", "deepseek-chat"]
        with patch("agent.models_dev.list_agentic_models", return_value=mdev):
            out = provider_model_ids("deepseek")
        assert "deepseek-v4.1-pro" in out
        assert "deepseek-v4-pro" in out
        # Curated entries are still present.
        assert "deepseek-chat" in out

    def test_deepseek_offline_falls_back_to_curated(self):
        """Offline models.dev → curated-only list, no crash."""
        with patch("agent.models_dev.list_agentic_models", return_value=[]):
            out = provider_model_ids("deepseek")
        assert "deepseek-v4-pro" in out
        assert "deepseek-chat" in out

class TestOpenRouterAndNousUnchanged:
    """Per Teknium: openrouter and nous are NEVER merged with models.dev."""

    def test_openrouter_not_in_preferred_set(self):
        assert "openrouter" not in _MODELS_DEV_PREFERRED

    def test_nous_not_in_preferred_set(self):
        assert "nous" not in _MODELS_DEV_PREFERRED

    def test_openrouter_does_not_call_merge(self):
        """openrouter takes its own live path — merge helper must NOT run."""
        with patch(
            "hermes_cli.models._merge_with_models_dev",
            side_effect=AssertionError("merge should not be called for openrouter"),
        ):
            # Even if model_ids() fails for some other reason, we just care
            # that the merge path isn't invoked.
            try:
                provider_model_ids("openrouter")
            except AssertionError:
                raise
            except Exception:
                pass  # model_ids() may fail in the hermetic test env — that's fine.
