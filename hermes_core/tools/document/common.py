# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Shared leaf value-coercion helpers for the document tools (split from document_tools.py)."""

from typing import Any, Dict, List


def _text(value: Any, default: str = "") -> str:
    text = str(value if value is not None else default).strip()
    return text or default


def _list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _string_list(value: Any, *, limit: int = 8) -> List[str]:
    return [_text(item) for item in _list(value) if _text(item)][:limit]


def _dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}
