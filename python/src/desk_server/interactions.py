"""Reusable agent-to-user interaction bridge for the desk chat surface."""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional


EmitFn = Callable[[Dict[str, Any]], None]


@dataclass
class _PendingInteraction:
    session_id: str
    interaction_id: str
    event: threading.Event = field(default_factory=threading.Event)
    response: Optional[Dict[str, Any]] = None


class DeskInteractionManager:
    """Thread-safe registry for interactions that pause an agent turn."""

    def __init__(self, timeout_seconds: float = 300.0) -> None:
        self.timeout_seconds = timeout_seconds
        self._lock = threading.Lock()
        self._pending: Dict[tuple[str, str], _PendingInteraction] = {}

    def request(
        self,
        *,
        session_id: str,
        kind: str,
        question: str,
        choices: Optional[list[str]],
        artifact: Optional[Dict[str, Any]],
        emit: EmitFn,
    ) -> Dict[str, Any]:
        interaction_id = str(uuid.uuid4())
        pending = _PendingInteraction(session_id=session_id, interaction_id=interaction_id)
        key = (session_id, interaction_id)
        with self._lock:
            self._pending[key] = pending

        payload = {
            "type": "interaction.request",
            "session_id": session_id,
            "interaction": {
                "id": interaction_id,
                "kind": kind,
                "question": question,
                "choices": list(choices or []),
                "artifact": artifact,
                "created_at": time.time(),
            },
        }
        emit(payload)

        try:
            if pending.event.wait(self.timeout_seconds):
                return pending.response or {"action": "cancel", "text": ""}
            return {
                "action": "timeout",
                "text": "The user interaction timed out. Use your best judgement and proceed.",
            }
        finally:
            with self._lock:
                self._pending.pop(key, None)

    def respond(
        self,
        *,
        session_id: str,
        interaction_id: str,
        action: str,
        text: str = "",
        data: Optional[Dict[str, Any]] = None,
    ) -> bool:
        key = (session_id, interaction_id)
        with self._lock:
            pending = self._pending.get(key)
            if pending is None:
                return False
            pending.response = {
                "action": str(action or "").strip() or "submit",
                "text": str(text or ""),
                "data": data or {},
            }
            pending.event.set()
            return True


interaction_manager = DeskInteractionManager()
