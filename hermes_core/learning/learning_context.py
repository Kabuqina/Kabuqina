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
        self, *, title: str, space_id: Optional[str] = None, make_current: bool = True,
        kind: str = "course",
    ) -> str:
        sid = self._store.create_space(
            self._owner_id, title=title, space_id=space_id,
            make_current=make_current, kind=kind,
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

    def get_scratch_page(self, space_id: str) -> Dict[str, Any]:
        return self._store.get_scratch_page(self._owner_id, space_id)

    def save_scratch_pad(self, space_id: str, pad: str) -> None:
        self._store.save_scratch_pad(self._owner_id, space_id, pad)

    def add_scratch_note(
        self, space_id: str, *, text: str, origin: str, note_id: Optional[str] = None
    ) -> str:
        return self._store.add_scratch_note(
            self._owner_id, space_id, text=text, origin=origin, note_id=note_id
        )

    def file_scratch_note(
        self, space_id: str, note_id: str, target_space_id: str
    ) -> Dict[str, Any]:
        return self._store.file_scratch_note(
            self._owner_id, space_id, note_id, target_space_id
        )

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

    def artifact_summary_page(
        self,
        *,
        kind: Optional[str],
        status: Optional[str],
        limit: int,
        offset: int,
    ) -> Dict[str, Any]:
        return self._store.artifact_summary_page(
            self._owner_id,
            self._require_space(),
            kind=kind,
            status=status,
            limit=limit,
            offset=offset,
        )

    def set_artifact_status(self, artifact_id: str, new_status: str) -> None:
        """Trusted lifecycle transition — not exposed as a model tool."""
        self._store.update_artifact_status(
            self._owner_id, self._require_space(), artifact_id, new_status
        )

    def set_artifact_review(self, artifact_id: str, review_status: str, *, review_mode: Optional[str] = None) -> None:
        self._store.update_artifact_review(
            self._owner_id, self._require_space(), artifact_id, review_status,
            review_mode=review_mode,
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

    def compare_and_update_item_state(
        self,
        item_id: str,
        expected_state: Dict[str, Any],
        state: Dict[str, Any],
    ) -> bool:
        return self._store.compare_and_update_item_state(
            self._owner_id,
            self._require_space(),
            item_id,
            expected_state,
            state,
        )

    def record_activity(
        self,
        *,
        activity_type: str,
        artifact_id: Optional[str] = None,
        item_id: Optional[str] = None,
        detail: Optional[Dict[str, Any]] = None,
        occurred_at: Optional[str] = None,
    ) -> str:
        return self._store.insert_activity(
            self._owner_id,
            self._require_space(),
            activity_type=activity_type,
            artifact_id=artifact_id,
            item_id=item_id,
            detail=detail,
            occurred_at=occurred_at,
        )

    def record_bounded_activity_once(
        self,
        *,
        activity_id: str,
        activity_type: str,
        artifact_id: Optional[str],
        item_id: Optional[str],
        detail: Dict[str, Any],
        max_occurrences: int,
    ) -> Dict[str, Any]:
        return self._store.insert_bounded_activity_once(
            self._owner_id,
            self._require_space(),
            activity_id=activity_id,
            activity_type=activity_type,
            artifact_id=artifact_id,
            item_id=item_id,
            detail=detail,
            max_occurrences=max_occurrences,
        )

    def list_activities(self) -> List[Dict[str, Any]]:
        return self._store.list_activities(self._owner_id, self._require_space())

    def list_activities_between(
        self,
        *,
        activity_type: str,
        created_at_gte: str,
        created_at_lt: str,
    ) -> List[Dict[str, Any]]:
        return self._store.list_activities_between(
            self._owner_id,
            self._require_space(),
            activity_type=activity_type,
            created_at_gte=created_at_gte,
            created_at_lt=created_at_lt,
        )

    def get_study_preferences(self) -> Optional[Dict[str, Any]]:
        return self._store.get_study_preferences(self._owner_id)

    def put_study_preferences(self, preferences: Dict[str, Any]) -> None:
        self._store.put_study_preferences(self._owner_id, preferences)

    def activity_summary_page(self, *, limit: int) -> Dict[str, Any]:
        return self._store.activity_summary_page(
            self._owner_id, self._require_space(), limit=limit
        )

    def quiz_attempt_page(self, *, limit: int) -> Dict[str, Any]:
        return self._store.quiz_attempt_page(
            self._owner_id, self._require_space(), limit=limit
        )

    def quiz_attempt_by_id(self, activity_id: str) -> Optional[Dict[str, Any]]:
        return self._store.quiz_attempt_by_id(
            self._owner_id, self._require_space(), activity_id
        )

    def mark_migration(
        self, migration_key: str, *, detail: Optional[Dict[str, Any]] = None
    ) -> None:
        self._store.mark_migration(self._owner_id, migration_key, detail=detail)

    def is_migrated(self, migration_key: str) -> bool:
        return self._store.is_migrated(self._owner_id, migration_key)

    def export_owner_bundle(self) -> Dict[str, Any]:
        return self._store.export_owner_bundle(self._owner_id)

    def import_owner_bundle(self, bundle: Dict[str, Any]) -> Dict[str, int]:
        return self._store.import_owner_bundle(self._owner_id, bundle)

    def delete_all_learning_data(self) -> Dict[str, int]:
        return self._store.delete_owner_data(self._owner_id)

    def list_migrations(self, *, status: Optional[str] = None) -> List[Dict[str, Any]]:
        return self._store.list_migrations(self._owner_id, status=status)

    def mark_migration_failure(self, migration_key: str, detail: Dict[str, Any]) -> None:
        self._store.mark_migration_failure(self._owner_id, migration_key, detail)


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
