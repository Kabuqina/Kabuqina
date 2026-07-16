from pathlib import Path
import os
import subprocess


REPO_ROOT = Path(__file__).resolve().parents[2]
SETUP_SCRIPT = REPO_ROOT / "setup-hermes.sh"


def _bash_visible_path(path: Path) -> str:
    if os.name != "nt":
        return str(path)
    resolved = path.resolve()
    drive = resolved.drive.rstrip(":").lower()
    if not drive:
        return resolved.as_posix()
    return f"/mnt/{drive}{resolved.as_posix()[2:]}"


def test_setup_hermes_script_is_valid_shell():
    result = subprocess.run(
        ["bash", "-n", _bash_visible_path(SETUP_SCRIPT)],
        capture_output=True,
        text=True,
        timeout=120 if os.name == "nt" else 30,
    )
    assert result.returncode == 0, result.stderr


def test_setup_hermes_script_has_termux_path():
    content = SETUP_SCRIPT.read_text(encoding="utf-8")

    assert "is_termux()" in content
    assert ".[termux]" in content
    assert "constraints-termux.txt" in content
    assert "$PREFIX/bin" in content
    assert "Skipping tinker-atropos on Termux" in content
