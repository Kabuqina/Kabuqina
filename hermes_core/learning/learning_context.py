"""``LearningExecutionContext`` — the only source of ``owner_id`` for learning.

The runtime resolves a stable ``owner_id`` (desktop local id, or
``gateway:<platform>:<hashed-user-id>``) and injects it here. Model tool calls
never carry ``owner_id``; if untrusted input smuggles one in, the context drops
it. Every space-scoped operation flows through this context so that both
``owner_id`` and the currently selected ``space_id`` constrain every read/write.

This class holds no engine state and imports no engine code.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Dict, Iterator, List, Optional

from learning.learning_store import LearningStore


class LearningExecutionContext:
    """Owner + current-space scope over a :class:`LearningStore`."""

    __slots__ = ("_store", "_owner_id", "_space_id")

    def __init__(
        self,
        store: LearningStore,
        owner_id: str,
        space_id: Optional[str] = None,
    ):
        if not isinstance(owner_id, str) or not owner_id.strip():
            raise ValueError("owner_id must be a non-empty string")
        object.__setattr__(self, "_store", store)
        object.__setattr__(self, "_owner_id", owner_id)
        object.__setattr__(self, "_space_id", space_id)

    # Owner is immutable once injected — no setter, and __slots__ blocks
    # arbitrary attribute assignment.
    def __setattr__(self, name: str, value: Any) -> None:  # noqa: D401
        raise AttributeError("LearningExecutionContext is read-only")

    @property
    def owner_id(self) -> str:
        return self._owner_id

    @property
    def space_id(self) -> Optional[str]:
        return self._space_id

    # ── spaces ─────────────────────────────────────────────────────────── #

    def create_space(
        self, *, title: str, space_id: Optional[str] = None, make_current: bool = True
    ) -> str:
        sid = self._store.create_space(
            self._owner_id, title=title, space_id=space_id, make_current=make_current
        )
        if make_current:
            object.__setattr__(self, "_space_id", sid)
        return sid

    def select_space(self, space_id: str) -> None:
        self._store.set_current_space(self._owner_id, space_id)
        object.__setattr__(self, "_space_id", space_id)

    def list_spaces(self) -> List[Dict[str, Any]]:
        return self._store.list_spaces(self._owner_id)

    def current_space(self) -> Optional[str]:
        return self._space_id or self._store.get_current_space(self._owner_id)

    def _require_space(self) -> str:
        sid = self.current_space()
        if not sid:
            raise ValueError("no learning space selected for this context")
        return sid

    # ── artifacts ──────────────────────────────────────────────────────── #

    def put_artifact(
        self,
        *,
        kind: str,
        title: str,
        payload: Dict[str, Any],
        source_refs: Optional[List[Any]] = None,
        review: Optional[Dict[str, str]] = None,
        **ignored: Any,
    ) -> Dict[str, Any]:
        """Persist a new AI-authored artifact as ``draft`` under this owner/space.

        ``**ignored`` deliberately absorbs any model-supplied ``owner_id`` /
        ``space_id`` — identity comes only from the context.
        """
        space_id = self._require_space()
        envelope = {
            "version": 1,
            "kind": kind,
            "space_id": space_id,
            "title": title,
            "source_refs": source_refs or [],
            "payload": payload,
        }
        if review is not None:
            envelope["review"] = review
        return self._store.insert_artifact(self._owner_id, space_id, envelope)

    def get_artifact(self, artifact_id: str) -> Optional[Dict[str, Any]]:
        return self._store.get_artifact(self._owner_id, self._require_space(), artifact_id)

    def list_artifacts(
        self, *, kind: Optional[str] = None, status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        return self._store.list_artifacts(
            self._owner_id, self._require_space(), kind=kind, status=status
        )

    def set_artifact_status(self, artifact_id: str, new_status: str) -> None:
        """Trusted lifecycle transition — not exposed as a model tool."""
        self._store.update_artifact_status(
            self._owner_id, self._require_space(), artifact_id, new_status
        )

    # ── items ─────────────────────────────────────────────────────────── #

    def upsert_item(
        self,
        *,
        item_id: str,
        item_type: str,
        artifact_id: Optional[str] = None,
        state: Optional[Dict[str, Any]] = None,
    ) -> str:
        return self._store.upsert_item(
            self._owner_id,
            self._require_space(),
            item_id=item_id,
            item_type=item_type,
            artifact_id=artifact_id,
            state=state,
        )

    def list_items(
        self,
        *,
        item_type: Optional[str] = None,
        artifact_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        return self._store.list_items(
            self._owner_id,
            self._require_space(),
            item_type=item_type,
            artifact_id=artifact_id,
        )

    def update_item_state(self, item_id: str, state: Dict[str, Any]) -> None:
        self._store.update_item_state(
            self._owner_id,
            self._require_space(),
            item_id,
            state,
        )

    # ── activities + migrations ────────────────────────────────────────── #

    def record_activity(
        self,
        *,
        activity_type: str,
        artifact_id: Optional[str] = None,
        item_id: Optional[str] = None,
        detail: Optional[Dict[str, Any]] = None,
    ) -> str:
        return self._store.insert_activity(
            self._owner_id,
            self._require_space(),
            activity_type=activity_type,
            artifact_id=artifact_id,
            item_id=item_id,
            detail=detail,
        )

    def list_activities(self) -> List[Dict[str, Any]]:
        return self._store.list_activities(self._owner_id, self._require_space())

    def mark_migration(
        self, migration_key: str, *, detail: Optional[Dict[str, Any]] = None
    ) -> None:
        self._store.mark_migration(self._owner_id, migration_key, detail=detail)

    def is_migrated(self, migration_key: str) -> bool:
        return self._store.is_migrated(self._owner_id, migration_key)


# --------------------------------------------------------------------------- #
# Active-context scope — the runtime injects the resolved context here so that
# model tools read owner/space from it and never from tool arguments. Mirrors
# the goal-runner's ``goal_report_scope`` ContextVar pattern.
# --------------------------------------------------------------------------- #

_active_learning_context: ContextVar[Optional[LearningExecutionContext]] = ContextVar(
    "active_learning_context", default=None
)


@contextmanager
def learning_context_scope(
    context: LearningExecutionContext,
) -> Iterator[LearningExecutionContext]:
    """Bind ``context`` as the active learning context for the duration."""
    token = _active_learning_context.set(context)
    try:
        yield context
    finally:
        _active_learning_context.reset(token)


def active_learning_context() -> Optional[LearningExecutionContext]:
    """The context bound by :func:`learning_context_scope`, or ``None``."""
    return _active_learning_context.get()


def require_active_learning_context() -> LearningExecutionContext:
    """The active learning context, or raise :class:`LookupError`."""
    ctx = _active_learning_context.get()
    if ctx is None:
        raise LookupError("no active learning context")
    return ctx
