"""Bounded subprocess runner for trusted STUDY code grading.

Threat model
============
The executed program combines learner-authored code with test code from a
model-authored quiz that a trusted user has explicitly activated. Both are
untrusted. This runner reduces accidental and adversarial impact by using a
fresh temporary working directory, CPython isolated mode (``-I``), a minimal
environment, a hard timeout with process-tree termination, no visible Windows
console, and bounded output buffers. Raw output is never returned by the public
API; only a short failure classification is exposed.

This is *not* a complete security sandbox. In v1 the child still runs as the
current OS user and can attempt absolute-path filesystem access, network
egress, process creation, and memory exhaustion before the timeout. The temp
CWD is containment-by-default, not an OS access-control boundary. Windows has
no per-process network-deny primitive used here. Future hardening candidates
are installer-managed firewall rules or a WASM/Pyodide execution backend.
Release notes must retain these residual-risk statements.

The empty ``__builtins__`` mapping used by numeric-equivalence ``eval`` is a
robustness measure, not a security boundary: Python object-graph escapes can
still reach runtime objects. Those expressions already run in this untrusted
child process and this helper must never be reused as a "safe eval" primitive.
"""

from __future__ import annotations

import json
import logging
import os
import re
import secrets
import signal
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from typing import Any, Dict, Iterable, List

DEFAULT_TIMEOUT_SECONDS = 5.0
MAX_TIMEOUT_SECONDS = 30.0
MAX_STREAM_BYTES = 64 * 1024
MAX_SOURCE_CHARS = 20_000
MAX_VARIABLES = 16
_EQUIVALENCE_MARKER = "__KQ_EQ__"
_COMPLETION_MARKER_PREFIX = "__KQ_GRADE_COMPLETE__"

logger = logging.getLogger(__name__)


