# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Opt-in STUDY due-card reminder backed by the existing cron scheduler."""

from __future__ import annotations

import re
from typing import Any, Dict, List

from cron.jobs import create_job, list_jobs, remove_job, update_job

REMINDER_KIND = "kabuqina.study.review-reminder.v1"
DEFAULT_REMINDER_TIME = "20:00"
REMINDER_NAME = "STUDY review reminder"


def _normalize_time(value: Any) -> str:
    text = str(value or "").strip()
    match = re.fullmatch(r"([01]\d|2[0-3]):([0-5]\d)", text)
    if not match:
        raise ValueError("time_of_day must use 24-hour HH:MM")
    return text


def _cron_schedule(time_of_day: str) -> str:
    hour, minute = time_of_day.split(":", 1)
    return f"{int(minute)} {int(hour)} * * *"


class StudyReviewReminderService:
    """Create/update/remove the single owner-scoped reminder cron job."""

    def __init__(self, owner_id: str):
        if not isinstance(owner_id, str) or not owner_id.strip():
            raise ValueError("owner_id is required")
        self._owner_id = owner_id.strip()

    def get_settings(self) -> Dict[str, Any]:
        jobs = self._jobs()
        if not jobs:
            return {
                "enabled": False,
                "time_of_day": DEFAULT_REMINDER_TIME,
                "job_id": None,
            }
        job = jobs[0]
        spec = job.get("study_review_reminder") or {}
        return {
            "enabled": bool(job.get("enabled", True))
            and job.get("state") != "paused",
            "time_of_day": str(spec.get("time_of_day") or DEFAULT_REMINDER_TIME),
            "job_id": job["id"],
        }

    def configure(self, *, enabled: bool, time_of_day: str) -> Dict[str, Any]:
        normalized_time = _normalize_time(time_of_day)
        jobs = self._jobs()
        primary = jobs[0] if jobs else None
        for duplicate in jobs[1:]:
            remove_job(duplicate["id"])

        if not enabled:
            if primary:
                remove_job(primary["id"])
            return {
                "enabled": False,
                "time_of_day": normalized_time,
                "job_id": None,
            }

        spec = {
            "kind": REMINDER_KIND,
            "owner_id": self._owner_id,
            "time_of_day": normalized_time,
        }
        schedule = _cron_schedule(normalized_time)
        if primary:
            job = update_job(
                primary["id"],
                {
                    "name": REMINDER_NAME,
                    "mode": "notify",
                    "message": "[SILENT]",
                    "prompt": "[SILENT]",
                    "deliver": "desktop",
                    "schedule": schedule,
                    "enabled": True,
                    "state": "scheduled",
                    "paused_at": None,
                    "paused_reason": None,
                    "study_review_reminder": spec,
                },
            )
        else:
            created = create_job(
                prompt="[SILENT]",
                schedule=schedule,
                name=REMINDER_NAME,
                deliver="desktop",
                mode="notify",
                message="[SILENT]",
            )
            job = update_job(created["id"], {"study_review_reminder": spec})
        if not job:
            raise RuntimeError("failed to persist study review reminder")
        return {
            "enabled": True,
            "time_of_day": normalized_time,
            "job_id": job["id"],
        }

    def _jobs(self) -> List[Dict[str, Any]]:
        return [
            job
            for job in list_jobs(include_disabled=True)
            if isinstance(job.get("study_review_reminder"), dict)
            and job["study_review_reminder"].get("kind") == REMINDER_KIND
            and job["study_review_reminder"].get("owner_id") == self._owner_id
        ]
