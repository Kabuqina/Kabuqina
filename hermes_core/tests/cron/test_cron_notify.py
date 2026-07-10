"""Tests for cron notify mode (fixed-text delivery without LLM)."""

from unittest.mock import patch

import pytest

from cron.jobs import create_job
from cron.scheduler import _job_execution_mode, _run_notify_job, run_job


class TestJobExecutionMode:
    def test_defaults_to_agent(self):
        assert _job_execution_mode({}) == "agent"
        assert _job_execution_mode({"mode": "agent"}) == "agent"

    def test_notify_aliases(self):
        assert _job_execution_mode({"mode": "notify"}) == "notify"
        assert _job_execution_mode({"mode": "static"}) == "notify"
        assert _job_execution_mode({"mode": "message"}) == "notify"


class TestRunNotifyJob:
    def test_returns_body(self):
        job = {"id": "a" * 12, "name": "water", "message": "喝杯水"}
        ok, doc, final, err = _run_notify_job(job)
        assert ok is True
        assert final == "喝杯水"
        assert err is None
        assert "Cron notify" in doc

    def test_prompt_fallback(self):
        job = {"id": "b" * 12, "name": "rest", "prompt": "休息一下"}
        ok, _, final, err = _run_notify_job(job)
        assert ok is True
        assert final == "休息一下"
        assert err is None

    def test_empty_body_fails(self):
        job = {"id": "c" * 12, "name": "empty", "mode": "notify"}
        ok, doc, final, err = _run_notify_job(job)
        assert ok is False
        assert doc == ""
        assert final == ""
        assert "non-empty" in (err or "")

    def test_study_review_reminder_renders_live_count(self):
        job = {
            "id": "r" * 12,
            "name": "study-review",
            "mode": "notify",
            "message": "placeholder",
            "study_review_reminder": {"owner_id": "desktop:test-owner"},
        }
        with patch("cron.scheduler._study_review_due_count", return_value=3):
            ok, _, final, err = _run_notify_job(job)
        assert ok is True
        assert final == "今日有 3 张卡片到期"
        assert err is None

    def test_study_review_reminder_is_silent_when_nothing_is_due(self):
        job = {
            "id": "s" * 12,
            "name": "study-review",
            "mode": "notify",
            "message": "placeholder",
            "study_review_reminder": {"owner_id": "desktop:test-owner"},
        }
        with patch("cron.scheduler._study_review_due_count", return_value=0):
            ok, _, final, err = _run_notify_job(job)
        assert ok is True
        assert final == "[SILENT]"
        assert err is None


class TestRunJobNotifySkipsAgent:
    def test_skips_ai_agent(self, monkeypatch):
        job = {
            "id": "d" * 12,
            "name": "ping",
            "mode": "notify",
            "message": "时间到了",
            "prompt": "时间到了",
        }
        with patch("run_agent.AIAgent") as mock_agent:
            ok, _, final, err = run_job(job)
            mock_agent.assert_not_called()
        assert ok is True
        assert final == "时间到了"
        assert err is None


class TestCreateJobNotify:
    def test_stores_mode_and_message(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        job = create_job(
            prompt="",
            schedule="every 1h",
            name="hydrate",
            mode="notify",
            message="喝水",
            deliver="local",
        )
        assert job["mode"] == "notify"
        assert job["message"] == "喝水"
        assert job["prompt"] == "喝水"

    def test_notify_requires_body(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        with pytest.raises(ValueError, match="non-empty"):
            create_job(prompt="", schedule="every 1h", mode="notify")
