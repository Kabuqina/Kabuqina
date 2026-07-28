"""Owner-scoped Study preferences and import-read policy.

These values are trusted product settings, not model-authored learning artifacts.
They therefore live beside the learning spine while remaining independent from
artifact review/lifecycle state.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from learning.learning_context import LearningExecutionContext


IMPORT_READ_MODES = ("auto", "precise", "math")
DEFAULT_IMPORT_READ_MODE = "auto"
DEFAULT_DAILY_NEW_CARD_LIMIT = 20
DEFAULT_DAILY_REVIEW_CARD_LIMIT = 100
MAX_DAILY_NEW_CARD_LIMIT = 100
MAX_DAILY_REVIEW_CARD_LIMIT = 1_000

DEFAULT_STUDY_PREFERENCES = {
    "import_read_mode": DEFAULT_IMPORT_READ_MODE,
    "daily_new_card_limit": DEFAULT_DAILY_NEW_CARD_LIMIT,
    "daily_review_card_limit": DEFAULT_DAILY_REVIEW_CARD_LIMIT,
}


def _limit(value: Any, label: str, maximum: int) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or not 0 <= value <= maximum
    ):
        raise ValueError(f"{label} must be within 0..{maximum}")
    return value


def normalize_study_preferences(value: Any) -> dict[str, Any]:
    """Validate one complete persisted preference row."""
    if not isinstance(value, Mapping):
        raise ValueError("study preferences must be an object")
    unknown = set(value) - set(DEFAULT_STUDY_PREFERENCES)
    if unknown:
        raise ValueError(f"unknown study preference: {sorted(unknown)[0]}")
    mode = value.get("import_read_mode", DEFAULT_IMPORT_READ_MODE)
    if not isinstance(mode, str) or mode not in IMPORT_READ_MODES:
        raise ValueError(f"import_read_mode must be one of {list(IMPORT_READ_MODES)}")
    return {
        "import_read_mode": mode,
        "daily_new_card_limit": _limit(
            value.get("daily_new_card_limit", DEFAULT_DAILY_NEW_CARD_LIMIT),
            "daily_new_card_limit",
            MAX_DAILY_NEW_CARD_LIMIT,
        ),
        "daily_review_card_limit": _limit(
            value.get("daily_review_card_limit", DEFAULT_DAILY_REVIEW_CARD_LIMIT),
            "daily_review_card_limit",
            MAX_DAILY_REVIEW_CARD_LIMIT,
        ),
    }


def resolve_import_read_mode(
    preferred_mode: str,
    requested_mode: str | None = None,
    *,
    override: bool = False,
) -> dict[str, Any]:
    """Resolve the Study-import default/cap without affecting ordinary Chat reads."""
    preferred = normalize_study_preferences({"import_read_mode": preferred_mode})[
        "import_read_mode"
    ]
    requested = requested_mode if requested_mode is not None else preferred
    if not isinstance(requested, str) or requested not in IMPORT_READ_MODES:
        raise ValueError(f"requested_mode must be one of {list(IMPORT_READ_MODES)}")
    effective = requested
    limited = False
    if (
        not override
        and IMPORT_READ_MODES.index(requested) > IMPORT_READ_MODES.index(preferred)
    ):
        effective = preferred
        limited = True
    return {
        "preferred_mode": preferred,
        "requested_mode": requested,
        "effective_mode": effective,
        "limited": limited,
        "override": bool(override),
    }


class StudyPreferencesService:
    def __init__(self, context: LearningExecutionContext):
        self._ctx = context

    def get(self) -> dict[str, Any]:
        stored = self._ctx.get_study_preferences()
        return normalize_study_preferences(stored or DEFAULT_STUDY_PREFERENCES)

    def update(self, patch: Any) -> dict[str, Any]:
        if not isinstance(patch, Mapping):
            raise ValueError("study preference update must be an object")
        unknown = set(patch) - set(DEFAULT_STUDY_PREFERENCES)
        if unknown:
            raise ValueError(f"unknown study preference: {sorted(unknown)[0]}")
        merged = {**self.get(), **dict(patch)}
        normalized = normalize_study_preferences(merged)
        self._ctx.put_study_preferences(normalized)
        return normalized


__all__ = [
    "DEFAULT_DAILY_NEW_CARD_LIMIT",
    "DEFAULT_DAILY_REVIEW_CARD_LIMIT",
    "DEFAULT_IMPORT_READ_MODE",
    "DEFAULT_STUDY_PREFERENCES",
    "IMPORT_READ_MODES",
    "MAX_DAILY_NEW_CARD_LIMIT",
    "MAX_DAILY_REVIEW_CARD_LIMIT",
    "StudyPreferencesService",
    "normalize_study_preferences",
    "resolve_import_read_mode",
]
