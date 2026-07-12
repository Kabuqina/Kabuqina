#!/usr/bin/env python3
# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Prepare, wake, and compare the bounded Goal Runner Pilot 1.

This harness is deliberately narrower than the product Goal UI.  It accepts no
arbitrary verifier, toolset, budget, or workspace definition: every run starts
from the frozen ``goal_manifest_pilot`` fixture, uses only the ``file`` toolset,
and records a single explicit ``loop`` *or* ``graph`` engine.  ``wake`` runs at
most one agent iteration, preserving the one-iteration-per-wake contract.

The script never copies credentials.  When a real wake is intended, provide a
disposable profile config with ``--config`` and supply credentials through the
normal process environment.  The script prints and compares only transition,
verifier, and artifact-hash metadata; it never prints prompts, model output,
document contents, or report bodies.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


CORE_ROOT = Path(__file__).resolve().parents[1]
PILOT_FIXTURE = (
    CORE_ROOT / "tests" / "cron" / "fixtures" / "goal_manifest_pilot"
)
_RECORD_NAME = "pilot-run.json"
_RECORD_VERSION = 1
_ENGINES = frozenset({"loop", "graph"})
_MISSING_FIXTURE_PATH = "materials/lesson.docx"
_PUBLIC_ITERATION_PROMPT = (
    "Inspect at most one new or changed supported file, then update "
    "learning-materials.json with its normalized relative path, SHA-256, and "
    "byte size. Do not write outside the selected workspace."
)
_SYNTHETIC_ITERATION_PROMPT = (
    "Complete exactly the seeded manifest gap for materials/lesson.docx. "
    "Do not call search_files: the synthetic candidate is already selected. "
    "Read learning-materials.json, call file_metadata on "
    "materials/lesson.docx, then update the manifest while preserving its "
    "existing records. Finish by calling goal_report exactly once."
)


class PilotError(RuntimeError):
    """Raised when a pilot command would escape its narrow contract."""


