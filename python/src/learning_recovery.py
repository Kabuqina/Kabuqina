"""Desktop-owned recovery runner for durable Study/Tutor operations."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
import threading
from typing import Optional

from learning.learning_data_service import CompositeLearningDataService


logger = logging.getLogger(__name__)


def recover_learning_operations_once(root: Path | str | None = None) -> int:
    """Recover only operations whose writer process liveness lock is free."""

    service = CompositeLearningDataService.from_root(root)
    try:
        recovered = service.recover_operations()
        logger.info("learning recovery scan completed recovered=%d", recovered)
        return recovered
    except BaseException as exc:
        logger.warning(
            "learning recovery scan failed reason=%s",
            getattr(exc, "reason_code", type(exc).__name__),
        )
        raise
    finally:
        service.close()


class LearningRecoveryRunner:
    """The desktop child is the sole periodic recovery owner."""

    def __init__(self, *, interval_s: float = 30.0) -> None:
        if interval_s <= 0:
            raise ValueError("interval_s must be positive")
        self._interval_s = float(interval_s)
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def _run(self) -> None:
        while not self._stop.wait(self._interval_s):
            try:
                recover_learning_operations_once()
            except BaseException:
                # The typed, content-free reason is already logged above. Keep
                # the desktop alive and retry without clearing the fence.
                continue

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._thread = threading.Thread(
            target=self._run,
            name="learning-operation-recovery",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)


def _main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path)
    args = parser.parse_args()
    try:
        recover_learning_operations_once(args.root)
    except BaseException:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
