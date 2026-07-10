# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT / "python" / "src"
CORE_DIR = ROOT / "hermes_core"
for path in (SRC_DIR, CORE_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))


@pytest.fixture()
def isolated_cron(tmp_path, monkeypatch):
    import cron.jobs as jobs

    monkeypatch.setattr(jobs, "CRON_DIR", tmp_path / "cron")
    monkeypatch.setattr(jobs, "JOBS_FILE", tmp_path / "cron" / "jobs.json")
    monkeypatch.setattr(jobs, "OUTPUT_DIR", tmp_path / "cron" / "output")
    return jobs


def test_reminder_is_default_off_and_opt_out_removes_job(isolated_cron):
    from study_review_reminder import StudyReviewReminderService

    service = StudyReviewReminderService("desktop:owner-A")
    assert service.get_settings() == {
        "enabled": False,
        "time_of_day": "20:00",
        "job_id": None,
    }

    enabled = service.configure(enabled=True, time_of_day="19:30")
    jobs = isolated_cron.list_jobs(include_disabled=True)
    assert enabled["enabled"] is True
    assert len(jobs) == 1
    assert jobs[0]["mode"] == "notify"
    assert jobs[0]["deliver"] == "desktop"
    assert jobs[0]["schedule"]["expr"] == "30 19 * * *"
    assert jobs[0]["study_review_reminder"]["owner_id"] == "desktop:owner-A"

    updated = service.configure(enabled=True, time_of_day="08:05")
    assert updated["job_id"] == enabled["job_id"]
    assert len(isolated_cron.list_jobs(include_disabled=True)) == 1
    assert isolated_cron.list_jobs(include_disabled=True)[0]["schedule"]["expr"] == "5 8 * * *"

    disabled = service.configure(enabled=False, time_of_day="08:05")
    assert disabled["enabled"] is False
    assert isolated_cron.list_jobs(include_disabled=True) == []


@pytest.mark.parametrize("value", ["", "24:00", "9:00", "12:60", "noon"])
def test_reminder_rejects_invalid_time(isolated_cron, value):
    from study_review_reminder import StudyReviewReminderService

    with pytest.raises(ValueError, match="HH:MM"):
        StudyReviewReminderService("desktop:owner-A").configure(
            enabled=True, time_of_day=value
        )
