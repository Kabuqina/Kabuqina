"""Subprocess driver for test_learning_recovery.py (not production code)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import time

import test_learning_recovery as tests


class _ReadyFile:
    def __init__(self, path: Path) -> None:
        self.path = path

    def send(self, value) -> None:
        self.path.write_text(json.dumps(value), encoding="utf-8")

    def put(self, value) -> None:
        self.send(value)

    def close(self) -> None:
        return None


class _ReleaseFile:
    def __init__(self, path: Path) -> None:
        self.path = path

    def wait(self, timeout: float) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.path.exists():
                return True
            time.sleep(0.02)
        return False


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=("delete", "import", "restore", "live"))
    parser.add_argument("root")
    parser.add_argument("phase")
    parser.add_argument("ready")
    parser.add_argument("--release")
    parser.add_argument("--bundle")
    args = parser.parse_args()
    ready = _ReadyFile(Path(args.ready))
    if args.operation == "delete":
        tests._crash_delete_at_phase(args.root, args.phase, ready)
    if args.operation == "import":
        bundle = json.loads(Path(args.bundle).read_text(encoding="utf-8"))
        tests._crash_import_at_phase(args.root, bundle, args.phase, ready)
    if args.operation == "restore":
        tests._crash_restore_at_phase(args.root, args.phase, ready)
    tests._hold_live_operation(
        args.root,
        ready,
        _ReleaseFile(Path(args.release)),
    )


if __name__ == "__main__":
    main()
