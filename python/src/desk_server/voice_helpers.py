# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Desk voice/STT helpers."""
from __future__ import annotations
import asyncio, base64, json, logging, os, sys, tempfile, time, traceback
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from hermes_cli.config import get_hermes_home, load_config, save_config, save_env_value
log = logging.getLogger(__name__)
# region agent log
def _agent_dbg_stt(line: dict) -> None:
    """Append one NDJSON line for debug session 914e79.

    Tries several paths so logs are findable in dev vs MSI bundle:
      * ``%HERMESDESK_DATA_DIR%/logs/`` (same folder as hermesdesk.log)
      * repo / runtime parent (legacy single-path behavior)
      * system temp as last resort
    """
    import json
    import time

    line.setdefault("sessionId", "914e79")
    line.setdefault("timestamp", int(time.time() * 1000))

    candidates: List[Path] = []
    data_dir = (os.environ.get("HERMESDESK_DATA_DIR") or "").strip()
    if data_dir:
        candidates.append(Path(data_dir) / "logs" / "debug-914e79.log")
    # Dev: hermes_core/hermes_cli/web_server.py -> parents[2] == repo root
    try:
        candidates.append(Path(__file__).resolve().parents[2] / "debug-914e79.log")
    except Exception:
        pass
    try:
        candidates.append(get_hermes_home() / "logs" / "debug-914e79.log")
    except Exception:
        pass
    candidates.append(Path(tempfile.gettempdir()) / "hermesdesk-debug-914e79.log")

    payload = json.dumps(line, ensure_ascii=False) + "\n"
    for p in candidates:
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            with open(p, "a", encoding="utf-8") as _f:
                _f.write(payload)
            return
        except Exception:
            continue


# endregion

_DESK_STT_MODEL_FILENAME = "ggml-base-q5_1.bin"
# Pinned mirror of the upstream HuggingFace snapshot. The base-q5_1 model is
# ~57 MB and Q5_1-quantised so it runs on a typical laptop CPU at ~real-time.
# The Kabuqina-hosted copy is first so user installs do not depend on GitHub/HF
# availability; HF and the community mirror remain fallbacks.
_DESK_STT_MODEL_URLS = (
    f"https://kabuqina.com/packages/stt/{_DESK_STT_MODEL_FILENAME}",
    f"https://huggingface.co/ggerganov/whisper.cpp/resolve/main/{_DESK_STT_MODEL_FILENAME}",
    f"https://hf-mirror.com/ggerganov/whisper.cpp/resolve/main/{_DESK_STT_MODEL_FILENAME}",
)
# SHA-256 of the published file. Empty string skips verification (acceptable
# for dev; pin for production releases). The endpoint logs a warning when
# unverified so the bundle owner notices.
_DESK_STT_MODEL_SHA256 = ""


def _desk_voice_paths_mod():
    try:
        import desk_voice_paths  # type: ignore[import-untyped]
    except ImportError:
        return None
    return desk_voice_paths


def _desk_stt_model_path() -> Path:
    """Canonical GGML path for downloads and API ``path`` when the file is absent."""
    dvm = _desk_voice_paths_mod()
    if dvm is not None:
        return dvm.canonical_stt_model_path(
            _DESK_STT_MODEL_FILENAME, no_env_fallback_dir=get_hermes_home()
        )
    data_dir = os.environ.get("HERMESDESK_DATA_DIR") or os.environ.get(
        "LOCALAPPDATA"
    )
    if not data_dir:
        return get_hermes_home() / "stt-models" / _DESK_STT_MODEL_FILENAME
    base = Path(data_dir)
    if "LOCALAPPDATA" in os.environ and base == Path(os.environ["LOCALAPPDATA"]):
        base = base / "HermesDesk"
    return base / "stt-models" / _DESK_STT_MODEL_FILENAME


def _desk_stt_model_resolved() -> tuple[Path, bool]:
    """Return ``(path, downloaded)`` for status: on-disk file if any, else canonical."""
    dvm = _desk_voice_paths_mod()
    if dvm is not None:
        home = get_hermes_home()
        found = dvm.resolve_existing_stt_model(
            _DESK_STT_MODEL_FILENAME, no_env_fallback_dir=home
        )
        if found is not None:
            return found, True
        return (
            dvm.canonical_stt_model_path(
                _DESK_STT_MODEL_FILENAME, no_env_fallback_dir=home
            ),
            False,
        )
    p = _desk_stt_model_path()
    try:
        p.stat()
        return p, True
    except OSError:
        return p, False


