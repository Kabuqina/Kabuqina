# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Desk voice/STT/TTS routes."""
from __future__ import annotations
import asyncio, base64, json, logging, os, tempfile, traceback
from typing import Any, Dict, List, Optional, Tuple
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from kabuqina_cli.config import load_config, save_config, save_env_value
from desk_server.voice_helpers import *
log = logging.getLogger(__name__)
router = APIRouter()

_DESK_VOICE_ENV_ALLOWED = frozenset({
    "GROQ_API_KEY",
    "VOICE_TOOLS_OPENAI_KEY",
    "OPENAI_API_KEY",
    "MISTRAL_API_KEY",
    "XAI_API_KEY",
    "HERMES_LOCAL_STT_COMMAND",
    "HERMES_LOCAL_STT_LANGUAGE",
    "ELEVENLABS_API_KEY",
    "MINIMAX_API_KEY",
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
})

_DESK_VOICE_PROVIDER_ALLOWED = {
    "stt": frozenset({"local", "local_command", "groq", "openai", "mistral", "xai"}),
    "tts": frozenset({
        "edge", "elevenlabs", "openai", "xai", "minimax", "mistral",
        "gemini", "neutts", "kittentts", "piper",
    }),
}

@router.post("/api/desk/transcribe")
async def desk_transcribe(request: Request):
    """HermesDesk: transcribe audio to text using the configured STT provider.

    Request JSON: audio_b64 (base64-encoded audio), mime (MIME type string).
    Response JSON: {"transcript": "..."} on success.

    Data flow: the Rust shell POSTs raw base64 here; this handler decodes it,
    writes a temporary file, runs the synchronous transcribe_audio() in a
    thread-pool executor (to avoid blocking the event loop), then cleans up.

    The entire handler stays inside ``try``/``except`` so HermesDesk never leaks
    Starlette's plain-text ``Internal Server Error`` response (which Rust
    cannot parse as JSON).
    """
    tmp_path: Optional[str] = None
    try:
        from tools.transcription_tools import (
            _get_provider,
            _load_stt_config,
            is_stt_enabled,
            transcribe_audio,
        )

        ensure_bundled_local_stt_env()
        ensure_default_stt_provider()

        if not is_stt_enabled():
            return JSONResponse(
                {
                    "error": "stt_not_configured",
                    "detail": "请在设置中配置语音识别服务（Groq / OpenAI 等）。",
                },
                status_code=400,
            )

        try:
            body = await request.json()
        except Exception:
            return JSONResponse(
                {"error": "invalid_json", "detail": "Invalid JSON body"},
                status_code=400,
            )

        if not isinstance(body, dict):
            return JSONResponse({"error": "invalid_body"}, status_code=400)

        audio_b64 = (body.get("audio_b64") or "").strip()
        mime = (body.get("mime") or "audio/webm").strip()

        if not audio_b64:
            return JSONResponse({"error": "missing_audio_b64"}, status_code=400)

        try:
            audio_bytes = base64.b64decode(audio_b64)
        except Exception as exc:
            return JSONResponse(
                {"error": "invalid_base64", "detail": str(exc)}, status_code=400
            )

        _EXT_MAP = {
            "audio/webm": ".webm",
            "audio/ogg": ".ogg",
            "audio/mp4": ".mp4",
            "audio/mpeg": ".mp3",
            "audio/wav": ".wav",
            "audio/x-wav": ".wav",
        }
        base_mime = mime.split(";")[0].strip()
        ext = _EXT_MAP.get(base_mime, ".webm")

        stt_cfg = _load_stt_config()
        resolved = _get_provider(stt_cfg)

        if resolved == "none":
            return JSONResponse(
                {
                    "error": "no_stt_provider",
                    "detail": (
                        "未检测到可用的语音识别后端。请在 kabuqina-home/.env 或控制台 Keys 中配置 "
                        "GROQ_API_KEY、OPENAI_API_KEY（或 VOICE_TOOLS_OPENAI_KEY）、MISTRAL_API_KEY、"
                        "XAI_API_KEY 之一，或运行 python/build_bundle.ps1 打入 whisper.cpp 本地转写。"
                    ),
                },
                status_code=400,
            )

        tmp_parent: Optional[str] = None
        dvp = desk_voice_paths_mod()
        if dvp is not None:
            vtmp = dvp.workspace_voice_tmp_dir()
            if vtmp is not None:
                vtmp.mkdir(parents=True, exist_ok=True)
                tmp_parent = str(vtmp)
        with tempfile.NamedTemporaryFile(
            suffix=ext, prefix="hermesdesk_stt_", delete=False, dir=tmp_parent
        ) as tmp_file:
            tmp_file.write(audio_bytes)
            tmp_path = tmp_file.name

        loop = asyncio.get_running_loop()
        result: dict = await loop.run_in_executor(None, transcribe_audio, tmp_path)

        if not result.get("success"):
            err = result.get("error") or "transcription_failed"
            err_text = str(err)
            log.warning("desk transcribe: STT failed: %s", err_text)
            if "STT_MODEL_MISSING" in err_text:
                return JSONResponse(
                    {
                        "error": "stt_model_missing",
                        "detail": "本地语音识别模型尚未下载，请先点击下载（约 60 MB）。",
                    },
                    status_code=400,
                )
            return JSONResponse(
                {"error": "transcription_failed", "detail": err_text},
                status_code=500,
            )

        transcript = (result.get("transcript") or "").strip()
        return JSONResponse({"transcript": transcript})

    except Exception as exc:
        log.exception("desk transcribe: unexpected error")
        return JSONResponse(
            {
                "error": "transcribe_internal",
                "detail": f"{type(exc).__name__}: {exc}",
            },
            status_code=500,
        )
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