def _json_line(payload: Mapping[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def _add_core_root_to_path() -> None:
    root = str(CORE_ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)


def _fixture_tree_digest() -> str:
    digest = hashlib.sha256()
    for path in sorted(PILOT_FIXTURE.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(PILOT_FIXTURE).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative)
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _read_fixture_definition() -> dict[str, Any]:
    try:
        raw = json.loads(
            (PILOT_FIXTURE / "pilot-definition.json").read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as exc:
        raise PilotError("Pilot 1 definition fixture is unreadable") from exc
    if not isinstance(raw, dict):
        raise PilotError("Pilot 1 definition fixture must be a JSON object")
    return raw


def _assert_frozen_fixture(definition: Mapping[str, Any]) -> None:
    """Fail closed if the harness's fixed public-safety contract drifts."""
    verifier = definition.get("verifier")
    limits = definition.get("limits")
    if definition.get("mode") != "goal":
        raise PilotError("Pilot 1 fixture must be a goal job")
    if definition.get("prompt") != _PUBLIC_ITERATION_PROMPT:
        raise PilotError("Pilot 1 public iteration prompt drifted")
    if definition.get("enabled_toolsets") != ["file"]:
        raise PilotError("Pilot 1 permits only the file toolset")
    if definition.get("deliver") != "local":
        raise PilotError("Pilot 1 delivery must remain local")
    if not isinstance(verifier, Mapping) or verifier.get("kind") != "manifest_complete":
        raise PilotError("Pilot 1 requires the manifest_complete verifier")
    if verifier.get("config") != {
        "manifest": "learning-materials.json",
        "roots": ["materials"],
        "extensions": [".pdf", ".docx", ".pptx"],
    }:
        raise PilotError("Pilot 1 verifier configuration drifted")
    if limits != {
        "max_runs": 40,
        "max_cost_usd": "5.00",
        "max_wall_seconds": 14400,
        "deadline": None,
        "no_progress_limit": 3,
        "max_infrastructure_failures": 3,
    }:
        raise PilotError("Pilot 1 limits or pause thresholds drifted")
    if definition.get("approval_mode") != "ask_before_external_side_effect":
        raise PilotError("Pilot 1 approval mode drifted")


def _run_paths(run_dir: Path) -> tuple[Path, Path, Path]:
    root = run_dir.resolve()
    return root, root / "workspace", root / "hermes-home"


def _prepare_workspace(workspace: Path) -> None:
    shutil.copytree(PILOT_FIXTURE, workspace)
    manifest_path = workspace / "learning-materials.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        files = manifest["files"]
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise PilotError("Pilot fixture manifest is unreadable") from exc
    if not isinstance(files, list):
        raise PilotError("Pilot fixture manifest files must be a list")
    remaining = [
        record
        for record in files
        if not isinstance(record, Mapping)
        or record.get("path") != _MISSING_FIXTURE_PATH
    ]
    if len(remaining) != len(files) - 1:
        raise PilotError("Pilot fixture must contain exactly one removable material")
    manifest_path.write_text(
        json.dumps({"files": remaining}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _write_record(path: Path, payload: Mapping[str, Any]) -> None:
    try:
        with path.open("x", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
    except FileExistsError as exc:
        raise PilotError(f"pilot record already exists: {path}") from exc


def _read_record(run_dir: Path) -> dict[str, Any]:
    root, workspace, home = _run_paths(run_dir)
    try:
        raw = json.loads((root / _RECORD_NAME).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PilotError("pilot record is unreadable") from exc
    if not isinstance(raw, dict) or raw.get("schema_version") != _RECORD_VERSION:
        raise PilotError("pilot record has an unsupported schema")
    if raw.get("workspace") != "workspace" or raw.get("hermes_home") != "hermes-home":
        raise PilotError("pilot record paths are invalid")
    if raw.get("engine") not in _ENGINES:
        raise PilotError("pilot record engine is invalid")
    job_id = raw.get("job_id")
    if not isinstance(job_id, str) or len(job_id) != 12:
        raise PilotError("pilot record job id is invalid")
    if not workspace.is_dir() or not home.is_dir():
        raise PilotError("pilot workspace or isolated profile is missing")
    return raw


def _activate_home(home: Path) -> None:
    os.environ["HERMES_HOME"] = str(home)
    _add_core_root_to_path()


def _runtime_components() -> tuple[Any, Any, Any, Any, Any, Any]:
    """Import runtime pieces only after the isolated home is selected."""
    from cron.goal_agent_worker import GoalAgentWorker
    from cron.goal_runner import run_goal_iteration
    from cron.goal_state import load_goal_state
    from cron.goal_verifiers import RegistryVerifier
    from cron.jobs import create_job, get_job
    from cron.scheduler import _build_goal_definition

    return (
        create_job,
        get_job,
        _build_goal_definition,
        GoalAgentWorker,
        RegistryVerifier,
        (run_goal_iteration, load_goal_state),
    )


def _assert_persisted_job_contract(job: Mapping[str, Any], workspace: Path) -> None:
    definition = _read_fixture_definition()
    _assert_frozen_fixture(definition)
    if job.get("mode") != "goal":
        raise PilotError("persisted Pilot 1 job is not a goal job")
    if job.get("enabled_toolsets") != ["file"]:
        raise PilotError("persisted Pilot 1 job broadens the toolset")
    if Path(str(job.get("workdir", ""))).resolve() != workspace.resolve():
        raise PilotError("persisted Pilot 1 workdir changed")
    goal = job.get("goal")
    if not isinstance(goal, Mapping):
        raise PilotError("persisted Pilot 1 goal spec is missing")
    if goal.get("verifier") != definition["verifier"]:
        raise PilotError("persisted Pilot 1 verifier changed")
    if goal.get("limits") != definition["limits"]:
        raise PilotError("persisted Pilot 1 limits changed")
    if goal.get("approval_mode") != definition["approval_mode"]:
        raise PilotError("persisted Pilot 1 approval policy changed")
    if job.get("prompt") != _SYNTHETIC_ITERATION_PROMPT:
        raise PilotError("persisted synthetic Pilot 1 prompt changed")


def prepare_run(run_dir: Path, engine: str, config_path: Path | None = None) -> dict[str, Any]:
    """Create one fresh, isolated, synthetic run without invoking a model."""
    if engine not in _ENGINES:
        raise PilotError("engine must be loop or graph")
    root, workspace, home = _run_paths(run_dir)
    if root.exists():
        raise PilotError("run directory must not already exist")
    definition = _read_fixture_definition()
    _assert_frozen_fixture(definition)

    root.mkdir(parents=True)
    _prepare_workspace(workspace)
    home.mkdir()
    if config_path is not None:
        source = config_path.resolve()
        if not source.is_file():
            raise PilotError("--config must name an existing config.yaml file")
        shutil.copy2(source, home / "config.yaml")

    _activate_home(home)
    create_job, _, _, _, _, _ = _runtime_components()
    creation_definition = dict(definition)
    # The fixture's display name is part of the frozen public contract, but
    # each isolated run needs an engine-specific label for unambiguous evidence.
    creation_definition.pop("name", None)
    # The dual-engine harness works against one intentionally incomplete
    # fixture, so it supplies the known missing file rather than performing a
    # broad filesystem search. This keeps the proof focused on the controller,
    # verifier, and engine parity, while the public desktop template remains
    # the generic bounded-inventory prompt above.
    creation_definition["prompt"] = _SYNTHETIC_ITERATION_PROMPT
    job = create_job(
        name=f"Pilot 1 manifest inventory ({engine})",
        workdir=str(workspace.resolve()),
        **creation_definition,
    )
    _assert_persisted_job_contract(job, workspace)
    record = {
        "schema_version": _RECORD_VERSION,
        "engine": engine,
        "job_id": job["id"],
        "workspace": "workspace",
        "hermes_home": "hermes-home",
        "fixture_sha256": _fixture_tree_digest(),
        "seeded_missing_path": _MISSING_FIXTURE_PATH,
        "prepared_at": datetime.now(timezone.utc).isoformat(),
    }
    _write_record(root / _RECORD_NAME, record)
    return {
        "engine": engine,
        "job_id": job["id"],
        "run_dir": str(root),
        "status": "prepared",
    }


def wake_run(run_dir: Path, model: str = "") -> dict[str, Any]:
    """Run exactly one real AIAgent iteration through the recorded engine."""
    record = _read_record(run_dir)
    root, workspace, home = _run_paths(run_dir)
    _activate_home(home)
    (
        _,
        get_job,
        build_goal_definition,
        goal_agent_worker,
        registry_verifier,
        runner_components,
    ) = _runtime_components()
    run_goal_iteration, load_goal_state = runner_components
    job = get_job(record["job_id"])
    if job is None:
        raise PilotError("recorded Pilot 1 job no longer exists")
    _assert_persisted_job_contract(job, workspace)
    definition = build_goal_definition(job)
    before = load_goal_state(definition.job_id)
    worker = goal_agent_worker(agent_engine=record["engine"], model=model)
    result = run_goal_iteration(
        definition,
        worker=worker,
        verifier=registry_verifier(),
        now=datetime.now(timezone.utc),
    )
    state = result.transition.next_state
    try:
        evidence_path = result.evidence_path.resolve().relative_to(home.resolve())
    except ValueError as exc:
        raise PilotError("Pilot 1 wrote evidence outside its isolated profile") from exc
    return {
        "engine": record["engine"],
        "job_id": definition.job_id,
        "iteration": state.iteration,
        "previous_status": result.transition.previous_status,
        "next_status": state.status,
        "reason": result.transition.reason,
        "verifier_outcome": state.last_verifier_outcome,
        "artifact_hash": state.last_artifact_hash,
        "cost_accounting": state.cost_accounting,
        "evidence_path": evidence_path.as_posix(),
        "had_prior_state": before is not None,
    }


def _transition_trace(run_dir: Path) -> dict[str, Any]:
    record = _read_record(run_dir)
    _, _, home = _run_paths(run_dir)
    iteration_root = home / "cron" / "goal-runs" / record["job_id"] / "iterations"
    transitions: list[dict[str, Any]] = []
    verifier_outcomes: list[str | None] = []
    if iteration_root.exists():
        for iteration_dir in sorted(iteration_root.iterdir()):
            transition_path = iteration_dir / "transition.json"
            if not transition_path.is_file():
                continue
            try:
                transition = json.loads(transition_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise PilotError("committed pilot transition is unreadable") from exc
            if not isinstance(transition, Mapping):
                raise PilotError("committed pilot transition is invalid")
            transitions.append(
                {
                    "iteration": transition.get("iteration"),
                    "previous_status": transition.get("previous_status"),
                    "next_status": transition.get("next_status"),
                    "reason": transition.get("reason"),
                    "artifact_hash": transition.get("last_artifact_hash"),
                }
            )
            verification_path = iteration_dir / "verification.json"
            if verification_path.is_file():
                try:
                    verification = json.loads(
                        verification_path.read_text(encoding="utf-8")
                    )
                except (OSError, json.JSONDecodeError) as exc:
                    raise PilotError("committed pilot verification is unreadable") from exc
                if not isinstance(verification, Mapping):
                    raise PilotError("committed pilot verification is invalid")
                verifier_outcomes.append(verification.get("outcome"))
            else:
                verifier_outcomes.append(None)
    final_status = transitions[-1]["next_status"] if transitions else "prepared"
    final_artifact_hash = transitions[-1]["artifact_hash"] if transitions else None
    return {
        "engine": record["engine"],
        "job_id": record["job_id"],
        "status": final_status,
        "transitions": transitions,
        "verifier_outcomes": verifier_outcomes,
        "artifact_hash": final_artifact_hash,
    }


def compare_runs(loop_run_dir: Path, graph_run_dir: Path) -> dict[str, Any]:
    """Compare only durable, sanitized controller evidence from both engines."""
    loop = _transition_trace(loop_run_dir)
    graph = _transition_trace(graph_run_dir)
    if loop["engine"] != "loop" or graph["engine"] != "graph":
        raise PilotError("compare requires one loop run and one graph run")
    return {
        "loop": loop,
        "graph": graph,
        "comparison": {
            "transition_sequence_equal": loop["transitions"] == graph["transitions"],
            "verifier_outcomes_equal": (
                loop["verifier_outcomes"] == graph["verifier_outcomes"]
            ),
            "artifact_hash_equal": loop["artifact_hash"] == graph["artifact_hash"],
            "manual_review_required": True,
        },
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    prepare = commands.add_parser("prepare", help="create one isolated synthetic run")
    prepare.add_argument("--run-dir", type=Path, required=True)
    prepare.add_argument("--engine", choices=sorted(_ENGINES), required=True)
    prepare.add_argument(
        "--config",
        type=Path,
        help="optional non-secret config.yaml copied into the isolated profile",
    )

    wake = commands.add_parser("wake", help="run exactly one Pilot 1 wake")
    wake.add_argument("--run-dir", type=Path, required=True)
    wake.add_argument("--model", default="", help="optional explicit model override")

    compare = commands.add_parser(
        "compare", help="compare sanitized loop and graph pilot evidence"
    )
    compare.add_argument("--loop-run-dir", type=Path, required=True)
    compare.add_argument("--graph-run-dir", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "prepare":
            payload = prepare_run(args.run_dir, args.engine, args.config)
        elif args.command == "wake":
            payload = wake_run(args.run_dir, args.model)
        else:
            payload = compare_runs(args.loop_run_dir, args.graph_run_dir)
    except (PilotError, OSError, ValueError) as exc:
        _json_line({"error": str(exc)})
        return 1
    _json_line(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