def _download_stt_model_blocking(dest: Path) -> Tuple[bool, Dict[str, Any]]:
    """Stream the GGML model to ``dest`` (atomic + verified).

    Tries each URL in ``_DESK_STT_MODEL_URLS`` in order. Writes to
    ``<dest>.tmp``, fsyncs, then renames over the final path. Verifies
    SHA-256 if pinned. Returns ``(ok, info_dict)``; on failure ``info_dict``
    contains ``error``/``detail`` keys.

    Synchronous on purpose so the FastAPI handler can offload it via
    ``run_in_executor``.
    """
    # region agent log
    _agent_dbg_stt(
        {
            "hypothesisId": "H1",
            "location": "_download_stt_model_blocking:enter",
            "message": "blocking worker started",
            "data": {"dest": str(dest)},
        }
    )
    # endregion
    import hashlib

    import httpx

    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        # region agent log
        _agent_dbg_stt(
            {
                "hypothesisId": "H1",
                "location": "_download_stt_model_blocking:mkdir",
                "message": "mkdir failed (uncaught would yield plain 500)",
                "data": {"type": type(exc).__name__, "detail": repr(exc)},
            }
        )
        # endregion
        raise

    # region agent log
    _agent_dbg_stt(
        {
            "hypothesisId": "H1",
            "location": "_download_stt_model_blocking:mkdir_ok",
            "message": "parent dir ready",
            "data": {"parent": str(dest.parent)},
        }
    )
    # endregion

    tmp = dest.with_suffix(dest.suffix + ".tmp")

    last_err: Optional[str] = None
    for url in _DESK_STT_MODEL_URLS:
        try:
            hasher = hashlib.sha256() if _DESK_STT_MODEL_SHA256 else None
            total = 0
            with httpx.Client(
                timeout=httpx.Timeout(600.0, connect=30.0),
                follow_redirects=True,
            ) as client:
                with client.stream("GET", url) as resp:
                    if resp.status_code != 200:
                        last_err = f"{url}: HTTP {resp.status_code}"
                        log.warning("stt-model download: %s", last_err)
                        continue
                    with open(tmp, "wb") as f:
                        for chunk in resp.iter_bytes(chunk_size=512 * 1024):
                            if not chunk:
                                continue
                            f.write(chunk)
                            total += len(chunk)
                            if hasher is not None:
                                hasher.update(chunk)
                        f.flush()
                        try:
                            os.fsync(f.fileno())
                        except OSError:
                            pass
            # SHA-256 check (skipped if not pinned).
            if hasher is not None:
                got = hasher.hexdigest().lower()
                expected = _DESK_STT_MODEL_SHA256.lower()
                if got != expected:
                    try:
                        tmp.unlink()
                    except OSError:
                        pass
                    last_err = f"sha256 mismatch (got {got}, expected {expected})"
                    log.warning("stt-model download: %s", last_err)
                    continue
            elif total < 1_000_000:
                # No hash pinned, but anything <1 MB is clearly not the
                # base-q5_1 model (real file is ~57 MB). Reject so a partial
                # / error-page download can't masquerade as success.
                try:
                    tmp.unlink()
                except OSError:
                    pass
                last_err = f"download too small ({total} bytes); likely not the model"
                log.warning("stt-model download: %s", last_err)
                continue
            # Atomic rename over destination.
            os.replace(tmp, dest)
            # region agent log
            _agent_dbg_stt(
                {
                    "hypothesisId": "H2",
                    "location": "_download_stt_model_blocking:success",
                    "message": "download ok",
                    "data": {"size": total, "source": url},
                }
            )
            # endregion
            return True, {"size": total, "path": str(dest), "source": url}
        except Exception as exc:
            try:
                if tmp.exists():
                    tmp.unlink()
            except OSError:
                pass
            last_err = f"{url}: {exc}"
            log.warning("stt-model download: %s", last_err)
            continue

    # region agent log
    _agent_dbg_stt(
        {
            "hypothesisId": "H2",
            "location": "_download_stt_model_blocking:all_urls_failed",
            "message": "returning controlled failure dict",
            "data": {"last_err": last_err or "unknown"},
        }
    )
    # endregion
    return False, {"error": "download_failed", "detail": last_err or "unknown"}


# ---------------------------------------------------------------------------
# Default STT provider auto-selection (HermesDesk only)
#
# When the user has never touched STT settings AND no cloud key is exported
# in env, we set ``stt.provider = local_command`` so transcribe_audio uses
# the bundled whisper.cpp wrapper (configured by desktop_entrypoint.py).
# Idempotent: only writes once per process; never overwrites a pre-existing
# config or an explicit user choice.
# ---------------------------------------------------------------------------
_DESK_STT_BUNDLE_ENV_WIRED = False