@router.post("/api/desk/save-voice-setup")
async def desk_save_voice_setup(request: Request):
    """HermesDesk: persist STT/TTS provider choice + secrets from the wizard.

    Request JSON: ``{section: "stt"|"tts", provider: str|null, env: {KEY: VALUE, ...}}``

    - ``provider`` (when non-null) is written to ``config.yaml`` at
      ``<section>.provider``; a value of ``null`` leaves the existing setting
      untouched (e.g. user picked "skip").
    - ``env`` entries are written via ``save_env_value`` (which both updates
      ``kabuqina-home/.env`` on disk and refreshes ``os.environ`` so the running
      process picks them up without a restart). Keys outside an internal
      allow-list are silently dropped; empty values are skipped (we never
      accidentally clear a saved key with a blank field).
    """
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")
    if not isinstance(body, dict):
        return JSONResponse({"error": "invalid_body"}, status_code=400)

    section = (body.get("section") or "").strip()
    if section not in ("stt", "tts"):
        return JSONResponse({"error": "invalid_section"}, status_code=400)

    provider_raw = body.get("provider")
    provider: Optional[str] = None
    if isinstance(provider_raw, str):
        cand = provider_raw.strip()
        if cand:
            if cand not in _DESK_VOICE_PROVIDER_ALLOWED[section]:
                return JSONResponse(
                    {"error": "invalid_provider", "detail": cand},
                    status_code=400,
                )
            provider = cand

    env = body.get("env") or {}
    if not isinstance(env, dict):
        return JSONResponse({"error": "invalid_env"}, status_code=400)

    saved_env: List[str] = []
    for k_raw, v_raw in env.items():
        if not isinstance(k_raw, str) or not isinstance(v_raw, str):
            continue
        key = k_raw.strip()
        val = v_raw  # don't strip secret bodies; user might intentionally have leading/trailing whitespace
        if not key or not val:
            continue
        if key not in _DESK_VOICE_ENV_ALLOWED:
            continue
        try:
            save_env_value(key, val)
            saved_env.append(key)
        except Exception as exc:
            log.warning("save-voice-setup: save_env_value(%s) failed: %s", key, exc)

    saved_provider = False
    if provider:
        try:
            cfg = load_config()
            sect = cfg.setdefault(section, {})
            if not isinstance(sect, dict):
                sect = {}
                cfg[section] = sect
            sect["provider"] = provider
            save_config(cfg)
            saved_provider = True
        except Exception as exc:
            log.warning("save-voice-setup: save_config(%s.provider) failed: %s", section, exc)
            return JSONResponse(
                {"error": "save_config_failed", "detail": str(exc)},
                status_code=500,
            )

    return JSONResponse({
        "ok": True,
        "section": section,
        "saved_provider": saved_provider,
        "saved_env": saved_env,
    })
@router.post("/api/desk/tts")
async def desk_tts(request: Request):
    """HermesDesk: generate TTS audio for the given text.

    Returns the audio file directly (MP3). The caller (Tauri shell proxy)
    streams the bytes to the webview for playback.
    """
    import json
    from tools.tts_tool import text_to_speech_tool

    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")
    if not isinstance(body, dict):
        return JSONResponse({"error": "invalid_body"}, status_code=400)

    text = (body.get("text") or "").strip()
    if not text:
        return JSONResponse({"error": "text_required"}, status_code=400)

    # Run in thread pool -- text_to_speech_tool is synchronous
    result_str = await asyncio.to_thread(text_to_speech_tool, text=text)
    try:
        result = json.loads(result_str)
    except Exception:
        log.exception("desk_tts: failed to parse tool result")
        return JSONResponse({"error": "parse_failed"}, status_code=500)

    if not result.get("success"):
        err = result.get("error", "tts_failed")
        return JSONResponse({"ok": False, "error": err}, status_code=500)

    file_path = result["file_path"]
    if not os.path.isfile(file_path):
        return JSONResponse({"error": "file_not_found"}, status_code=500)

    return FileResponse(file_path, media_type="audio/mpeg")
