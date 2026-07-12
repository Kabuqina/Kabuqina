# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Contract tests for the constrained Task 10 Pilot 1 harness."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


CORE_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = CORE_ROOT / "scripts" / "run_goal_manifest_pilot.py"


def _run_script(*args: str) -> tuple[dict, str]:
    env = dict(os.environ)
    env.pop("HERMES_HOME", None)
    result = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=CORE_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    return json.loads(result.stdout), result.stdout


def _prepare(tmp_path: Path, engine: str) -> tuple[Path, dict]:
    run_dir = tmp_path / f"{engine}-pilot"
    payload, _ = _run_script(
        "prepare", "--run-dir", str(run_dir), "--engine", engine
    )
    return run_dir, payload


def _write_transition(run_dir: Path, *, artifact_hash: str) -> None:
    record = json.loads((run_dir / "pilot-run.json").read_text(encoding="utf-8"))
    iteration_dir = (
        run_dir
        / "hermes-home"
        / "cron"
        / "goal-runs"
        / record["job_id"]
        / "iterations"
        / "000001"
    )
    iteration_dir.mkdir(parents=True)
    (iteration_dir / "transition.json").write_text(
        json.dumps(
            {
                "iteration": 1,
                "previous_status": "scheduled",
                "next_status": "completed",
                "reason": "verified_complete",
                "last_artifact_hash": artifact_hash,
                "next_state": {"last_summary": "never expose this body"},
            }
        ),
        encoding="utf-8",
    )
    (iteration_dir / "verification.json").write_text(
        json.dumps(
            {
                "outcome": "pass",
                "summary": "secret report body must not reach compare output",
                "evidence": {"secret": "not-for-output"},
            }
        ),
        encoding="utf-8",
    )


def test_prepare_creates_fresh_isolated_file_only_pilot(tmp_path):
    run_dir, payload = _prepare(tmp_path, "loop")

    assert payload["status"] == "prepared"
    record = json.loads((run_dir / "pilot-run.json").read_text(encoding="utf-8"))
    jobs_document = json.loads(
        (run_dir / "hermes-home" / "cron" / "jobs.json").read_text(encoding="utf-8")
    )
    job = jobs_document["jobs"][0]
    manifest = json.loads(
        (run_dir / "workspace" / "learning-materials.json").read_text(
            encoding="utf-8"
        )
    )

    assert record["engine"] == "loop"
    assert record["job_id"] == payload["job_id"]
    assert job["enabled_toolsets"] == ["file"]
    assert job["goal"]["limits"]["max_runs"] == 40
    assert job["goal"]["verifier"]["kind"] == "manifest_complete"
    assert [item["path"] for item in manifest["files"]] == ["materials/algebra.pdf"]


def test_compare_uses_only_sanitized_transition_and_verifier_metadata(tmp_path):
    loop_dir, _ = _prepare(tmp_path, "loop")
    graph_dir, _ = _prepare(tmp_path, "graph")
    _write_transition(loop_dir, artifact_hash="a" * 64)
    _write_transition(graph_dir, artifact_hash="a" * 64)

    payload, stdout = _run_script(
        "compare",
        "--loop-run-dir",
        str(loop_dir),
        "--graph-run-dir",
        str(graph_dir),
    )

    assert payload["comparison"] == {
        "artifact_hash_equal": True,
        "manual_review_required": True,
        "transition_sequence_equal": True,
        "verifier_outcomes_equal": True,
    }
    assert payload["loop"]["transitions"] == [
        {
            "artifact_hash": "a" * 64,
            "iteration": 1,
            "next_status": "completed",
            "previous_status": "scheduled",
            "reason": "verified_complete",
        }
    ]
    assert "secret report body" not in stdout
    assert "not-for-output" not in stdout


def test_prepare_refuses_to_reuse_existing_run_directory(tmp_path):
    run_dir, _ = _prepare(tmp_path, "graph")
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "prepare",
            "--run-dir",
            str(run_dir),
            "--engine",
            "graph",
        ],
        cwd=CORE_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 1
    assert json.loads(result.stdout)["error"] == "run directory must not already exist"
