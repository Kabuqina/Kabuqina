"""Camofox REST browser backend."""

from __future__ import annotations

import base64
import json
import os
import re
import threading
import uuid
from typing import Any
from urllib.parse import urlparse

import requests

from hermes_cli.config import load_config
from tools.browser_camofox_state import get_camofox_identity

_sessions: dict[str, dict[str, Any]] = {}
_sessions_lock = threading.Lock()
_vnc_url: str | None = None
_vnc_url_checked = False


def _json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False)


def _base_url() -> str:
    return os.environ.get("CAMOFOX_URL", "").strip().rstrip("/")


def is_camofox_mode() -> bool:
    if os.environ.get("BROWSER_CDP_URL", "").strip():
        return False
    return bool(_base_url())


def _request_url(path: str) -> str:
    return f"{_base_url()}{path}"


def _post(path: str, body: dict[str, Any] | None = None, timeout: float = 30.0) -> dict[str, Any]:
    resp = requests.post(_request_url(path), json=body or {}, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def _get(path: str, timeout: float = 30.0) -> dict[str, Any]:
    resp = requests.get(_request_url(path), timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def _get_raw(path: str, timeout: float = 30.0):
    resp = requests.get(_request_url(path), timeout=timeout)
    resp.raise_for_status()
    return resp


def _managed_persistence_enabled() -> bool:
    try:
        cfg = load_config() or {}
        browser_cfg = cfg.get("browser") if isinstance(cfg, dict) else {}
        camofox_cfg = browser_cfg.get("camofox") if isinstance(browser_cfg, dict) else {}
        return bool(camofox_cfg.get("managed_persistence")) if isinstance(camofox_cfg, dict) else False
    except Exception:
        return False


def _get_session(task_id: str | None = None) -> dict[str, Any]:
    key = task_id or "default"
    with _sessions_lock:
        existing = _sessions.get(key)
        if existing is not None:
            return existing
        if _managed_persistence_enabled():
            identity = get_camofox_identity(key)
            session = {
                "task_id": key,
                "user_id": identity["user_id"],
                "session_key": identity["session_key"],
                "managed": True,
                "tab_id": None,
                "url": None,
            }
        else:
            session = {
                "task_id": key,
                "user_id": f"hermes_{uuid.uuid4().hex[:16]}",
                "session_key": f"task_{uuid.uuid4().hex[:16]}",
                "managed": False,
                "tab_id": None,
                "url": None,
            }
        _sessions[key] = session
        return session


def _drop_session(task_id: str | None = None) -> None:
    with _sessions_lock:
        _sessions.pop(task_id or "default", None)


def _lookup_session(task_id: str | None = None) -> dict[str, Any] | None:
    with _sessions_lock:
        return _sessions.get(task_id or "default")


def _ensure_tab(task_id: str | None = None) -> dict[str, Any]:
    session = _lookup_session(task_id)
    if not session or not session.get("tab_id"):
        raise RuntimeError("No Camofox tab. Call browser_navigate first.")
    return session


def _extract_ref(ref: str) -> str:
    return str(ref or "").lstrip("@")


def check_camofox_available() -> bool:
    global _vnc_url, _vnc_url_checked
    if not _base_url():
        return False
    try:
        resp = requests.get(_request_url("/health"), timeout=2)
        if resp.status_code >= 400:
            return False
        data = resp.json() if getattr(resp, "json", None) else {}
        if not _vnc_url_checked:
            _vnc_url_checked = True
            port = data.get("vncPort") if isinstance(data, dict) else None
            if isinstance(port, int) and 0 < port < 65536:
                parsed = urlparse(_base_url())
                _vnc_url = f"{parsed.scheme or 'http'}://{parsed.hostname}:{port}"
        return True
    except Exception:
        return False


def get_vnc_url() -> str | None:
    return _vnc_url


def _with_vnc_hint(payload: dict[str, Any]) -> dict[str, Any]:
    if _vnc_url:
        payload["vnc_url"] = _vnc_url
        payload["vnc_hint"] = "Watch the live Camofox browser via vnc_url."
    return payload


def camofox_navigate(url: str, task_id: str | None = None) -> str:
    try:
        session = _get_session(task_id)
        if not session.get("tab_id"):
            data = _post("/tabs", {"url": url, "userId": session["user_id"]})
            session["tab_id"] = data.get("tabId") or data.get("tab_id")
        else:
            data = _post(f"/tabs/{session['tab_id']}/navigate", {"url": url})
        session["url"] = data.get("url") or url
        return _json(_with_vnc_hint({"success": True, "url": session["url"]}))
    except Exception as exc:
        return _json({"success": False, "error": f"Cannot connect to Camofox: {exc}"})


def camofox_snapshot(full: bool = False, task_id: str | None = None, user_task: str | None = None) -> str:
    try:
        session = _ensure_tab(task_id)
        data = _get(f"/tabs/{session['tab_id']}/snapshot")
        snapshot = str(data.get("snapshot") or "")
        return _json({
            "success": True,
            "snapshot": snapshot,
            "element_count": int(data.get("refsCount") or snapshot.count("[e")),
        })
    except Exception as exc:
        return _json({"success": False, "error": f"{exc} Use browser_navigate first."})


def camofox_click(ref: str, task_id: str | None = None) -> str:
    session = _ensure_tab(task_id)
    clean = _extract_ref(ref)
    _post(f"/tabs/{session['tab_id']}/click", {"ref": clean})
    return _json({"success": True, "clicked": clean})


def camofox_type(ref: str, text: str, task_id: str | None = None) -> str:
    session = _ensure_tab(task_id)
    clean = _extract_ref(ref)
    _post(f"/tabs/{session['tab_id']}/type", {"ref": clean, "text": text})
    return _json({"success": True, "typed": text})


def camofox_scroll(direction: str = "down", task_id: str | None = None) -> str:
    session = _ensure_tab(task_id)
    _post(f"/tabs/{session['tab_id']}/scroll", {"direction": direction})
    return _json({"success": True, "scrolled": direction})


def camofox_back(task_id: str | None = None) -> str:
    session = _ensure_tab(task_id)
    data = _post(f"/tabs/{session['tab_id']}/back")
    return _json({"success": True, "url": data.get("url")})


def camofox_press(key: str, task_id: str | None = None) -> str:
    session = _ensure_tab(task_id)
    _post(f"/tabs/{session['tab_id']}/press", {"key": key})
    return _json({"success": True, "pressed": key})


def camofox_close(task_id: str | None = None) -> str:
    session = _lookup_session(task_id)
    if session and session.get("tab_id"):
        try:
            requests.delete(_request_url(f"/tabs/{session['tab_id']}"), timeout=10)
        except Exception:
            pass
    _drop_session(task_id)
    return _json({"success": True, "closed": True})


def camofox_soft_cleanup(task_id: str | None = None) -> bool:
    if not _managed_persistence_enabled():
        return False
    _drop_session(task_id)
    return True


def camofox_console(clear: bool = False, task_id: str | None = None) -> str:
    return _json({
        "success": True,
        "messages": [],
        "total_messages": 0,
        "note": "Console messages are not available from the Camofox REST backend.",
    })


def camofox_get_images(task_id: str | None = None) -> str:
    snap = json.loads(camofox_snapshot(task_id=task_id))
    if not snap.get("success"):
        return _json(snap)
    images = []
    lines = str(snap.get("snapshot") or "").splitlines()
    current_alt = ""
    for line in lines:
        img_match = re.search(r'img\s+"([^"]*)"', line)
        if img_match:
            current_alt = img_match.group(1)
            continue
        url_match = re.search(r"/url:\s*(\S+)", line)
        if url_match:
            images.append({"src": url_match.group(1), "alt": current_alt})
            current_alt = ""
    return _json({"success": True, "count": len(images), "images": images})


def camofox_vision(question: str, annotate: bool = False, task_id: str | None = None) -> str:
    session = _ensure_tab(task_id)
    snapshot = _get(f"/tabs/{session['tab_id']}/snapshot").get("snapshot", "")
    raw = _get_raw(f"/tabs/{session['tab_id']}/screenshot")
    image_b64 = base64.b64encode(raw.content or b"").decode("ascii")
    cfg = load_config() or {}
    vision_cfg = ((cfg.get("auxiliary") or {}).get("vision") or {}) if isinstance(cfg, dict) else {}
    temperature = float(vision_cfg.get("temperature", 0.1))
    timeout = float(vision_cfg.get("timeout", 120.0))

    from providers import chat_completions

    response = chat_completions.call_llm(
        [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": f"{question}\n\nSnapshot:\n{snapshot}"},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}},
                ],
            }
        ],
        temperature=temperature,
        timeout=timeout,
    )
    analysis = response.choices[0].message.content
    return _json({"success": True, "analysis": analysis})
