# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Desk chat HTTP routes."""
from __future__ import annotations
import asyncio, json, logging, queue, threading, time, uuid
from typing import Any, Dict
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from desk_server.chat_core import (
    _desk_active_agents,
    _desk_active_lock,
    _desk_build_user_message,
    _desk_chat_build_agent,
    _desk_chat_run_in_thread,
    _desk_extract_reply_text,
    _desk_normalize_history_message,
    _desk_parse_attachments_from_body,
    _desk_prepare_active_agent,
    _desk_progress_response,
    _desk_slash_response,
    _desk_text_from_assistant_messages,
)
from desk_server.interactions import interaction_manager
from desk_server.warm import start_auto_load_packages_after_first_chat, warming_http_response
log = logging.getLogger(__name__)
router = APIRouter()


@router.post("/api/desk/interaction-response")
async def desk_interaction_response(request: Request):
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")
    if not isinstance(body, dict):
        return JSONResponse({"ok": False, "error": "invalid_body"}, status_code=400)

    session_id = str(body.get("session_id") or "").strip()
    interaction_id = str(body.get("interaction_id") or "").strip()
    action = str(body.get("action") or "").strip()
    text = str(body.get("text") or "")
    data = body.get("data")
    if not isinstance(data, dict):
        data = {}
    if not session_id or not interaction_id or not action:
        return JSONResponse(
            {
                "ok": False,
                "error": "invalid_body",
                "detail": "session_id, interaction_id, and action are required",
            },
            status_code=400,
        )

    ok = interaction_manager.respond(
        session_id=session_id,
        interaction_id=interaction_id,
        action=action,
        text=text,
        data=data,
    )
    if not ok:
        return JSONResponse({"ok": False, "error": "interaction_not_found"}, status_code=404)
    return JSONResponse({"ok": True})


