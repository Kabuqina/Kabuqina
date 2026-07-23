"""Process-level recovery entrypoint tests for durable learning operations."""

from __future__ import annotations

from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest


ROOT = Path(__file__).resolve().parents[2]
for path in (ROOT / "python", ROOT / "python" / "src", ROOT / "hermes_core"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from learning.checkpoint_store import LearningCheckpointV1  # noqa: E402
from learning.learning_data_service import CompositeLearningDataService  # noqa: E402
from learning.tutor_contract import validate_start_request  # noqa: E402


OWNER = "desktop:recovery-owner"


def _checkpoint(request):
    return LearningCheckpointV1(
        request.key,
        0,
        "created",
        {
            "schema_version": 1,
            "phase": "start",
            "goal": request.goal,
            "input_refs": [],
        },
    )


def _seed(service, *, owner=OWNER):
    service.learning_store.create_space(
        owner, title="Recovery", space_id="space-1", make_current=True
    )
    request = validate_start_request(
        {
            "schema_version": 1,
            "space_id": "space-1",
            "activity_kind": "tutor",
            "idempotency_key": "start-1",
            "goal": "Recover safely",
            "input_refs": [],
        },
        owner_id=owner,
        activity_id="activity-1",
    )
    service.runtime_store.create(request, _checkpoint(request))
    return request


def _crash_delete_at_phase(root, phase, ready):
    service = CompositeLearningDataService.from_root(root)
    lease = service.coordinator.begin_operation(OWNER, "", "delete")
    current = lease
    if phase != "fenced":
        service.learning_store.delete_owner_data(OWNER, operation_lease=current)
        current = service.coordinator.advance_operation(
            current, "learning_deleted", {"scope": "owner"}
        )
    if phase in {"runtime_deleted", "compacted"}:
        service.runtime_store.delete_owner_data(OWNER, operation_lease=current)
        current = service.coordinator.advance_operation(
            current, "runtime_deleted", {"scope": "owner"}
        )
    if phase == "compacted":
        service.runtime_store.compact(OWNER, operation_lease=current)
        current = service.coordinator.advance_operation(
            current, "compacted", {"scope": "owner"}
        )
    ready.send((current.operation_id, current.phase))
    ready.close()
    os._exit(23)


def _crash_import_at_phase(root, bundle, phase, ready):
    service = CompositeLearningDataService.from_root(root)
    lease = service.coordinator.begin_operation(
        OWNER, "", "full_import", service.bundle_sha256(bundle)
    )
    current = lease
    if phase != "fenced":
        current = service.coordinator.advance_operation(
            current, "validated_empty", {"target_was_empty": True}
        )
    if phase in {"learning_imported", "runtime_imported"}:
        service.learning_store.import_owner_bundle(
            OWNER, bundle["learning_v1"], operation_lease=current
        )
        current = service.coordinator.advance_operation(
            current, "learning_imported", {"target_was_empty": True}
        )
    if phase == "runtime_imported":
        service.runtime_store.import_owner_bundle(
            OWNER,
            bundle["tutor_runtime"],
            mode="replace_empty_owner",
            operation_lease=current,
        )
        current = service.coordinator.advance_operation(
            current, "runtime_imported", {"target_was_empty": True}
        )
    ready.send((current.operation_id, current.phase))
    ready.close()
    os._exit(24)


def _crash_restore_at_phase(root, phase, ready):
    service = CompositeLearningDataService.from_root(root)
    lease = service.coordinator.begin_operation(
        OWNER, "", "runtime_restore", "a" * 64
    )
    current = lease
    if phase == "runtime_merged":
        current = service.coordinator.advance_operation(
            current, "runtime_merged", {"bundle_sha256": "a" * 64}
        )
    elif phase == "runtime_deleted":
        service.runtime_store.delete_owner_data(OWNER, operation_lease=current)
        current = service.coordinator.advance_operation(
            current, "runtime_deleted", {"verified_bundle_sha256": "a" * 64}
        )
    ready.send((current.operation_id, current.phase))
    ready.close()
    os._exit(25)


def _hold_live_operation(root, ready, release):
    service = CompositeLearningDataService.from_root(root)
    try:
        lease = service.coordinator.begin_operation(OWNER, "", "delete")
        ready.put(lease.operation_id)
        release.wait(15)
    finally:
        service.close()


class LearningRecoveryEntrypointTests(unittest.TestCase):
    def setUp(self):
        self._temp = tempfile.TemporaryDirectory()
        self.root = Path(self._temp.name)
        self._old_pythonpath = os.environ.get("PYTHONPATH")
        os.environ["PYTHONPATH"] = os.pathsep.join(
            (
                str(ROOT / "python"),
                str(ROOT / "python" / "src"),
                str(ROOT / "hermes_core"),
            )
        )

    def tearDown(self):
        if self._old_pythonpath is None:
            os.environ.pop("PYTHONPATH", None)
        else:
            os.environ["PYTHONPATH"] = self._old_pythonpath
        self._temp.cleanup()

    def _run_entrypoint(self, root):
        env = os.environ.copy()
        env["PYTHONPATH"] = os.pathsep.join(
            (str(ROOT / "python" / "src"), str(ROOT / "hermes_core"))
        )
        return subprocess.run(
            [
                sys.executable,
                "-m",
                "learning_recovery",
                "--root",
                str(root),
            ],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=30,
            check=False,
        )

    def _spawn_driver(
        self,
        operation,
        root,
        phase,
        *,
        bundle=None,
        release_path=None,
    ):
        ready_path = Path(root) / f".ready-{operation}-{phase}.json"
        command = [
            sys.executable,
            str(ROOT / "python" / "tests" / "learning_recovery_child.py"),
            operation,
            str(root),
            phase,
            str(ready_path),
        ]
        if bundle is not None:
            bundle_path = Path(root).parent / f".bundle-{phase}.json"
            bundle_path.write_text(
                json.dumps(bundle, ensure_ascii=False),
                encoding="utf-8",
            )
            command.extend(("--bundle", str(bundle_path)))
        if release_path is not None:
            command.extend(("--release", str(release_path)))
        process = subprocess.Popen(
            command,
            cwd=ROOT,
            env=os.environ.copy(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline and not ready_path.exists():
            if process.poll() is not None:
                stdout, stderr = process.communicate()
                self.fail(f"child exited before ready: {stdout}\n{stderr}")
            time.sleep(0.02)
        self.assertTrue(ready_path.exists(), "child did not publish ready state")
        ready = json.loads(ready_path.read_text(encoding="utf-8"))
        return process, ready

    def _spawn_crash(self, operation, root, phase, *, bundle=None):
        process, ready = self._spawn_driver(
            operation, root, phase, bundle=bundle
        )
        process.communicate(timeout=15)
        self.assertNotEqual(process.returncode, 0)
        return ready

    def test_desktop_wires_recovery_before_port_handshake(self):
        source = (ROOT / "python" / "src" / "desktop_entrypoint.py").read_text(
            encoding="utf-8"
        )
        self.assertLess(
            source.index("recover_learning_operations_once()"),
            source.index("_write_handshake(port)"),
        )
        self.assertIn("_learning_recovery_runner.start()", source)

    def test_delete_restart_entrypoint_recovers_every_durable_phase(self):
        for phase in ("fenced", "learning_deleted", "runtime_deleted", "compacted"):
            with self.subTest(phase=phase):
                root = self.root / f"delete-{phase}"
                service = CompositeLearningDataService.from_root(root)
                _seed(service)
                service.close()
                self.assertEqual(
                    self._spawn_crash("delete", root, phase)[1],
                    phase,
                )
                result = self._run_entrypoint(root)
                self.assertEqual(result.returncode, 0, result.stderr)
                verified = CompositeLearningDataService.from_root(root)
                try:
                    self.assertEqual(verified.learning_store.list_spaces(OWNER), [])
                    self.assertTrue(verified.runtime_store.owner_is_empty(OWNER))
                    self.assertEqual(verified.coordinator.recover_operations(), ())
                finally:
                    verified.close()

    def test_import_restart_entrypoint_rolls_back_every_durable_phase(self):
        source = CompositeLearningDataService.from_root(self.root / "source")
        _seed(source)
        bundle = source.export_owner_bundle(OWNER)
        source.close()
        for phase in (
            "fenced",
            "validated_empty",
            "learning_imported",
            "runtime_imported",
        ):
            with self.subTest(phase=phase):
                root = self.root / f"import-{phase}"
                self.assertEqual(
                    self._spawn_crash(
                        "import",
                        root,
                        phase,
                        bundle=bundle,
                    )[1],
                    phase,
                )
                result = self._run_entrypoint(root)
                self.assertEqual(result.returncode, 0, result.stderr)
                verified = CompositeLearningDataService.from_root(root)
                try:
                    self.assertEqual(verified.learning_store.list_spaces(OWNER), [])
                    self.assertTrue(verified.runtime_store.owner_is_empty(OWNER))
                    self.assertEqual(verified.coordinator.recover_operations(), ())
                finally:
                    verified.close()

    def test_runtime_restore_restart_entrypoint_finishes_all_durable_phases(self):
        for phase in ("fenced", "runtime_merged", "runtime_deleted"):
            with self.subTest(phase=phase):
                root = self.root / f"restore-{phase}"
                service = CompositeLearningDataService.from_root(root)
                request = _seed(service)
                service.close()
                self.assertEqual(
                    self._spawn_crash(
                        "restore", root, phase
                    )[1],
                    phase,
                )
                result = self._run_entrypoint(root)
                self.assertEqual(result.returncode, 0, result.stderr)
                verified = CompositeLearningDataService.from_root(root)
                try:
                    expected_empty = phase == "runtime_deleted"
                    self.assertEqual(
                        verified.runtime_store.load(request.key) is None,
                        expected_empty,
                    )
                    self.assertEqual(verified.coordinator.recover_operations(), ())
                finally:
                    verified.close()

    def test_live_writer_is_not_recovered_by_second_entrypoint(self):
        root = self.root / "live"
        root.mkdir(parents=True, exist_ok=True)
        release_path = root / ".release"
        process, ready = self._spawn_driver(
            "live",
            root,
            "held",
            release_path=release_path,
        )
        operation_id = ready
        result = self._run_entrypoint(root)
        self.assertEqual(result.returncode, 0, result.stderr)
        observer = CompositeLearningDataService.from_root(root)
        try:
            self.assertEqual(observer.coordinator.recover_operations(), ())
            with closing(sqlite3.connect(observer.coordinator.db_path)) as connection:
                self.assertEqual(
                    connection.execute(
                        "SELECT operation_id FROM learning_operation_fences"
                    ).fetchone()[0],
                    operation_id,
                )
        finally:
            observer.close()
        release_path.write_text("release", encoding="utf-8")
        process.communicate(timeout=15)
        self.assertEqual(process.returncode, 0)
        self.assertEqual(self._run_entrypoint(root).returncode, 0)

    def test_failed_recovery_keeps_fence_and_logs_only_stable_reason(self):
        root = self.root / "failed"
        service = CompositeLearningDataService.from_root(root)
        lease = service.coordinator.begin_operation(
            "desktop:private-owner-content", "", "delete"
        )
        service.coordinator.close()
        with closing(sqlite3.connect(service.coordinator.db_path)) as connection:
            connection.execute(
                "UPDATE learning_operation_journal SET phase='corrupt_phase' "
                "WHERE operation_id=?",
                (lease.operation_id,),
            )
            connection.commit()
        service.close()
        result = self._run_entrypoint(root)
        self.assertEqual(result.returncode, 1)
        self.assertIn("operation_journal_phase_mismatch", result.stderr)
        self.assertNotIn("private-owner-content", result.stderr)
        with closing(
            sqlite3.connect(root / "learning_coordination.db")
        ) as connection:
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM learning_operation_fences"
                ).fetchone()[0],
                1,
            )
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM learning_operation_journal"
                ).fetchone()[0],
                1,
            )


if __name__ == "__main__":
    unittest.main()
