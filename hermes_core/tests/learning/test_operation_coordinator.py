"""Cross-process contracts for the persistent learning operation fence."""

from __future__ import annotations

import multiprocessing
from pathlib import Path
import sqlite3
import threading
import time

import pytest

from learning.operation_coordinator import (
    COORDINATION_SCHEMA_VERSION,
    LearningCoordinationSchemaError,
    LearningOperationConflictError,
    LearningOperationCoordinator,
    LearningOperationInProgressError,
    LearningOperationTimeoutError,
    OperationLease,
)


def _spawn_try_write(db_path: str, owner: str, space: str, output) -> None:
    coordinator = LearningOperationCoordinator(Path(db_path), timeout_s=0.5)
    try:
        with coordinator.begin_write(owner, space):
            output.put(("ok", None))
    except Exception as exc:  # child boundary: return only stable public data
        output.put((type(exc).__name__, getattr(exc, "reason_code", None)))


def _spawn_begin_and_crash(db_path: str, ready) -> None:
    coordinator = LearningOperationCoordinator(Path(db_path))
    lease = coordinator.begin_operation("owner-1", "space-1", "delete")
    ready.put((lease.operation_id, lease.phase))
    # Returning without finish simulates a process crash from the DB's point of
    # view: the fence and journal must remain durable.


def _spawn_hold_live_operation(db_path: str, ready, release) -> None:
    coordinator = LearningOperationCoordinator(Path(db_path))
    lease = coordinator.begin_operation("owner-1", "space-1", "delete")
    ready.put((lease.operation_id, lease.phase))
    release.wait(10)


def _coordinator(tmp_path, *, timeout=0.5):
    return LearningOperationCoordinator(
        tmp_path / "learning_coordination.db", timeout_s=timeout
    )


def test_fresh_database_has_v1_schema_wal_and_secure_delete(tmp_path):
    coordinator = _coordinator(tmp_path)
    # secure_delete is a per-connection safety setting; inspect a coordinator
    # connection rather than an unrelated sqlite3 default connection.
    with coordinator._connect() as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 1
        assert connection.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
        assert connection.execute("PRAGMA secure_delete").fetchone()[0] == 1
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
    assert COORDINATION_SCHEMA_VERSION == 1
    assert "learning_operation_fences" in tables
    assert "learning_operation_journal" in tables


