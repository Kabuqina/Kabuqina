from __future__ import annotations

import json
import sys
import types
import pytest

from providers import image_gen_registry
from providers.image_gen_provider import ImageGenProvider


@pytest.fixture(autouse=True)
def _reset_registry():
    sys.modules.setdefault("fal_client", types.SimpleNamespace())
    image_gen_registry._reset_for_tests()
    yield
    image_gen_registry._reset_for_tests()


class _FakeSampleProvider(ImageGenProvider):
    @property
    def name(self) -> str:
        return "sample"

    def generate(self, prompt, aspect_ratio="landscape", **kwargs):
        return {
            "success": True,
            "image": "/tmp/sample-test.png",
            "model": "sample-image-model",
            "prompt": prompt,
            "aspect_ratio": aspect_ratio,
            "provider": "sample",
        }


class TestPluginDispatch:
    def test_dispatch_routes_to_sample_provider(self, monkeypatch, tmp_path):
        from tools import image_generation_tool
        from providers import image_gen_registry as registry_module
        from kabuqina_cli import plugins as plugins_module

        monkeypatch.setenv("KABUQINA_HOME", str(tmp_path))
        (tmp_path / "config.yaml").write_text("image_gen:\n  provider: sample\n")
        image_gen_registry.register_provider(_FakeSampleProvider())

        monkeypatch.setattr(image_generation_tool, "_read_configured_image_provider", lambda: "sample")
        monkeypatch.setattr(plugins_module, "_ensure_plugins_discovered", lambda: None)
        monkeypatch.setattr(registry_module, "get_provider", lambda name: _FakeSampleProvider() if name == "sample" else None)

        dispatched = image_generation_tool._dispatch_to_plugin_provider("draw cat", "square")
        payload = json.loads(dispatched)

        assert payload["success"] is True
        assert payload["provider"] == "sample"
        assert payload["image"] == "/tmp/sample-test.png"
        assert payload["aspect_ratio"] == "square"

    def test_dispatch_reports_missing_registered_provider(self, monkeypatch, tmp_path):
        from tools import image_generation_tool
        from kabuqina_cli import plugins as plugins_module

        monkeypatch.setenv("KABUQINA_HOME", str(tmp_path))
        (tmp_path / "config.yaml").write_text("image_gen:\n  provider: missing-sample\n")

        monkeypatch.setattr(image_generation_tool, "_read_configured_image_provider", lambda: "missing-sample")
        monkeypatch.setattr(plugins_module, "_ensure_plugins_discovered", lambda: None)

        dispatched = image_generation_tool._dispatch_to_plugin_provider("draw cat", "landscape")
        payload = json.loads(dispatched)

        assert payload["success"] is False
        assert payload["error_type"] == "provider_not_registered"
        assert "image_gen.provider='missing-sample'" in payload["error"]

    def test_dispatch_force_refreshes_plugins_when_provider_initially_missing(self, monkeypatch, tmp_path):
        from tools import image_generation_tool
        from kabuqina_cli import plugins as plugins_module
        from providers import image_gen_registry as registry_module

        monkeypatch.setenv("KABUQINA_HOME", str(tmp_path))
        (tmp_path / "config.yaml").write_text("image_gen:\n  provider: sample\n")

        monkeypatch.setattr(image_generation_tool, "_read_configured_image_provider", lambda: "sample")

        calls = []
        provider_state = {"provider": None}

        def fake_ensure_plugins_discovered(force=False):
            calls.append(force)
            if force:
                provider_state["provider"] = _FakeSampleProvider()

        monkeypatch.setattr(plugins_module, "_ensure_plugins_discovered", fake_ensure_plugins_discovered)
        monkeypatch.setattr(registry_module, "get_provider", lambda name: provider_state["provider"])

        dispatched = image_generation_tool._dispatch_to_plugin_provider("draw hammy", "portrait")
        payload = json.loads(dispatched)

        assert calls == [False, True]
        assert payload["success"] is True
        assert payload["provider"] == "sample"
        assert payload["aspect_ratio"] == "portrait"
