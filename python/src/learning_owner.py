# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Desk-side owner establishment + injection for the STUDY learning spine.

The runtime is the ONLY source of ``owner_id`` (design §8.3):

- **Desktop** uses a stable local id (``desktop:<uuid>``) persisted once under
  the common Hermes root, so it survives restarts.
- **Gateway** derives ``gateway:<platform>:<hashed-user-id>`` from the
  platform's *stable* user id by hashing it — never from a display name /
  nickname, and never leaking the raw id.

Owner is injected into :class:`LearningExecutionContext` here; a request payload
can never override it. ``hermes_core`` is on ``sys.path`` (wired by the desktop
entrypoint at runtime, and by tests).
"""

from __future__ import annotations

import hashlib
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Mapping, Optional

from kabuqina_constants import get_default_kabuqina_root
from learning.learning_context import (
    LearningExecutionContext,
    learning_context_scope,
)
from learning.learning_store import LearningStore

DESKTOP_OWNER_PREFIX = "desktop"
GATEWAY_OWNER_PREFIX = "gateway"
_OWNER_ID_FILENAME = "learning_owner_id"
_GATEWAY_HASH_LEN = 16


def _owner_id_path(root: Optional[Path] = None) -> Path:
    base = Path(root) if root is not None else get_default_kabuqina_root()
    return base / _OWNER_ID_FILENAME


def desktop_owner_id(root: Optional[Path] = None) -> str:
    """Return the stable local desktop owner id, creating it once if absent.

    Persisted under the common Hermes root (or ``root`` when provided, e.g. in
    tests) so it is stable across calls and restarts.
    """
    path = _owner_id_path(root)
    try:
        existing = path.read_text(encoding="utf-8").strip()
        if existing:
            return existing
    except OSError:
        pass
    owner = f"{DESKTOP_OWNER_PREFIX}:{uuid.uuid4().hex}"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(owner, encoding="utf-8")
    return owner


def gateway_owner_id(platform: str, user_id: str) -> str:
    """Derive ``gateway:<platform>:<hashed-user-id>`` from a stable user id.

    Hashes the platform's stable user id (not a nickname/display name), so the
    owner is deterministic, stable, and does not leak the raw id.
    """
    if not isinstance(platform, str) or not platform.strip():
        raise ValueError("platform is required")
    if not isinstance(user_id, str) or not user_id.strip():
        raise ValueError("user_id is required")
    digest = hashlib.sha256(user_id.encode("utf-8")).hexdigest()[:_GATEWAY_HASH_LEN]
    return f"{GATEWAY_OWNER_PREFIX}:{platform.strip().lower()}:{digest}"


def establish_desktop_context(
    store: LearningStore,
    *,
    space_id: Optional[str] = None,
    request: Optional[Mapping[str, Any]] = None,
    root: Optional[Path] = None,
) -> LearningExecutionContext:
    """Build the desk :class:`LearningExecutionContext` for the desktop owner.

    ``request`` is accepted only to make explicit that any ``owner_id`` it
    carries is IGNORED — the owner is always the runtime desktop id.
    """
    _ = request  # deliberately unused: a request can never set the owner.
    owner_id = desktop_owner_id(root=root)
    return LearningExecutionContext(store, owner_id=owner_id, space_id=space_id)


def establish_gateway_context(
    store: LearningStore,
    *,
    platform: str,
    user_id: str,
    space_id: Optional[str] = None,
) -> LearningExecutionContext:
    """Build a :class:`LearningExecutionContext` for a resolved gateway owner."""
    owner_id = gateway_owner_id(platform, user_id)
    return LearningExecutionContext(store, owner_id=owner_id, space_id=space_id)


@contextmanager
def desktop_learning_scope(
    store: LearningStore,
    *,
    space_id: Optional[str] = None,
    request: Optional[Mapping[str, Any]] = None,
    root: Optional[Path] = None,
) -> Iterator[LearningExecutionContext]:
    """Bind the desktop learning context as active for the duration.

    Ties owner establishment to the ContextVar scope the ``learning`` toolset
    reads from, so model tools see the runtime owner and nothing else.
    """
    ctx = establish_desktop_context(
        store, space_id=space_id, request=request, root=root
    )
    with learning_context_scope(ctx):
        yield ctx