def _timeout(value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("timeout_s must be a number")
    normalized = float(value)
    if normalized <= 0 or normalized > MAX_TIMEOUT_SECONDS:
        raise ValueError(f"timeout_s must be within 0..{MAX_TIMEOUT_SECONDS}")
    return normalized


def _minimal_env(temp_dir: str) -> Dict[str, str]:
    allowed = ("SYSTEMROOT", "WINDIR", "COMSPEC", "PATHEXT") if os.name == "nt" else ()
    env = {key: os.environ[key] for key in allowed if os.environ.get(key)}
    env["TEMP"] = temp_dir
    env["TMP"] = temp_dir
    return env


def _drain(
    stream: Any,
    chunks: List[bytes],
    state: Dict[str, bool],
    *,
    completion_marker: bytes = b"",
) -> None:
    stored = 0
    marker_tail = b""
    while True:
        block = stream.read(8192)
        if not block:
            break
        if completion_marker:
            marker_window = marker_tail + block
            if completion_marker in marker_window:
                state["completed"] = True
            marker_tail = marker_window[-max(0, len(completion_marker) - 1) :]
        remaining = MAX_STREAM_BYTES - stored
        if remaining > 0:
            kept = block[:remaining]
            chunks.append(kept)
            stored += len(kept)
        if len(block) > max(0, remaining):
            state["truncated"] = True


def _kill_process_tree(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        result = subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            check=False,
            capture_output=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if result.returncode != 0 and process.poll() is None:
            process.kill()
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            if process.poll() is None:
                process.kill()


def _execute_python(
    script: str,
    *,
    timeout_s: float,
    completion_marker: str = "",
) -> Dict[str, Any]:
    timeout = _timeout(timeout_s)
    result: Dict[str, Any]
    temp_path: Path | None = None
    with tempfile.TemporaryDirectory(
        prefix="kabuqina-grade-", ignore_cleanup_errors=True
    ) as temp_dir:
        temp_path = Path(temp_dir)
        script_path = Path(temp_dir) / "grade.py"
        script_path.write_text(script, encoding="utf-8", newline="\n")
        creationflags = 0
        popen_kwargs: Dict[str, Any] = {}
        if os.name == "nt":
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(
                subprocess, "CREATE_NEW_PROCESS_GROUP", 0
            )
        else:
            popen_kwargs["start_new_session"] = True
        process = subprocess.Popen(
            [sys.executable, "-I", "-B", str(script_path)],
            cwd=temp_dir,
            env=_minimal_env(temp_dir),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=creationflags,
            **popen_kwargs,
        )
        stdout_chunks: List[bytes] = []
        stderr_chunks: List[bytes] = []
        stream_state = {"truncated": False, "completed": False}
        readers = [
            threading.Thread(
                target=_drain,
                args=(process.stdout, stdout_chunks, stream_state),
                kwargs={"completion_marker": completion_marker.encode("utf-8")},
                daemon=True,
            ),
            threading.Thread(
                target=_drain,
                args=(process.stderr, stderr_chunks, stream_state),
                daemon=True,
            ),
        ]
        for reader in readers:
            reader.start()
        timed_out = False
        termination_failed = False
        try:
            returncode = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            _kill_process_tree(process)
            try:
                returncode = process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                termination_failed = True
                try:
                    process.kill()
                except (OSError, subprocess.SubprocessError):
                    pass
                try:
                    returncode = process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    returncode = None
        finally:
            for reader in readers:
                reader.join(timeout=3)
            if process.stdout:
                process.stdout.close()
            if process.stderr:
                process.stderr.close()
        result = {
            "returncode": returncode,
            "stdout": b"".join(stdout_chunks).decode("utf-8", errors="replace"),
            "stderr": b"".join(stderr_chunks).decode("utf-8", errors="replace"),
            "timed_out": timed_out,
            "truncated": stream_state["truncated"],
            "completed": stream_state["completed"],
            "termination_failed": termination_failed,
        }
    cleanup_leaked = bool(temp_path and temp_path.exists())
    if cleanup_leaked:
        logger.warning("code grader temporary directory cleanup leaked: %s", temp_path)
    result["cleanup_leaked"] = cleanup_leaked
    return result


def _safe_failure_summary(result: Dict[str, Any]) -> str:
    if result["timed_out"]:
        return "Execution timed out"
    stderr = str(result.get("stderr") or "")
    for line in reversed(stderr.splitlines()):
        text = " ".join(line.strip().split())
        if not text:
            continue
        match = re.match(
            r"^(?P<kind>[A-Za-z_][A-Za-z0-9_.]*(?:Error|Exception))(?::\s*(?P<message>.*))?$",
            text,
        )
        if not match:
            continue
        kind = match.group("kind")
        message = re.sub(r"[\x00-\x1f\x7f]", " ", match.group("message") or "")
        message = " ".join(message.split())[:240]
        return f"{kind}: {message}" if message else kind
    return f"Process exited with code {result.get('returncode')}"


def run_python_grading(
    source: str,
    test_code: str,
    *,
    timeout_s: float = DEFAULT_TIMEOUT_SECONDS,
) -> Dict[str, Any]:
    """Execute learner source plus trusted tests and return a bounded result."""
    if not isinstance(source, str) or not isinstance(test_code, str):
        raise ValueError("source and test_code must be strings")
    if len(source) > MAX_SOURCE_CHARS or len(test_code) > MAX_SOURCE_CHARS:
        raise ValueError(f"source and test_code must be <= {MAX_SOURCE_CHARS} chars")
    completion_marker = f"{_COMPLETION_MARKER_PREFIX}{secrets.token_hex(16)}"
    script = (
        "# coding: utf-8\n"
        "import sys as __kq_grader_sys\n"
        f"{source.rstrip()}\n\n{test_code.rstrip()}\n\n"
        f"__kq_grader_sys.stdout.write({completion_marker!r} + '\\n')\n"
    )
    try:
        result = _execute_python(
            script,
            timeout_s=timeout_s,
            completion_marker=completion_marker,
        )
    except (OSError, subprocess.SubprocessError, PermissionError) as exc:
        return {
            "status": "unavailable",
            "passed": False,
            "failure_summary": f"Grader unavailable: {type(exc).__name__}",
            "timed_out": False,
            "truncated": False,
        }
    passed = (
        result["returncode"] == 0
        and not result["timed_out"]
        and result["completed"]
    )
    return {
        "status": (
            "passed"
            if passed
            else "timeout"
            if result["timed_out"]
            else "unavailable"
            if result["termination_failed"] or result["cleanup_leaked"]
            else "failed"
        ),
        "passed": passed,
        "failure_summary": "" if passed else _safe_failure_summary(result),
        "timed_out": result["timed_out"],
        "truncated": result["truncated"],
    }


def _variables(values: Iterable[str]) -> List[str]:
    if not isinstance(values, (list, tuple)):
        raise ValueError("variables must be a list")
    out: List[str] = []
    for value in values:
        if not isinstance(value, str) or not value.isidentifier() or value.startswith("_"):
            raise ValueError("variables must contain public Python identifiers")
        if value not in out:
            out.append(value)
        if len(out) > MAX_VARIABLES:
            raise ValueError(f"variables exceeds {MAX_VARIABLES}")
    return out


def check_numeric_equivalence(
    expr_py_a: str,
    expr_py_b: str,
    variables: Iterable[str],
    *,
    samples: int = 8,
    timeout_s: float = DEFAULT_TIMEOUT_SECONDS,
) -> Dict[str, Any]:
    """Compare Python-evaluable expressions at deterministic shared samples."""
    if not isinstance(expr_py_a, str) or not expr_py_a.strip():
        raise ValueError("expr_py_a is required")
    if not isinstance(expr_py_b, str) or not expr_py_b.strip():
        raise ValueError("expr_py_b is required")
    if len(expr_py_a) > MAX_SOURCE_CHARS or len(expr_py_b) > MAX_SOURCE_CHARS:
        raise ValueError(f"expressions must be <= {MAX_SOURCE_CHARS} chars")
    if isinstance(samples, bool) or not isinstance(samples, int) or not (1 <= samples <= 64):
        raise ValueError("samples must be within 1..64")
    names = _variables(variables)
    payload = json.dumps(
        {"a": expr_py_a, "b": expr_py_b, "variables": names, "samples": samples},
        ensure_ascii=False,
    )
    script = f'''# coding: utf-8
import json, math, random
cfg = json.loads({json.dumps(payload)})
rng = random.Random(12635537)
checked = 0
equivalent = True
safe_globals = {{"__builtins__": {{}}, "math": math}}
for _ in range(cfg["samples"]):
    scope = {{name: rng.uniform(-5.0, 5.0) for name in cfg["variables"]}}
    try:
        left = float(eval(cfg["a"], safe_globals, scope))
        right = float(eval(cfg["b"], safe_globals, scope))
        if not (math.isfinite(left) and math.isfinite(right)):
            continue
    except (ArithmeticError, ValueError, TypeError, NameError, OverflowError):
        continue
    checked += 1
    if not math.isclose(left, right, rel_tol=1e-9, abs_tol=1e-9):
        equivalent = False
        break
print("{_EQUIVALENCE_MARKER}" + json.dumps({{"equivalent": equivalent and checked > 0, "checked": checked}}))
'''
    result = _execute_python(script, timeout_s=timeout_s)
    if result["timed_out"]:
        return {
            "equivalent": False,
            "needs_human_check": True,
            "failure_summary": "Equivalence check timed out",
            "samples_checked": 0,
        }
    marker_line = next(
        (
            line[len(_EQUIVALENCE_MARKER) :]
            for line in reversed(result["stdout"].splitlines())
            if line.startswith(_EQUIVALENCE_MARKER)
        ),
        None,
    )
    if result["returncode"] != 0 or marker_line is None:
        return {
            "equivalent": False,
            "needs_human_check": True,
            "failure_summary": _safe_failure_summary(result),
            "samples_checked": 0,
        }
    try:
        parsed = json.loads(marker_line)
        checked = int(parsed.get("checked") or 0)
        equivalent = parsed.get("equivalent") is True
    except (TypeError, ValueError, json.JSONDecodeError):
        checked = 0
        equivalent = False
    return {
        "equivalent": equivalent,
        "needs_human_check": checked == 0,
        "failure_summary": "" if equivalent else (
            "No valid sample points" if checked == 0 else "Expressions differ"
        ),
        "samples_checked": checked,
    }
