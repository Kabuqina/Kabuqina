"""Profile-scoped state helpers for the Camofox browser backend."""

from __future__ import annotations

import hashlib
from pathlib import Path

from hermes_constants import get_hermes_home


def get_camofox_state_dir() -> Path:
    return get_hermes_home() / "browser_auth" / "camofox"


def get_camofox_identity(task_id: str | None = None) -> dict[str, str]:
    """Return stable profile identity plus a task-scoped session key."""
    state_dir = get_camofox_state_dir()
    profile_seed = str(state_dir.resolve())
    profile_hash = hashlib.sha256(profile_seed.encode("utf-8")).hexdigest()[:16]
    task = str(task_id or "default")
    task_hash = hashlib.sha256(task.encode("utf-8")).hexdigest()[:16]
    return {
        "user_id": f"hermes_{profile_hash}",
        "session_key": f"task_{task_hash}",
    }
