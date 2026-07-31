"""Output Writer — the non-file half of the Writer family (design §7).

The File Writer keeps producing PPTX/PDF/HTML/DOCX. The Output Writer produces
durable, structured learning artifacts:

1. Validate the ``LearningOutputEnvelope`` + per-kind payload (Task 1 contract).
2. Inject owner from the runtime context (Task 2); reject model-supplied owner.
3. Persist to ``learning.db`` as ``draft`` with an artifact id + version.
4. Emit a ``learning.output.created`` signal so the UI/Gateway can refresh
   without blocking the agent turn.

Trusted lifecycle transitions (activate/reject/archive) and *real user
activities* (answers, scores, reviews) route through here too — a user activity
is written straight to ``learning_activities`` and is never disguised as an AI
artifact. No LLM calls happen in this module.

M1 note: the create signal is delivered via an in-process callback. The
non-blocking desktop event bridge is M2 — this module stays engine-decoupled.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Callable, Dict, List, Optional

from learning.learning_context import LearningExecutionContext

# Signal name — the only source of this string (design §10.2).
SIGNAL_OUTPUT_CREATED = "learning.output.created"

CreatedCallback = Callable[[Dict[str, Any]], None]

_active_created_callback: ContextVar[Optional[CreatedCallback]] = ContextVar(
    "active_learning_created_callback", default=None
)


@contextmanager
def learning_created_callback_scope(
    callback: Optional[CreatedCallback],
):
    """Bind a non-blocking ``learning.output.created`` callback for this scope."""
    token = _active_created_callback.set(callback)
    try:
        yield
    finally:
        _active_created_callback.reset(token)


class OutputWriter:
    """Persist AI-authored learning artifacts and fan out create signals.

    ``on_created`` is an in-process callback invoked once per successful
    artifact write. It is best-effort — a raising callback must not corrupt a
    committed write, so exceptions are swallowed after the artifact is stored.
    """

    def __init__(
        self,
        context: LearningExecutionContext,
        on_created: Optional[CreatedCallback] = None,
    ):
        self._ctx = context
        self._on_created = on_created if on_created is not None else _active_created_callback.get()

    # ── AI artifact creation ───────────────────────────────────────────── #

    def write_artifact(
        self,
        *,
        kind: str,
        title: str,
        payload: Dict[str, Any],
        source_refs: Optional[List[Any]] = None,
        review: Optional[Dict[str, str]] = None,
        **ignored: Any,
    ) -> Dict[str, Any]:
        """Validate + persist AI content as ``draft``; emit the create signal.

        ``**ignored`` absorbs any model-supplied ``owner_id``/``space_id``. The
        review *status* is always forced to ``pending``: a model tool cannot ship
        its own content as already-reviewed (a requested review *mode* is kept).
        Raises on any contract violation *before* anything is persisted or
        signalled.
        """
        res = self._ctx.put_artifact(
            kind=kind,
            title=title,
            payload=payload,
            source_refs=source_refs,
            review=_pending_review(review),
        )
        space_id = self._ctx.current_space()
        self._emit_created(
            {
                "event": SIGNAL_OUTPUT_CREATED,
                "owner_id": self._ctx.owner_id,
                "space_id": space_id,
                "artifact_id": res["artifact_id"],
                "kind": kind,
                "version": res["version"],
                "status": "draft",
            }
        )
        return res

    def transition_artifact(self, artifact_id: str, new_status: str) -> None:
        """Trusted lifecycle transition (activate/reject/archive/delete).

        Never exposed as a model tool. Delegates to the context, which enforces
        the contract's allowed transitions and owner/space scoping.
        """
        self._ctx.set_artifact_status(artifact_id, new_status)

    # ── real user activity (not an AI artifact) ────────────────────────── #

    def record_activity(
        self,
        *,
        activity_type: str,
        artifact_id: Optional[str] = None,
        item_id: Optional[str] = None,
        detail: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Record a genuine user action directly in ``learning_activities``.

        Not an AI artifact: no draft, no envelope validation, no create signal.
        """
        return self._ctx.record_activity(
            activity_type=activity_type,
            artifact_id=artifact_id,
            item_id=item_id,
            detail=detail,
        )

    # ── internals ──────────────────────────────────────────────────────── #

    def _emit_created(self, signal: Dict[str, Any]) -> None:
        if self._on_created is None:
            return
        try:
            self._on_created(signal)
        except Exception:
            # Best-effort delivery: the artifact is already committed.
            pass


def _pending_review(review: Optional[Dict[str, str]]) -> Optional[Dict[str, str]]:
    """Force a fresh AI draft to ``status='pending'``, preserving a requested mode.

    Returns ``None`` when no review was supplied so the contract fills the
    per-kind default mode with a pending status.
    """
    if not review:
        return None
    forced: Dict[str, str] = {"status": "pending"}
    if "mode" in review:
        forced["mode"] = review["mode"]
    return forced
