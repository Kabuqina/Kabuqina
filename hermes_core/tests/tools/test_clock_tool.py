"""Tests for get_current_time clock tool."""

import json
import os
from datetime import timedelta

import pytest

import kabuqina_time
from tools.clock_tool import get_current_time_tool


def _reset_tz_cache():
    kabuqina_time.reset_cache()
    os.environ.pop("HERMES_TIMEZONE", None)


class TestGetCurrentTimeTool:
    def setup_method(self):
        _reset_tz_cache()

    def teardown_method(self):
        _reset_tz_cache()

    def test_returns_json_with_timezone(self):
        os.environ["HERMES_TIMEZONE"] = "Australia/Perth"
        kabuqina_time.reset_cache()
        raw = get_current_time_tool()
        data = json.loads(raw)
        assert data["timezone"] == "Australia/Perth"
        assert "formatted" in data
        assert "iso8601" in data
        assert data["weekday"]
        assert data["date"]
        assert data["time_24h"]
        assert isinstance(data["unix"], int)

    def test_perth_offset(self):
        os.environ["HERMES_TIMEZONE"] = "Australia/Perth"
        kabuqina_time.reset_cache()
        data = json.loads(get_current_time_tool())
        from datetime import datetime

        dt = datetime.fromisoformat(data["iso8601"])
        assert dt.utcoffset() == timedelta(hours=8)

    def test_tool_registered(self):
        import tools.clock_tool  # noqa: F401 — registers on import

        from tools.registry import registry

        entry = registry.get_entry("get_current_time")
        assert entry is not None
        assert entry.toolset == "clock"
