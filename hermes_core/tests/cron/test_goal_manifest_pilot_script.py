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


def _prepare(tmp_path: Path) -> tuple[Path, dict]:
    engine = "graph"
    run_dir = tmp_path / f"{engine}-pilot"
    payload, _ = _run_script(
        "prepare", "--run-dir", str(run_dir), "--engine", engine
    )
    return run_dir, payload


def test_prepare_creates_fresh_isolated_file_only_pilot(tmp_path):
    run_dir, payload = _prepare(tmp_path)

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

    assert record["engine"] == "graph"
    assert record["job_id"] == payload["job_id"]
    assert job["enabled_toolsets"] == ["file"]
    assert "materials/lesson.docx" in job["prompt"]
    assert "Do not call search_files" in job["prompt"]
    assert job["goal"]["limits"]["max_runs"] == 40
    assert job["goal"]["verifier"]["kind"] == "manifest_complete"
    assert [item["path"] for item in manifest["files"]] == ["materials/algebra.pdf"]


def test_prepare_refuses_the_removed_loop_engine(tmp_path):
    run_dir = tmp_path / "loop-pilot"
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "prepare", "--run-dir", str(run_dir), "--engine", "loop"],
        cwd=CORE_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode != 0
    assert not run_dir.exists()


def test_prepare_refuses_to_reuse_existing_run_directory(tmp_path):
    run_dir, _ = _prepare(tmp_path)
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