@router.get("/api/desk/stt-model/status")
async def desk_stt_model_status():
    """Report whether the local STT model is downloaded.

    Frontend calls this before recording so it can prompt the user to
    download once. Returns ``downloaded`` and ``size`` so the UI can also
    show a stale/corrupt-file warning if the size is way off.
    """
    path, downloaded = desk_stt_model_resolved()
    if not downloaded:
        return JSONResponse({
            "downloaded": False,
            "size": 0,
            "path": str(path),
        })
    try:
        st = path.stat()
        return JSONResponse({
            "downloaded": True,
            "size": int(st.st_size),
            "path": str(path),
        })
    except OSError as exc:
        return JSONResponse(
            {"error": "stat_failed", "detail": str(exc)},
            status_code=500,
        )


@router.post("/api/desk/stt-model/download")
async def desk_stt_model_download():
    """Download the local STT model (one-shot; idempotent if already present).

    Returns ``{ "ok": true, "size": ..., "path": ... }`` on success or
    ``{ "error": "...", "detail": "..." }`` with a 500 on failure. The
    download itself runs in the default thread-pool executor so the FastAPI
    event loop stays responsive.
    """
    import traceback

    try:
        dest = desk_stt_model_path()
        # region agent log
        agent_dbg_stt(
            {
                "hypothesisId": "H4",
                "location": "desk_stt_model_download:entry",
                "message": "POST /api/desk/stt-model/download",
                "data": {"dest": str(dest), "exists": dest.exists()},
            }
        )
        # endregion
        if dest.exists():
            try:
                size = dest.stat().st_size
            except OSError:
                size = 0
            return JSONResponse({"ok": True, "size": size, "path": str(dest), "already": True})

        if not DESK_STT_MODEL_SHA256:
            log.warning(
                "stt-model download proceeding without SHA-256 verification "
                "(DESK_STT_MODEL_SHA256 not pinned); set it before shipping."
            )

        try:
            loop = asyncio.get_running_loop()
            # region agent log
            agent_dbg_stt(
                {
                    "hypothesisId": "H4",
                    "location": "desk_stt_model_download:before_executor",
                    "message": "scheduling run_in_executor",
                    "data": {},
                }
            )
            # endregion
            ok, info = await loop.run_in_executor(None, download_stt_model_blocking, dest)
        except Exception as exc:
            tb = traceback.format_exc()
            # region agent log
            agent_dbg_stt(
                {
                    "hypothesisId": "H3",
                    "location": "desk_stt_model_download:executor_exception",
                    "message": "run_in_executor raised; return JSON instead of plain 500",
                    "data": {
                        "type": type(exc).__name__,
                        "detail": repr(exc),
                        "traceback": tb[:6000],
                    },
                }
            )
            # endregion
            log.exception("stt-model download: executor failed")
            return JSONResponse(
                {
                    "error": "stt_model_download_executor_failed",
                    "detail": f"{type(exc).__name__}: {exc}",
                },
                status_code=500,
            )

        # region agent log
        agent_dbg_stt(
            {
                "hypothesisId": "H5",
                "location": "desk_stt_model_download:after_executor",
                "message": "executor returned",
                "data": {
                    "ok": ok,
                    "info_keys": list(info.keys()) if isinstance(info, dict) else "n/a",
                },
            }
        )
        # endregion
        if not ok:
            return JSONResponse(info, status_code=500)
        body = {"ok": True, **info}
        return JSONResponse(body)
    except Exception as exc:
        tb = traceback.format_exc()
        # region agent log
        agent_dbg_stt(
            {
                "hypothesisId": "H5",
                "location": "desk_stt_model_download:outer_exception",
                "message": "unexpected failure in handler",
                "data": {
                    "type": type(exc).__name__,
                    "detail": repr(exc),
                    "traceback": tb[:6000],
                },
            }
        )
        # endregion
        log.exception("stt-model download handler failed")
        return JSONResponse(
            {
                "error": "stt_model_download_internal",
                "detail": f"{type(exc).__name__}: {exc}",
            },
            status_code=500,
        )