def _ensure_bundled_local_stt_env() -> None:
    """HermesDesk: set ``HERMES_LOCAL_STT_COMMAND`` from the runtime bundle.

    ``desktop_entrypoint._wire_local_stt`` already does this before importing
    ``web_server``.  If that step skipped (e.g. ``stt-bin`` missing in an older
    bundle, then added after ``build_bundle`` without restarting) or the env
    was lost, we mirror the same wiring here using ``HERMESDESK_BUNDLE_DIR``
    (set by the Tauri shell for the embedded Python).

    This allows ``stt.provider: local`` to fall through to ``local_command`` in
    ``transcription_tools._get_provider`` when faster-whisper is not installed
    (the default HermesDesk bundle).
    """
    global _DESK_STT_BUNDLE_ENV_WIRED
    if _DESK_STT_BUNDLE_ENV_WIRED:
        return
    if os.environ.get("HERMES_LOCAL_STT_COMMAND", "").strip():
        _DESK_STT_BUNDLE_ENV_WIRED = True
        return
    bundle = (os.environ.get("HERMESDESK_BUNDLE_DIR") or "").strip()
    if not bundle:
        _DESK_STT_BUNDLE_ENV_WIRED = True
        return
    root = Path(bundle)
    wrapper = root / "stt_wrapper.py"
    whisper = root / "stt-bin" / "whisper-cli.exe"
    if not wrapper.is_file() or not whisper.is_file():
        log.info(
            "bundled whisper.cpp not found under HERMESDESK_BUNDLE_DIR "
            "(wrapper_ok=%s whisper_ok=%s); local STT unavailable until "
            "python/build_bundle.ps1 stages stt-bin/",
            wrapper.is_file(),
            whisper.is_file(),
        )
        _DESK_STT_BUNDLE_ENV_WIRED = True
        return
    os.environ["HERMES_LOCAL_STT_COMMAND"] = (
        f'"{sys.executable}" "{wrapper}" '
        f"{{input_path}} {{output_dir}} {{language}} {{model}}"
    )
    os.environ.setdefault("HERMES_LOCAL_STT_LANGUAGE", "auto")
    log.info("HERMES_LOCAL_STT_COMMAND wired from bundle (second-chance web_server)")
    _DESK_STT_BUNDLE_ENV_WIRED = True


_DESK_STT_DEFAULT_APPLIED = False
_DESK_STT_CLOUD_KEY_ENV_VARS = (
    "GROQ_API_KEY",
    "OPENAI_API_KEY",
    "VOICE_TOOLS_OPENAI_KEY",
    "MISTRAL_API_KEY",
    "XAI_API_KEY",
)


def _ensure_default_stt_provider() -> None:
    """If neither config nor env names a cloud STT, pick ``local_command``.

    Runs once per process (idempotent flag) on the first /api/desk/transcribe
    call, so the user sees a working mic even if they never opened the
    onboarding wizard.
    """
    global _DESK_STT_DEFAULT_APPLIED
    if _DESK_STT_DEFAULT_APPLIED:
        return
    _DESK_STT_DEFAULT_APPLIED = True

    # Only when the wrapper is wired up — otherwise we'd just be promising a
    # local STT we can't actually run.
    if not os.environ.get("HERMES_LOCAL_STT_COMMAND", "").strip():
        return

    try:
        cfg = load_config()
    except Exception as exc:
        log.warning("ensure_default_stt_provider: load_config failed: %s", exc)
        return

    stt = cfg.get("stt") if isinstance(cfg, dict) else None
    if isinstance(stt, dict) and stt.get("provider"):
        return  # User already chose something; respect it.

    if any(os.environ.get(k, "").strip() for k in _DESK_STT_CLOUD_KEY_ENV_VARS):
        return  # Cloud key present — let _get_provider auto-resolve to it.

    try:
        new_stt = dict(stt) if isinstance(stt, dict) else {}
        new_stt["provider"] = "local_command"
        new_stt.setdefault("model", "base")
        cfg["stt"] = new_stt
        save_config(cfg)
        log.info("ensure_default_stt_provider: set stt.provider=local_command")
    except Exception as exc:
        log.warning("ensure_default_stt_provider: save_config failed: %s", exc)


# Public aliases for route modules.
agent_dbg_stt = _agent_dbg_stt
desk_voice_paths_mod = _desk_voice_paths_mod
desk_stt_model_path = _desk_stt_model_path
desk_stt_model_resolved = _desk_stt_model_resolved
download_stt_model_blocking = _download_stt_model_blocking
ensure_bundled_local_stt_env = _ensure_bundled_local_stt_env
ensure_default_stt_provider = _ensure_default_stt_provider
DESK_STT_MODEL_SHA256 = _DESK_STT_MODEL_SHA256
DESK_STT_MODEL_URLS = _DESK_STT_MODEL_URLS
