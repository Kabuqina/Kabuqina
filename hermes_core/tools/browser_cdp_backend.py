"""CDP browser backend for Kabuqina — drives Edge via DevTools Protocol.

Provides high-level operations (navigate, snapshot, vision, click, type, etc.)
over a CDP WebSocket connection.  Used by ``browser_tool.py`` when
``BROWSER_CDP_URL`` is set (Kabuqina auto-launches Edge with
``--remote-debugging-port=9222``).

All Page.* / Runtime.* / Input.* / DOM.* commands require a **page-level
session**.  We first connect to the browser-level WebSocket, create a page
target via ``Target.createTarget``, attach via ``Target.attachToTarget``
(flatten), and then send the session-scoped command — all on a single
ephemeral WebSocket per call.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

from kabuqina_constants import get_kabuqina_home

logger = logging.getLogger(__name__)

try:
    import websockets
    _WS_AVAILABLE = True
except ImportError:
    websockets = None
    _WS_AVAILABLE = False

# Cached page target ID (scoped to the current Edge CDP session).
_page_target_id: Optional[str] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_cdp_url() -> str:
    try:
        from tools.browser_tool import _get_cdp_override
        return (_get_cdp_override() or "").strip()
    except Exception:
        return ""


def _json(result: Any, success: bool = True) -> str:
    return json.dumps({"success": success, "data": result} if success else {"success": False, "error": str(result)})


def _run_async(coro):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, coro).result()
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# CDP call with page-level session support
# ---------------------------------------------------------------------------

async def _page_session_call(method: str, params: Dict[str, Any] = None, timeout: float = 15.0) -> dict:
    """Connect to browser WS, ensure a page target, attach, and call *method*
    in the page session.  The target lifecycle is:

    1. ``Target.createTarget`` (``about:blank``) once, cached globally.
    2. ``Target.attachToTarget`` on every call (session is ephemeral).
    3. Send ``method`` with ``sessionId``.
    """
    global _page_target_id

    ws_url = _get_cdp_url()
    if not ws_url:
        raise RuntimeError("BROWSER_CDP_URL not set")
    assert _WS_AVAILABLE

    async with websockets.connect(ws_url, max_size=None, open_timeout=timeout,
                                  close_timeout=5, ping_interval=None) as ws:
        next_id = 1

        # -- Step 1: ensure a page target exists (create once) --
        if _page_target_id is None:
            create_id = next_id
            next_id += 1
            await ws.send(json.dumps({
                "id": create_id, "method": "Target.createTarget",
                "params": {"url": "about:blank"},
            }))
            deadline = time.time() + timeout
            while True:
                remaining = deadline - time.time()
                if remaining <= 0:
                    raise TimeoutError("createTarget timed out")
                raw = await asyncio.wait_for(ws.recv(), timeout=remaining)
                msg = json.loads(raw)
                if msg.get("id") == create_id:
                    if "error" in msg:
                        raise RuntimeError(f"createTarget failed: {msg['error']}")
                    _page_target_id = msg.get("result", {}).get("targetId", "")
                    if not _page_target_id:
                        raise RuntimeError("createTarget returned no targetId")
                    break

        # -- Step 2: attach to the page target (flatten = multiplex over browser WS) --
        attach_id = next_id
        next_id += 1
        await ws.send(json.dumps({
            "id": attach_id, "method": "Target.attachToTarget",
            "params": {"targetId": _page_target_id, "flatten": True},
        }))
        deadline = time.time() + timeout
        session_id = None
        while True:
            remaining = deadline - time.time()
            if remaining <= 0:
                raise TimeoutError("attachToTarget timed out")
            raw = await asyncio.wait_for(ws.recv(), timeout=remaining)
            msg = json.loads(raw)
            if msg.get("id") == attach_id:
                if "error" in msg:
                    raise RuntimeError(f"attachToTarget failed: {msg['error']}")
                session_id = msg.get("result", {}).get("sessionId", "")
                if not session_id:
                    raise RuntimeError("attachToTarget returned no sessionId")
                break

        # -- Step 3: send the real command with sessionId --
        call_id = next_id
        next_id += 1
        msg = {"id": call_id, "method": method, "params": params or {}, "sessionId": session_id}
        await ws.send(json.dumps(msg))

        deadline = time.time() + timeout
        while True:
            remaining = deadline - time.time()
            if remaining <= 0:
                raise TimeoutError(f"CDP {method} timed out")
            raw = await asyncio.wait_for(ws.recv(), timeout=remaining)
            msg = json.loads(raw)
            if msg.get("id") == call_id:
                if "error" in msg:
                    raise RuntimeError(f"CDP {method} error: {msg['error']}")
                return msg.get("result", {})


# ---------------------------------------------------------------------------
# High-level operations
# ---------------------------------------------------------------------------

def navigate(url: str) -> str:
    try:
        _run_async(_page_session_call("Page.navigate", {"url": url}, timeout=30))
        time.sleep(1.5)
        result = _run_async(_page_session_call("Runtime.evaluate", {
            "expression": "JSON.stringify({title: document.title, url: location.href})",
        }, timeout=10))
        data = json.loads(result.get("result", {}).get("value", "{}"))
        return _json(data)
    except Exception as e:
        return _json(f"navigate failed: {e}", success=False)


def snapshot() -> str:
    try:
        result = _run_async(_page_session_call("Runtime.evaluate", {
            "expression": """
                (() => {
                    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, null, false);
                    const parts = [];
                    while (walker.nextNode()) {
                        const t = walker.currentNode.textContent.trim();
                        if (t) parts.push(t);
                    }
                    return parts.join('\\n').substring(0, 80000);
                })()
            """,
        }, timeout=15))
        text = result.get("result", {}).get("value", "")
        return _json({"text": text or "(empty page)"})
    except Exception as e:
        return _json(f"snapshot failed: {e}", success=False)


def click(ref: str) -> str:
    try:
        safe_ref = ref.replace("'", "\\'")
        result = _run_async(_page_session_call("Runtime.evaluate", {
            "expression": f"""
                (() => {{
                    const el = document.querySelector('{safe_ref}');
                    if (!el) {{
                        const all = document.querySelectorAll('a, button, span, div');
                        for (const e of all) {{
                            if (e.textContent.trim().includes('{safe_ref}')) return e;
                        }}
                        return null;
                    }}
                    return el;
                }})()
            """,
        }, timeout=10))
        obj_id = result.get("result", {}).get("objectId")
        if not obj_id:
            return _json(f"Element not found: {ref}", success=False)

        box = _run_async(_page_session_call("DOM.getContentQuads", {"objectId": obj_id}, timeout=10))
        quads = box.get("quads", [])
        if not quads:
            return _json(f"Cannot locate element on screen: {ref}", success=False)

        q = quads[0]
        x = (q[0] + q[2]) / 2
        y = (q[1] + q[5]) / 2
        _run_async(_page_session_call("Input.dispatchMouseEvent", {
            "type": "mousePressed", "x": x, "y": y, "button": "left", "clickCount": 1,
        }, timeout=10))
        _run_async(_page_session_call("Input.dispatchMouseEvent", {
            "type": "mouseReleased", "x": x, "y": y, "button": "left", "clickCount": 1,
        }, timeout=10))

        return _json({"clicked": ref, "x": x, "y": y})
    except Exception as e:
        return _json(f"click failed: {e}", success=False)


def type_text(ref: str, text: str) -> str:
    try:
        safe_ref = ref.replace("'", "\\'")
        result = _run_async(_page_session_call("Runtime.evaluate", {
            "expression": f"""
                (() => {{
                    const el = document.querySelector('{safe_ref}');
                    if (!el) return false;
                    el.focus();
                    el.value = '';
                    return true;
                }})()
            """,
        }, timeout=10))
        focused = result.get("result", {}).get("value", False)
        if not focused:
            return _json(f"Element not found: {ref}", success=False)

        _run_async(_page_session_call("Input.insertText", {"text": text}, timeout=10))
        return _json({"typed": text, "into": ref})
    except Exception as e:
        return _json(f"type failed: {e}", success=False)


def scroll(direction: str) -> str:
    amount = {"up": "0, -500", "down": "0, 500", "left": "-500, 0", "right": "500, 0"}
    delta = amount.get(direction, "0, 500")
    try:
        _run_async(_page_session_call("Runtime.evaluate", {
            "expression": f"window.scrollBy({delta})",
        }, timeout=10))
        return _json({"scrolled": direction})
    except Exception as e:
        return _json(f"scroll failed: {e}", success=False)


def back() -> str:
    try:
        _run_async(_page_session_call("Runtime.evaluate", {
            "expression": "window.history.back()",
        }, timeout=15))
        return _json({"back": True})
    except Exception as e:
        return _json(f"back failed: {e}", success=False)


def press(key: str) -> str:
    key_map = {
        "enter": "Enter", "escape": "Escape", "tab": "Tab",
        "up": "ArrowUp", "down": "ArrowDown", "left": "ArrowLeft", "right": "ArrowRight",
        "space": " ", "backspace": "Backspace", "delete": "Delete",
    }
    mapped = key_map.get(key.lower(), key)
    try:
        _run_async(_page_session_call("Input.dispatchKeyEvent", {
            "type": "rawKeyDown", "key": mapped, "windowsVirtualKeyCode": 0,
        }, timeout=10))
        _run_async(_page_session_call("Input.dispatchKeyEvent", {
            "type": "keyUp", "key": mapped, "windowsVirtualKeyCode": 0,
        }, timeout=10))
        return _json({"pressed": mapped})
    except Exception as e:
        return _json(f"press failed: {e}", success=False)


def console(clear: bool = False, expression: str | None = None) -> str:
    try:
        if clear:
            _run_async(_page_session_call("Runtime.evaluate", {
                "expression": "console.clear()",
            }, timeout=10))
            return _json({"cleared": True})
        if expression:
            result = _run_async(_page_session_call("Runtime.evaluate", {
                "expression": expression, "returnByValue": True,
            }, timeout=15))
            value = result.get("result", {})
            return _json({"result": value.get("value", str(value))})
        logs = _run_async(_page_session_call("Runtime.evaluate", {
            "expression": "console._logs ? console._logs.join('\\n') : '(no logs)'",
        }, timeout=10))
        return _json({"logs": logs.get("result", {}).get("value", "")})
    except Exception as e:
        return _json(f"console failed: {e}", success=False)


def get_images() -> str:
    try:
        result = _run_async(_page_session_call("Runtime.evaluate", {
            "expression": """
                JSON.stringify(Array.from(document.images).slice(0, 20).map(i => ({
                    src: i.src, alt: i.alt || '', width: i.naturalWidth, height: i.naturalHeight
                })))
            """,
        }, timeout=10))
        val = result.get("result", {}).get("value", "[]")
        return _json(json.loads(val) if isinstance(val, str) else val)
    except Exception as e:
        return _json(f"get_images failed: {e}", success=False)


def vision(question: str, annotate: bool = False) -> str:
    """Take a screenshot, then use the vision tool to answer the question."""
    try:
        result = _run_async(_page_session_call("Page.captureScreenshot", {
            "format": "png", "fromSurface": True,
        }, timeout=30))
        b64 = result.get("data", "")
        if not b64:
            return _json("Screenshot returned empty data", success=False)

        # Always save screenshot to disk first, regardless of vision outcome
        screenshots_dir = get_kabuqina_home() / "cache" / "screenshots"
        screenshots_dir.mkdir(parents=True, exist_ok=True)
        path = screenshots_dir / f"cdp_screenshot_{uuid.uuid4().hex}.png"
        path.write_bytes(base64.b64decode(b64))

        try:
            from tools.vision_tools import vision_inline
            answer = vision_inline(question, base64.b64decode(b64))
            return _json({"answer": answer, "screenshot_path": str(path)})
        except Exception as _ve:
            logger.warning("vision_inline failed (%s), screenshot saved to %s", _ve, path)
            return _json({
                "screenshot_taken": True,
                "answer": f"Screenshot captured but vision analysis failed: {_ve}. "
                           f"Screenshot saved to {path} — use read_file to inspect.",
                "screenshot_path": str(path),
            })
    except Exception as e:
        return _json(f"vision failed: {e}", success=False)