def test_unknown_newer_schema_fails_closed_without_rewriting_version(tmp_path):
    path = tmp_path / "learning_coordination.db"
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA user_version=2")
    with pytest.raises(LearningCoordinationSchemaError):
        LearningOperationCoordinator(path)
    with sqlite3.connect(path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 2


def test_owner_and_exact_space_fence_rules(tmp_path):
    coordinator = _coordinator(tmp_path)
    exact = coordinator.begin_operation("owner-1", "space-1", "delete")
    with pytest.raises(LearningOperationInProgressError):
        coordinator.begin_read("owner-1", "space-1")
    with pytest.raises(LearningOperationInProgressError):
        coordinator.begin_write("owner-1", "")
    with coordinator.begin_write("owner-1", "space-2"):
        pass
    with coordinator.begin_write("owner-2", "space-1"):
        pass
    coordinator.finish_operation(exact)

    owner = coordinator.begin_operation("owner-1", "", "full_import")
    for space in ("", "space-1", "space-2"):
        with pytest.raises(LearningOperationInProgressError):
            coordinator.begin_read("owner-1", space)
    with pytest.raises(LearningOperationInProgressError):
        coordinator.begin_operation("owner-1", "space-3", "delete")
    coordinator.finish_operation(owner)


def test_two_different_space_fences_may_coexist_but_owner_fence_conflicts(tmp_path):
    coordinator = _coordinator(tmp_path)
    first = coordinator.begin_operation("owner-1", "space-1", "delete")
    second = coordinator.begin_operation("owner-1", "space-2", "runtime_restore")
    recovered = coordinator.recover_operations()
    assert {(item.space_id, item.operation) for item in recovered} == {
        ("space-1", "delete"),
        ("space-2", "runtime_restore"),
    }
    with pytest.raises(LearningOperationInProgressError):
        coordinator.begin_operation("owner-1", "", "delete")
    coordinator.finish_operation(first)
    coordinator.finish_operation(second)


def test_matching_opaque_lease_allows_composite_guard_only_for_its_scope(tmp_path):
    coordinator = _coordinator(tmp_path)
    lease = coordinator.begin_operation("owner-1", "space-1", "delete")
    with coordinator.begin_write("owner-1", "space-1", operation_lease=lease):
        pass
    with pytest.raises(LearningOperationConflictError):
        coordinator.begin_write("owner-1", "space-2", operation_lease=lease)
    with pytest.raises(TypeError):
        OperationLease(
            operation_id=lease.operation_id,
            owner_id=lease.owner_id,
            space_id=lease.space_id,
            operation=lease.operation,
            phase=lease.phase,
        )
    coordinator.finish_operation(lease)


def test_advance_is_phase_cas_and_persists_bounded_journal(tmp_path):
    coordinator = _coordinator(tmp_path)
    initial = coordinator.begin_operation(
        "owner-1", "space-1", "delete", bundle_sha256="a" * 64
    )
    advanced = coordinator.advance_operation(
        initial,
        "learning_deleted",
        {"artifact_ids": ["a-1"], "fingerprint": "b" * 64},
    )
    assert advanced.phase == "learning_deleted"
    assert advanced.rollback_manifest["artifact_ids"] == ["a-1"]
    with pytest.raises(LearningOperationConflictError) as caught:
        coordinator.advance_operation(initial, "runtime_deleted", {})
    assert caught.value.reason_code == "stale_operation_phase"
    with pytest.raises(LearningOperationConflictError):
        coordinator.finish_operation(initial)
    coordinator.finish_operation(advanced)
    assert coordinator.recover_operations() == ()


def test_spawned_process_obeys_fence(tmp_path):
    coordinator = _coordinator(tmp_path)
    lease = coordinator.begin_operation("owner-1", "space-1", "delete")
    context = multiprocessing.get_context("spawn")
    output = context.Queue()
    process = context.Process(
        target=_spawn_try_write,
        args=(str(coordinator.db_path), "owner-1", "space-1", output),
    )
    process.start()
    process.join(10)
    assert process.exitcode == 0
    assert output.get(timeout=2) == (
        "LearningOperationInProgressError",
        "learning_operation_in_progress",
    )
    coordinator.finish_operation(lease)


def test_spawned_process_crash_leaves_recoverable_fence_and_journal(tmp_path):
    path = tmp_path / "learning_coordination.db"
    context = multiprocessing.get_context("spawn")
    ready = context.Queue()
    process = context.Process(target=_spawn_begin_and_crash, args=(str(path), ready))
    process.start()
    operation_id, phase = ready.get(timeout=10)
    process.join(10)
    assert process.exitcode == 0

    recovery_coordinator = LearningOperationCoordinator(path)
    recovered_by_new_process_owner = recovery_coordinator.recover_operations()
    assert len(recovered_by_new_process_owner) == 1
    assert recovered_by_new_process_owner[0].operation_id == operation_id
    assert recovered_by_new_process_owner[0].phase == phase == "fenced"
    recovery_coordinator.finish_operation(recovered_by_new_process_owner[0])


def test_second_process_cannot_recover_operation_while_writer_is_alive(tmp_path):
    path = tmp_path / "learning_coordination.db"
    context = multiprocessing.get_context("spawn")
    ready = context.Queue()
    release = context.Event()
    process = context.Process(
        target=_spawn_hold_live_operation,
        args=(str(path), ready, release),
    )
    process.start()
    operation_id, phase = ready.get(timeout=10)

    recovery_coordinator = LearningOperationCoordinator(path)
    assert recovery_coordinator.recover_operations() == ()
    with pytest.raises(LearningOperationInProgressError):
        recovery_coordinator.begin_write("owner-1", "space-1")

    release.set()
    process.join(10)
    assert process.exitcode == 0
    recovered = recovery_coordinator.recover_operations()
    assert [(lease.operation_id, lease.phase) for lease in recovered] == [
        (operation_id, phase)
    ]
    recovery_coordinator.finish_operation(recovered[0])


def test_operation_waits_for_already_started_guard_without_check_then_write_gap(tmp_path):
    coordinator = _coordinator(tmp_path, timeout=2.0)
    guard_entered = threading.Event()
    release_guard = threading.Event()

    def hold_guard():
        with coordinator.begin_write("owner-1", "space-1"):
            guard_entered.set()
            release_guard.wait(5)

    holder = threading.Thread(target=hold_guard)
    holder.start()
    assert guard_entered.wait(2)
    result = {}

    def install_operation():
        result["lease"] = coordinator.begin_operation("owner-1", "space-1", "delete")

    installer = threading.Thread(target=install_operation)
    installer.start()
    time.sleep(0.1)
    assert installer.is_alive()
    release_guard.set()
    holder.join(5)
    installer.join(5)
    assert "lease" in result
    coordinator.finish_operation(result["lease"])


def test_lock_timeout_is_bounded_and_typed(tmp_path):
    first = _coordinator(tmp_path, timeout=1.0)
    second = _coordinator(tmp_path, timeout=0.1)
    with first.begin_write("owner-1", "space-1"):
        started = time.monotonic()
        with pytest.raises(LearningOperationTimeoutError) as caught:
            second.begin_read("owner-2", "space-2")
        elapsed = time.monotonic() - started
    assert caught.value.reason_code == "learning_operation_timeout"
    assert elapsed < 1.0
