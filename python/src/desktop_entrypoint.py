# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Kabuqina Python entrypoint.

Spawned by the Tauri shell. Responsibilities:

  1. Configure logging under ``HERMESDESK_DATA_DIR`` (Tauri: e.g. ``%LOCALAPPDATA%\\com.kabuqina.app``).
  2. Validate the Tauri <-> Python contract version.
  3. Build a typed ``DesktopConfig`` from env vars.
  4. Install runtime overlays (must happen before importing the agent core).
  5. Pick a free localhost port, write it to a handshake file the
     Tauri shell is polling.
  6. Launch Kabuqina's desktop server bound to 127.0.0.1:PORT.
  7. Forward SIGTERM cleanly so closing the window closes the agent.

Tauri sets these env vars before spawn:

    KABUQINA_BUNDLE_DIR          install dir (read-only)
    KABUQINA_DATA_DIR            per-user state (writable)
    KABUQINA_WORKSPACE           workspace folder
    KABUQINA_PORT_FILE           path where we write the chosen port
    KABUQINA_*                   remaining desktop bridge and model settings

Legacy ``HERMESDESK_*`` names are accepted for one compatibility release by
``kabuqina_env``; new names always take precedence, including explicit empties.
"""

from __future__ import annotations

import logging
import logging.handlers
import os
import socket
import sys
import threading
import time
from pathlib import Path
from typing import Optional

from kabuqina_env import (
    get as get_kabuqina_env,
    export_home,
    normalize as normalize_kabuqina_env,
    resolve_child_home,
)

_docling_warm_thread: Optional[threading.Thread] = None


def _prime_torch_main_thread(log: logging.Logger) -> bool:
    """Optionally import torch fully before Docling can touch it.

    This used to run by default to avoid a PyTorch circular-import edge case, but
    on cold Windows starts it can block the desktop handshake for 50s+.
    Docling reads already run on a serialized worker thread, so startup keeps
    this opt-in for diagnostics instead of making every user pay the torch cost.
    """
    if os.environ.get("HERMESDESK_TORCH_PRIME", "0").strip().lower() not in ("1", "true", "yes", "on"):
        log.info("Docling torch prime disabled by HERMESDESK_TORCH_PRIME")
        return False
    t0 = time.monotonic()
    try:
        import torch
        import torch.library  # noqa: F401
        if not hasattr(torch, "library"):
            raise AttributeError("torch imported without torch.library")
        log.info(
            "Docling torch primed on main thread in %.0fms version=%s path=%s",
            (time.monotonic() - t0) * 1000,
            getattr(torch, "__version__", "?"),
            getattr(torch, "__file__", "?"),
        )
        return True
    except Exception as exc:
        log.warning("Docling torch prime failed after %.0fms: %s", (time.monotonic() - t0) * 1000, exc)
        return False


def _setup_logging() -> None:
    data_dir = Path(get_kabuqina_env("KABUQINA_DATA_DIR", "."))
    log_dir = data_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    handler = logging.handlers.RotatingFileHandler(
        log_dir / "kabuqina.log",
        maxBytes=2_000_000, backupCount=3, encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)-7s %(name)s %(message)s"
    ))
    logging.basicConfig(level=logging.INFO, handlers=[handler, logging.StreamHandler(sys.stderr)])


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _write_handshake(port: int) -> None:
    path = get_kabuqina_env("KABUQINA_PORT_FILE")
    if not path:
        return
    Path(path).write_text(str(port), encoding="utf-8")


def _wire_tts_voice(log: logging.Logger) -> None:
    """Auto-configure Edge TTS voice based on system language.

    Sets a language-appropriate Edge TTS voice (e.g. ``zh-CN-XiaoxiaoNeural``
    for Chinese users) if the user hasn't explicitly configured one.
    Respects an existing ``tts.edge.voice`` in ``config.yaml``.
    """
    # Determine the appropriate voice from system locale
    if sys.platform == "win32":
        import ctypes

        try:
            lang_id = ctypes.windll.kernel32.GetUserDefaultUILanguage()
            primary_lang = lang_id & 0x3FF
            if primary_lang != 0x04:  # LANG_CHINESE
                return
            desired_voice = "zh-CN-XiaoxiaoNeural"
        except Exception:
            return
    else:
        try:
            import locale

            loc = locale.getlocale()[0] or ""
            if not loc.lower().startswith("zh"):
                return
            desired_voice = "zh-CN-XiaoxiaoNeural"
        except Exception:
            return

    # Write to config.yaml only if voice is still the English default.
    # If the user has explicitly set a voice we respect it.
    try:
        from kabuqina_cli.config import load_config, save_config

        cfg = load_config() or {}
        tts = cfg.setdefault("tts", {})
        edge = tts.setdefault("edge", {})
        current = (edge.get("voice") or "").strip()
        if current in ("", "en-US-AriaNeural"):
            edge["voice"] = desired_voice
            save_config(cfg)
            log.info(
                "TTS voice auto-configured to %s (system locale: Chinese)",
                desired_voice,
            )
    except Exception as e:
        log.warning("failed to auto-configure TTS voice: %s", e)


def _warm_docling_async(log: logging.Logger) -> None:
    """Optionally warm Docling in the background.

    Disabled by default because Docling/PyTorch initialization can leave global
    dispatcher state behind after failed imports; user-triggered reads run on the
    serialized Docling thread instead.
    """
    global _docling_warm_thread
    if os.environ.get("HERMESDESK_DOCLING_WARMUP", "0").strip().lower() not in ("1", "true", "yes", "on"):
        log.info("Docling warmup disabled; set HERMESDESK_DOCLING_WARMUP=1 to enable")
        return

    def _worker() -> None:
        t0 = time.monotonic()
        try:
            from tools.document_tools import warm_docling_converter

            info = warm_docling_converter()
            log.info(
                "Docling warmup ok in %.0fms artifacts=%s converter=%s",
                (time.monotonic() - t0) * 1000,
                info.get("artifacts_path") or "(default)",
                info.get("converter") or "?",
            )
        except Exception as exc:
            log.warning("Docling warmup failed after %.0fms: %s", (time.monotonic() - t0) * 1000, exc)

    _docling_warm_thread = threading.Thread(target=_worker, name="docling-warmup", daemon=True)
    _docling_warm_thread.start()


def _wait_for_docling_warmup(log: logging.Logger, timeout_seconds: float = 120.0) -> None:
    """Avoid concurrent torch imports from Docling warmup and desk tool discovery."""
    if _docling_warm_thread is None or not _docling_warm_thread.is_alive():
        return
    log.info("waiting for Docling warmup before desk tool discovery")
    _docling_warm_thread.join(timeout=timeout_seconds)
    if _docling_warm_thread.is_alive():
        log.warning(
            "Docling warmup still running after %.0fs; starting desk warm anyway",
            timeout_seconds,
        )


def _wire_local_stt(log: logging.Logger) -> None:
    """Auto-configure ``HERMES_LOCAL_STT_COMMAND`` to use the bundled whisper.cpp.

    HermesDesk ships ``stt-bin/whisper-cli.exe`` + ``stt-bin/ffmpeg.exe`` and a
    ``stt_wrapper.py`` translator alongside this entrypoint (see
    ``python/build_bundle.ps1`` step 6b). When present, we point Hermes'
    ``local_command`` STT path at the wrapper so transcription works
    out-of-the-box without an API key — the user only sees a one-time prompt
    to lazy-download the ~57 MB GGML model on first mic click.

    Honours an existing override: if ``HERMES_LOCAL_STT_COMMAND`` is already
    set (power user pointing at a system-wide whisper install) we leave it
    alone.
    """
    if os.environ.get("HERMES_LOCAL_STT_COMMAND", "").strip():
        log.info("HERMES_LOCAL_STT_COMMAND already set; skipping auto-wire")
        return

    here = Path(__file__).resolve().parent
    wrapper = here / "stt_wrapper.py"
    bin_dir = here / "stt-bin"
    whisper_cli = bin_dir / "whisper-cli.exe"
    if not wrapper.is_file() or not whisper_cli.is_file():
        log.info("local STT wrapper or binaries missing (wrapper=%s exists=%s, whisper=%s exists=%s); leaving HERMES_LOCAL_STT_COMMAND unset",
                 wrapper, wrapper.is_file(), whisper_cli, whisper_cli.is_file())
        return

    # Double-quote the python.exe + script paths so Windows cmd.exe (Hermes
    # runs the command via shell=True) parses them as single argv items even
    # when the install path has spaces. Hermes shlex-quotes each placeholder
    # value before substituting; the wrapper strips surrounding quotes back
    # off so paths like 'C:\\Users\\X 1\\Temp\\foo.webm' survive the round
    # trip.
    template = (
        f'"{sys.executable}" "{wrapper}" '
        f'{{input_path}} {{output_dir}} {{language}} {{model}}'
    )
    os.environ["HERMES_LOCAL_STT_COMMAND"] = template
    # Default language: auto-detect for most users, but force "zh" when the
    # Windows display language is Chinese so Whisper outputs simplified
    # characters instead of traditional.
    default_lang = "auto"
    if sys.platform == "win32":
        import ctypes

        try:
            # GetUserDefaultUILanguage returns a LANGID; 0x0804 = zh-CN, 0x0404 = zh-TW, 0x0C04 = zh-HK
            lang_id = ctypes.windll.kernel32.GetUserDefaultUILanguage()
            # Primary language ID is the lower 10 bits
            primary_lang = lang_id & 0x3FF
            if primary_lang == 0x04:  # LANG_CHINESE
                default_lang = "zh"
        except Exception:
            pass
    else:
        try:
            import locale

            loc = locale.getlocale()[0] or ""
            if loc.lower().startswith("zh"):
                default_lang = "zh"
        except Exception:
            pass
    os.environ.setdefault("HERMES_LOCAL_STT_LANGUAGE", default_lang)
    log.info("HERMES_LOCAL_STT_COMMAND -> bundled whisper.cpp (%s), lang=%s", whisper_cli, default_lang)

    # Add stt-bin to PATH so Hermes' _find_ffmpeg_binary() (called by
    # _prepare_local_audio before the local_command template runs) can
    # locate the bundled ffmpeg.exe. Without this, non-WAV browser
    # recordings (WebM/Opus) fail with "ffmpeg not found" even though
    # stt_wrapper.py has its own copy — the core pre-conversion runs first.
    ffmpeg_in_bin = bin_dir / "ffmpeg.exe"
    if ffmpeg_in_bin.is_file() and str(bin_dir) not in os.environ.get("PATH", ""):
        os.environ["PATH"] = str(bin_dir) + os.pathsep + os.environ.get("PATH", "")
        log.info("PATH += %s (for bundled ffmpeg)", bin_dir)


def _redirect_kabuqina_home() -> Path:
    """Resolve Kabuqina's config/cache root inside the per-user data dir.

    The desktop shell owns this location instead of writing to the profile
    root. Rust selects it once and injects both home env names before this
    child starts. Direct standalone runs retain the old-only atomic migration
    fallback; shipped children never make an independent migration decision.

      * uninstall is clean (one folder to delete),
      * the workspace jail can keep ``~/`` opaque,
      * profile separation per Windows user is automatic.

    Set the env var BEFORE overlays import anything that touches
    ``kabuqina_constants`` or ``kabuqina_cli.config``.
    """
    data_dir = Path(get_kabuqina_env("KABUQINA_DATA_DIR", "."))
    home = resolve_child_home(data_dir, logger=logging.getLogger("kabuqina.entry"))
    home.mkdir(parents=True, exist_ok=True)
    export_home(home)
    return home


def _wire_sys_path() -> None:
    """Make overlays, the bundled core, and site-packages importable.

    The bundled layout under ``HERMESDESK_BUNDLE_DIR`` is::

        runtime/
            desktop_entrypoint.py     <- this file
            overlays/                 <- our monkey patches
            kabuqina/                 <- Kabuqina-owned agent core
                kabuqina_cli/
                agent/
                tools/
                ...
            site-packages/            <- pip-installed deps (httpx, fastapi, ...)
            python/                   <- embedded CPython

    Python auto-adds the script's directory (``runtime/``) to ``sys.path[0]``
    when launched as ``python.exe runtime\\desktop_entrypoint.py``, which
    makes ``overlays`` importable. The core and ``site-packages/`` need
    to be added manually — the build does ship a ``.pth`` shim, but the
    relative paths in it are fragile across dev vs bundled layouts. Doing
    it here makes the launcher self-contained.
    """
    here = Path(__file__).resolve().parent
    # ``hermes`` remains a one-release fallback for already-built runtimes.
    for sub in ("kabuqina", "hermes", "site-packages"):
        p = here / sub
        if p.is_dir():
            sys.path.insert(0, str(p))
    # Package ``helpers`` lives at ``runtime/helpers/``; parent must be on path.
    if (here / "helpers").is_dir():
        sys.path.insert(0, str(here))


def _verify_bundle_deps(log: logging.Logger) -> None:
    """Fail fast if ``build_bundle.ps1`` did not populate ``site-packages`` (or deps are broken).

    Common causes:
      * Never ran ``python\\build_bundle.ps1`` → empty ``site-packages``.
      * Inherited ``PYTHONPATH`` from the parent shell shadowing real PyYAML
        (Tauri now strips it; devs should avoid exporting a bogus ``yaml``).
      * Wrong PyPI package named ``yaml`` installed instead of ``PyYAML``.
    """
    here = Path(__file__).resolve().parent
    sp = here / "site-packages"
    if not sp.is_dir() or not (sp / "yaml").exists():
        log.error(
            "Bundle site-packages missing PyYAML layout under %s. "
            "From the repo root run: .\\python\\build_bundle.ps1",
            sp,
        )
        raise SystemExit(4)
    try:
        import yaml as _yaml  # type: ignore[no-redef]
    except ImportError as e:
        log.error("Cannot import yaml: %s. Re-run .\\python\\build_bundle.ps1", e)
        raise SystemExit(4) from e
    if not hasattr(_yaml, "safe_load"):
        log.error(
            "Broken `yaml` module at %s (expected PyYAML with safe_load). "
            "Remove conflicting PyPI package `yaml` / clear PYTHONPATH, then rebuild bundle.",
            getattr(_yaml, "__file__", "?"),
        )
        raise SystemExit(4)
    try:
        import fastapi  # noqa: F401
        import uvicorn  # noqa: F401
    except ImportError as e:
        log.error(
            "fastapi/uvicorn missing from bundle: %s. Re-run .\\python\\build_bundle.ps1",
            e,
        )
        raise SystemExit(4)


def main() -> int:
    normalize_kabuqina_env()
    _setup_logging()
    log = logging.getLogger("kabuqina.entry")
    boot_t0 = time.monotonic()
    log.info("starting Kabuqina Python (pid=%d)", os.getpid())

    # Mark this process as an interactive session BEFORE any Hermes import.
    # Upstream gates two distinct behaviors on HERMES_INTERACTIVE:
    #   1. ``cronjob_tools.check_cronjob_requirements`` — without it, the
    #      ``cronjob`` tool is filtered out of the agent's tool list
    #      (registry.py: check_fn returns False → continue).
    #   2. ``approval.check_dangerous_command`` — without it, dangerous
    #      shell commands auto-approve and never reach our Tauri modal.
    # The HermesDesk /chat surface IS interactive (a real human at the
    # keyboard sees and responds to dialogs), so this is correct.
    os.environ.setdefault("HERMES_INTERACTIVE", "1")

    _wire_sys_path()
    t_deps = time.monotonic()
    _verify_bundle_deps(log)
    _prime_torch_main_thread(log)
    kabuqina_home = _redirect_kabuqina_home()
    log.info("KABUQINA_HOME -> %s", kabuqina_home)
    try:
        from gateway_env_loader import ensure_gateway_env_loaded

        ensure_gateway_env_loaded()
    except Exception:
        log.exception("failed to load kabuqina-home .env for messaging/cron delivery")
    try:
        from desktop_timezone import apply_desktop_timezone

        apply_desktop_timezone(kabuqina_home)
    except Exception:
        log.exception("failed to apply desktop timezone")
    _wire_local_stt(log)
    _wire_tts_voice(log)
    log.info("boot timing deps_ms=%.0f", (time.monotonic() - t_deps) * 1000)

    # 0. Contract version check.  Must match the Tauri shell's expectation.
    from desktop_contract import CONTRACT_VERSION as _EXPECTED_CONTRACT

    _got = int(os.environ.get("HERMESDESK_CONTRACT_VERSION", "0"))
    if _got != _EXPECTED_CONTRACT:
        log.error(
            "Contract version mismatch: Tauri shell sent v%d, Python expects v%d. "
            "Rebuild the Python bundle (python/build_bundle.ps1) so the bundled "
            "kabuqina_cli matches the Tauri shell's contract.",
            _got, _EXPECTED_CONTRACT,
        )
        return 5

    # 0b. Build typed bootstrap config (Phase 2 — no behavior change yet).
    # Phase 3 policy objects will consume this instead of raw env vars.
    from desktop_config import from_env

    cfg = from_env()
    log.info(
        "DesktopConfig: mode=%s provider=%s llm_host=%s workspace=%s desk_minimal=%s",
        cfg.runtime_mode.value, cfg.provider, cfg.llm_host, cfg.workspace, cfg.desk_minimal,
    )

    # 1. Overlays first.
    t_overlays = time.monotonic()
    try:
        from overlays import apply_all
    except ImportError:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from overlays import apply_all  # type: ignore[no-redef]
    apply_all()
    log.info("boot timing overlays_ms=%.0f", (time.monotonic() - t_overlays) * 1000)
    _warm_docling_async(log)

    # 1a. The desktop child is the sole recovery owner. Tauri does not start
    # Gateway children until this process writes its port handshake, and the
    # coordinator's OS liveness lock prevents takeover from any writer process
    # that is still alive. Failures leave the durable fence/journal intact.
    from learning_recovery import (
        LearningRecoveryRunner,
        recover_learning_operations_once,
    )

    try:
        recover_learning_operations_once()
    except BaseException as exc:
        log.warning(
            "startup learning recovery deferred reason=%s",
            getattr(exc, "reason_code", type(exc).__name__),
        )
    _learning_recovery_runner = LearningRecoveryRunner()
    _learning_recovery_runner.start()

    # 1b. Eager-load real ``gateway.session_context`` so ``tools/approval`` + terminal
    #     use ContextVar state (not a stale stub left in sys.modules).
    try:
        import importlib

        importlib.import_module("gateway.session_context")
        log.info("gateway.session_context import ok")
    except Exception as e:
        log.warning("gateway.session_context import failed: %s", e)

    # 2. Import desk_server before the port handshake. Import creates session state
    #    (SESSION_TOKEN mirrored to `hermes_web_session_token.txt`) that the Tauri
    #    shell reads once `port.txt` is visible.
    t_web = time.monotonic()
    try:
        import desk_server  # type: ignore
    except Exception:
        log.exception("failed to import desk_server; aborting")
        return 3
    log.info("boot timing desk_server_import_ms=%.0f", (time.monotonic() - t_web) * 1000)

    # Main agent must know about Kabuqina power-user mode (terminal/code/MoA gated off by default).
    try:
        try:
            from overlays.desk_system_prompt import install as _desk_system_prompt_install
        except ImportError:
            # Dev layout: `overlays/` lives under `python/`, not `python/src/`.
            _root = str(Path(__file__).resolve().parent.parent)
            if _root not in sys.path:
                sys.path.insert(0, _root)
            from overlays.desk_system_prompt import install as _desk_system_prompt_install
        _desk_system_prompt_install()
    except Exception as e:
        log.warning("desk_system_prompt install: %s", e)

    # 2b. Re-run approval bridge install now that `hermes/` is on sys.path.
    #     The first install (overlay #7) ran before _wire_sys_path(), so
    #     send_message_tool / cronjob_tools were not importable yet.
    #     This second call wraps the messaging + cron tool handlers with
    #     Tauri approval dialogs.
    try:
        from overlays import approval_bridge as _ab
    except ImportError:
        _ab = None
    if _ab is not None:
        _ab.install()
        log.info("approval bridge re-installed (post sys.path)")

    # 2b'. Same story for cron desktop delivery: cron.scheduler only becomes
    #      importable after _wire_sys_path(), so the first install attempt
    #      from apply_all() is a no-op. Re-run here.
    try:
        from overlays import cron_desktop_delivery as _cdd
    except ImportError:
        _cdd = None
    if _cdd is not None:
        _cdd.install()
        log.info("cron desktop-delivery overlay re-installed (post sys.path)")

    # 2b''. Same story for retain-completed (one-shot job history).
    try:
        from overlays import cron_retain_completed as _crc
    except ImportError:
        _crc = None
    if _crc is not None:
        _crc.install()
        log.info("cron retain-completed overlay re-installed (post sys.path)")

    # 2c. Register "desktop" as a virtual platform so upstream cron delivery
    #     can resolve it (Platform._missing_ → platform_registry).
    try:
        from gateway.platform_registry import platform_registry, PlatformEntry

        _desktop_entry = PlatformEntry(
            name="desktop",
            label="Desktop (local)",
            adapter_factory=lambda config: None,  # delivery uses _DesktopDeliveryAdapter in cron runner
            check_fn=lambda: True,
            emoji="🖥️",
        )
        platform_registry.register(_desktop_entry)
        log.info("desktop platform registered in platform_registry")
    except Exception as e:
        log.warning("failed to register desktop platform: %s", e)

    # Mirror SPA session token for the Tauri shell (reads same path as ``paths::ensure_data_dir``).
    # desk_server generates SESSION_TOKEN at import; we mirror it here for the Tauri shell.
    _dd = (os.environ.get("HERMESDESK_DATA_DIR") or "").strip()
    if _dd:
        try:
            tok = getattr(desk_server, "SESSION_TOKEN", None) or getattr(desk_server, "_SESSION_TOKEN", None)
            if tok:
                p = Path(_dd) / "hermes_web_session_token.txt"
                p.write_text(str(tok), encoding="utf-8")
                log.info("wrote %s (len=%d)", p, len(str(tok)))
        except OSError as e:
            log.warning("hermes_web_session_token.txt: %s", e)

    # 3. Pick port and tell Tauri.
    port = _free_port()
    _write_handshake(port)
    log.info("bound port %d, handshake written (boot timing port_write_ms=%.0f)", port, (time.monotonic() - boot_t0) * 1000)

    if cfg.desk_minimal:
        _wait_for_docling_warmup(log)
        desk_server.start_desk_warm_background()

    # 3b. Start the cron scheduler ticker in a daemon thread so scheduled
    #     jobs fire even without the gateway process.
    #     The ticker waits 60 s before its first tick (web server startup).
    try:
        from cron_scheduler_runner import CronSchedulerRunner

        _cron_runner = CronSchedulerRunner()
        _cron_runner.start()
    except Exception:
        log.exception("failed to start cron ticker (scheduled tasks unavailable)")

    # Kabuqina desk API: desk_server.start_server(host, port, open_browser=False)
    runner = (
        getattr(desk_server, "start_server", None)
        or getattr(desk_server, "run", None)
        or getattr(desk_server, "main", None)
    )
    if runner is None:
        log.error(
            "no start_server()/run()/main() entry in desk_server; "
            "check desk_server package"
        )
        return 4

    try:
        # Try a few common signatures so we tolerate small upstream churn.
        # Prefer no auto-open browser: HermesDesk shell is the main UI; OS browser is confusing noise.
        for attempt in (
            lambda: runner(host="127.0.0.1", port=port, open_browser=False),
            lambda: runner("127.0.0.1", port, False),
            lambda: runner(port=port),
        ):
            try:
                return int(attempt() or 0)
            except TypeError:
                continue
        # Last resort: argv-style.
        old_argv = sys.argv[:]
        sys.argv = ["hermes-web", "--host", "127.0.0.1", "--port", str(port)]
        try:
            return int(runner() or 0)
        finally:
            sys.argv = old_argv
    except KeyboardInterrupt:
        log.info("interrupt received; shutting down")
        return 0


if __name__ == "__main__":
    sys.exit(main())