@router.post("/api/desk/stop")
async def desk_stop(request: Request):
    """Interrupt the agent for a desk chat session (best-effort)."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    session_id = (body.get("session_id") or "").strip() if isinstance(body, dict) else ""
    if not session_id:
        return JSONResponse({"ok": False, "error": "missing_session_id"}, status_code=400)
    with _desk_active_lock:
        ag = _desk_active_agents.get(session_id)
    if ag is not None:
        try:
            ag.interrupt("User requested stop from HermesDesk")
        except Exception as e:
            log.warning("desk stop: interrupt failed: %s", e)
        return JSONResponse({"ok": True, "interrupted": True})
    return JSONResponse({"ok": True, "interrupted": False, "detail": "no active agent for this session"})


@router.get("/api/desk/chat-preview/{session_id}")
async def desk_chat_preview(session_id: str, since: int = 0):
    """Return agent progress for the given session (lightweight poll target).

    Query: `since` — only return tool events with seq > since (frontend cursor).
    Response shape::

        {
            running: bool, status: str, iteration: int, max_iterations: int,
            current_tool: str|None, error: str|None,
            events: [{seq, kind, tool, preview, duration, is_error, ts}, ...],
            next_seq: int,
        }
    """
    with _desk_active_lock:
        ag = _desk_active_agents.get(session_id)
    if ag is None:
        return JSONResponse({
            "running": False, "status": "inactive",
            "events": [], "next_seq": 0,
        })
    progress = _desk_progress_response(ag, since=since)
    if not progress.get("running"):
        with _desk_active_lock:
            _desk_active_agents.pop(session_id, None)
    return JSONResponse(progress)


def _desk_sse(payload: Dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False, separators=(',', ':'))}\n\n"


def _desk_slash_streaming_response(payload: Dict[str, Any]) -> StreamingResponse:
    async def event_generator():
        session_id = payload.get("session_id")
        yield _desk_sse({"type": "start", "session_id": session_id})
        yield _desk_sse({"type": "final", **payload})
        yield _desk_sse({"type": "done", "session_id": session_id})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/api/desk/chat-stream")
async def desk_chat_stream(request: Request):
    """HermesDesk: stream a real AIAgent turn as SSE events."""
    warming = warming_http_response()
    if warming is not None:
        return warming
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")
    if not isinstance(body, dict):
        return JSONResponse({"ok": False, "error": "invalid_body"}, status_code=400)
    message = (body.get("message") or "").strip()
    atts = _desk_parse_attachments_from_body(body)
    built = _desk_build_user_message(message, atts)
    if built is None:
        return JSONResponse(
            {"ok": False, "error": "empty_message", "detail": "message and attachments are both empty"},
            status_code=400,
        )
    user_payload, persist_um = built
    session_id = (body.get("session_id") or "").strip() or str(uuid.uuid4())
    request_started = time.monotonic()
    if not atts:
        slash_payload = _desk_slash_response(message, session_id)
        if slash_payload is not None:
            return _desk_slash_streaming_response(slash_payload)

    from hermes_state import SessionDB

    db = SessionDB()
    try:
        try:
            raw_history = db.get_messages_as_conversation(session_id)
        except Exception as e:
            log.exception("desk stream: load history failed")
            db.close()
            return JSONResponse({"ok": False, "error": "session_db", "detail": str(e)}, status_code=500)
        history = [
            _desk_normalize_history_message(m)
            for m in raw_history
            if m.get("role") != "session_meta"
        ]

        try:
            agent = _desk_chat_build_agent(session_id, db)
        except ValueError as e:
            db.close()
            return JSONResponse({"ok": False, "error": "config", "detail": str(e)}, status_code=503)
        except Exception as e:
            log.exception("desk stream: agent init failed")
            db.close()
            return JSONResponse({"ok": False, "error": "agent_init", "detail": str(e)}, status_code=500)

        agent_ready_at = time.monotonic()

        event_q: "queue.Queue[Dict[str, Any]]" = queue.Queue()
        _recv_len = len(message) + sum(len(p.get("data") or b"") for p in atts)
        timing: Dict[str, Any] = {"first_delta_at": None}

        def emit(payload: Dict[str, Any]) -> None:
            payload.setdefault("session_id", session_id)
            event_q.put(payload)

        def on_delta(delta: Any) -> None:
            if isinstance(delta, str) and delta:
                if timing["first_delta_at"] is None:
                    timing["first_delta_at"] = time.monotonic()
                emit({"type": "delta", "text": delta})
            elif delta is None:
                emit({"type": "boundary"})

        _desk_prepare_active_agent(
            session_id,
            agent,
            stream_delta_callback=on_delta,
            progress_event_callback=emit,
        )

        def worker() -> None:
            turn_succeeded = False
            try:
                log.info(
                    "desk stream: session=%s user_chars~%d history_msgs=%d attachments=%d",
                    session_id, _recv_len, len(history), len(atts),
                )
                payload = _desk_chat_run_in_thread(
                    agent,
                    user_payload,
                    history,
                    session_id,
                    persist_um,
                    stream_delta_callback=on_delta,
                    progress_event_callback=emit,
                )
                result = (payload or {}).get("result") or {}
                final_text = _desk_extract_reply_text(result)
                if not final_text:
                    try:
                        db_msgs = db.get_messages_as_conversation(session_id)
                        final_text = _desk_text_from_assistant_messages(db_msgs)
                    except Exception:
                        log.debug("desk stream: could not re-read session messages for reply text", exc_info=True)

                ft = (final_text or "").strip()
                if ft in ("(empty)",):
                    ft = ""
                if not ft and isinstance(result, dict):
                    emit({
                        "type": "error",
                        "ok": False,
                        "error": "empty_model_response",
                        "detail": (
                            "The model returned no visible text this turn -- "
                            "check your API key, model ID, and network in Settings."
                        ),
                        "received_chars": max(1, _recv_len),
                    })
                    return

                _agent_model = getattr(agent, "model", "") or ""
                _result_model = ((payload or {}).get("result") or {}).get("model") or ""
                _effective_model = _agent_model or _result_model
                emit({
                    "type": "final",
                    "ok": True,
                    "proto": False,
                    "final_response": ft,
                    "received_chars": max(1, _recv_len),
                    "preview": (ft[:500] + "..." if len(ft) > 500 else ft) if ft else "",
                    "prompt_tokens": int((payload or {}).get("prompt_tokens") or 0),
                    "completion_tokens": int((payload or {}).get("completion_tokens") or 0),
                    "model": _effective_model,
                })
                turn_succeeded = True
                finished_at = time.monotonic()
                first_delta_at = timing.get("first_delta_at")
                log.info(
                    "desk stream timing: session=%s new_session=%s agent_init_ms=%.0f "
                    "ttft_ms=%s total_ms=%.0f prompt_chars=%d input=%d output=%d "
                    "cache_read=%d cache_write=%d",
                    session_id,
                    not history,
                    (agent_ready_at - request_started) * 1000,
                    f"{(first_delta_at - request_started) * 1000:.0f}" if first_delta_at else "none",
                    (finished_at - request_started) * 1000,
                    int((payload or {}).get("system_prompt_chars") or 0),
                    int((payload or {}).get("input_tokens") or 0),
                    int((payload or {}).get("output_tokens") or 0),
                    int((payload or {}).get("cache_read_tokens") or 0),
                    int((payload or {}).get("cache_write_tokens") or 0),
                )
            except Exception as e:
                log.exception("desk stream: run_conversation failed")
                emit({"type": "error", "ok": False, "error": "run_failed", "detail": str(e)})
            finally:
                try:
                    db.close()
                except Exception:
                    pass
                emit({"type": "done"})
                if turn_succeeded:
                    start_auto_load_packages_after_first_chat()

        threading.Thread(target=worker, daemon=True, name=f"desk-chat-stream-{session_id[:8]}").start()

        async def event_generator():
            yield _desk_sse({
                "type": "start",
                "session_id": session_id,
                "progress": _desk_progress_response(agent),
            })
            last_progress = ""
            while True:
                try:
                    item = await asyncio.to_thread(event_q.get, True, 0.25)
                except queue.Empty:
                    progress = _desk_progress_response(agent)
                    encoded_progress = json.dumps(progress, sort_keys=True, default=str)
                    if encoded_progress != last_progress:
                        last_progress = encoded_progress
                        yield _desk_sse({"type": "progress", "session_id": session_id, "progress": progress})
                    else:
                        yield ": keepalive\n\n"
                    continue
                yield _desk_sse(item)
                if item.get("type") == "done":
                    break

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )
    except Exception:
        try:
            db.close()
        except Exception:
            pass
        raise


@router.post("/api/desk/chat-proto")
async def desk_chat_proto(request: Request):
    """HermesDesk: run a real AIAgent turn (same credentials + workspace as CLI).

    Request JSON: message (text), session_id (optional, for multi-turn),
    attachments (optional) list of {name, mime, data} with data base64-encoded.
    """
    warming = warming_http_response()
    if warming is not None:
        return warming
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")
    if not isinstance(body, dict):
        return JSONResponse({"ok": False, "error": "invalid_body"}, status_code=400)
    message = (body.get("message") or "").strip()
    atts = _desk_parse_attachments_from_body(body)
    built = _desk_build_user_message(message, atts)
    if built is None:
        return JSONResponse(
            {"ok": False, "error": "empty_message", "detail": "message and attachments are both empty"},
            status_code=400,
        )
    user_payload, persist_um = built

    session_id = (body.get("session_id") or "").strip() or str(uuid.uuid4())
    if not atts:
        slash_payload = _desk_slash_response(message, session_id)
        if slash_payload is not None:
            return JSONResponse(slash_payload)

    from hermes_state import SessionDB

    db = SessionDB()
    try:
        try:
            raw_history = db.get_messages_as_conversation(session_id)
        except Exception as e:
            log.exception("desk chat: load history failed")
            return JSONResponse(
                {"ok": False, "error": "session_db", "detail": str(e)},
                status_code=500,
            )
        history = [
            _desk_normalize_history_message(m)
            for m in raw_history
            if m.get("role") != "session_meta"
        ]

        try:
            agent = _desk_chat_build_agent(session_id, db)
        except ValueError as e:
            return JSONResponse({"ok": False, "error": "config", "detail": str(e)}, status_code=503)
        except Exception as e:
            log.exception("desk chat: agent init failed")
            return JSONResponse({"ok": False, "error": "agent_init", "detail": str(e)}, status_code=500)

        _recv_len = len(message) + sum(len(p.get("data") or b"") for p in atts)
        log.info(
            "desk chat: session=%s user_chars~%d history_msgs=%d attachments=%d",
            session_id, _recv_len, len(history), len(atts),
        )
        try:
            _desk_prepare_active_agent(session_id, agent)
            payload = await asyncio.to_thread(
                _desk_chat_run_in_thread, agent, user_payload, history, session_id, persist_um
            )
        except Exception as e:
            log.exception("desk chat: run_conversation failed")
            return JSONResponse({"ok": False, "error": "run_failed", "detail": str(e)}, status_code=500)

        result = (payload or {}).get("result") or {}
        final_text = _desk_extract_reply_text(result)
        if not final_text:
            try:
                db_msgs = db.get_messages_as_conversation(session_id)
                final_text = _desk_text_from_assistant_messages(db_msgs)
            except Exception:
                log.debug("desk chat: could not re-read session messages for reply text", exc_info=True)

        ft = (final_text or "").strip()
        if ft in ("(empty)",):
            ft = ""
        if not ft and isinstance(result, dict):
            log.warning(
                "desk chat: empty assistant text (session=%s completed=%s failed=%s keys=%s)",
                session_id, result.get("completed"), result.get("failed"), list(result.keys()),
            )
            return JSONResponse(
                {
                    "ok": False,
                    "error": "empty_model_response",
                    "detail": (
                        "The model returned no visible text this turn -- "
                        "check your API key, model ID, and network in Settings."
                    ),
                    "session_id": session_id,
                    "received_chars": max(1, _recv_len),
                }
            )

        _agent_model = getattr(agent, "model", "") or ""
        _result_model = ((payload or {}).get("result") or {}).get("model") or ""
        _effective_model = _agent_model or _result_model
        return JSONResponse(
            {
                "ok": True,
                "proto": False,
                "session_id": session_id,
                "final_response": ft,
                "received_chars": max(1, _recv_len),
                "preview": (ft[:500] + "..." if len(ft) > 500 else ft) if ft else "",
                "prompt_tokens": int((payload or {}).get("prompt_tokens") or 0),
                "completion_tokens": int((payload or {}).get("completion_tokens") or 0),
                "model": _effective_model,
            }
        )
    finally:
        try:
            db.close()
        except Exception:
            pass
