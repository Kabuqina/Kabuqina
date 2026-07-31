"""Injected trusted reader port for current-course material artifacts.

The learning tool owns the artifact-id/page-window contract. Desktop path
resolution and exact temporary read authority remain in the host integration.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Callable, Dict, Iterator, Optional


MaterialReader = Callable[[str, int, int], Dict[str, Any]]

_active_material_reader: ContextVar[Optional[MaterialReader]] = ContextVar(
    "active_learning_material_reader", default=None
)


@contextmanager
def learning_material_reader_scope(reader: Optional[MaterialReader]) -> Iterator[None]:
    token = _active_material_reader.set(reader)
    try:
        yield
    finally:
        _active_material_reader.reset(token)


def read_learning_material(
    artifact_id: str, *, page_start: int, page_end: int
) -> Dict[str, Any]:
    reader = _active_material_reader.get()
    if reader is None:
        raise LookupError("trusted learning material reader is unavailable")
    return reader(artifact_id, page_start, page_end)


__all__ = [
    "MaterialReader",
    "learning_material_reader_scope",
    "read_learning_material",
]
