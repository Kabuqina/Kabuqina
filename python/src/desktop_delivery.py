# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Desktop delivery — POST messages to the Tauri shell for local display.

This is HermesDesk's "desktop" virtual messaging platform.  When a user
(or a cron job) sends a message to ``target="desktop"``, it lands here:
the payload is POSTed to a loopback endpoint on the Tauri bridge, which
writes it into the /chat message stream and fires a Windows notification.

No network egress, no third-party service — local-only delivery.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request

log = logging.getLogger("kabuqina.desktop.delivery")

REMINDER_SESSION_ID = "hermesdesk-reminders"
REMINDER_SESSION_TITLE = "小娜提醒"


def format_reminder_content(title: str, message: str) -> str:
    header = (title or "小娜提醒").strip()
    body = (message or "").strip()
    if body:
        return f"**⏰ {header}**\n\n{body}"
    return f"**⏰ {header}**"


def persist_reminder_session(title: str, message: str) -> None:
    """Append a fired reminder to the desk chat session DB so history survives reloads."""
    content = format_reminder_content(title, message)
    if not content.strip():
        return
    try:
        from hermes_state import SessionDB

        db = SessionDB()
        try:
            db.create_session(
                session_id=REMINDER_SESSION_ID,
                source="hermesdesk",
                model="cron-reminder",
            )
            try:
                db.set_session_title(REMINDER_SESSION_ID, REMINDER_SESSION_TITLE)
            except ValueError:
                pass
            marker = (title or "小娜提醒").strip()
            db.append_message(REMINDER_SESSION_ID, role="user", content=f"⏰ {marker}")
            db.append_message(REMINDER_SESSION_ID, role="assistant", content=content)
        finally:
            db.close()
    except Exception:
        log.exception("desktop delivery: failed to persist reminder session")


def deliver(message: str, title: str = "", attachments: list[str] | None = None) -> bool:
    """Deliver a message to the desktop (Tauri /chat + Windows notification).

    Returns True on success.
    """
    persist_reminder_session(title, message)

    url = os.environ.get("HERMESDESK_DESKTOP_DELIVERY_URL")
    if not url:
        log.warning("HERMESDESK_DESKTOP_DELIVERY_URL not set; cannot deliver")
        return False

    payload = json.dumps({
        "message": message,
        "title": title or "Kabuqina",
        "attachments": attachments or [],
    }).encode("utf-8")

    req = urllib.request.Request(
        url, data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:  # nosec - loopback
            body = json.loads(resp.read())
            ok = bool(body.get("ok"))
            if ok:
                log.info("desktop delivery: ok (title=%r, len=%d)", title, len(message))
            else:
                log.warning("desktop delivery: bridge returned ok=false")
            return ok
    except urllib.error.URLError:
        log.exception("desktop delivery: bridge unreachable")
        return False
    except Exception:
        log.exception("desktop delivery: unexpected error")
        return False
