# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

_SRC = Path(__file__).resolve().parents[1] / "src"
_HERMES_CORE = Path(__file__).resolve().parents[2] / "hermes_core"
for _p in (_SRC, _HERMES_CORE):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from desktop_delivery import (  # noqa: E402
    REMINDER_SESSION_ID,
    REMINDER_SESSION_TITLE,
    deliver,
    format_reminder_content,
    persist_reminder_session,
)


class TestDesktopDelivery(unittest.TestCase):
    def test_format_reminder_content(self):
        self.assertEqual(
            format_reminder_content("喝水", "该喝水啦"),
            "**⏰ 喝水**\n\n该喝水啦",
        )

    @patch("kabuqina_state.SessionDB")
    def test_persist_reminder_session_writes_history(self, session_db_cls):
        db = MagicMock()
        session_db_cls.return_value = db

        persist_reminder_session("喝水", "该喝水啦")

        session_db_cls.assert_called_once()
        db.create_session.assert_called_once_with(
            session_id=REMINDER_SESSION_ID,
            source="hermesdesk",
            model="cron-reminder",
        )
        db.set_session_title.assert_called_once_with(REMINDER_SESSION_ID, REMINDER_SESSION_TITLE)
        self.assertEqual(db.append_message.call_count, 2)
        db.close.assert_called_once()

    @patch("desktop_delivery.persist_reminder_session")
    @patch("urllib.request.urlopen")
    def test_deliver_persists_after_bridge_ok(self, urlopen, persist):
        urlopen.return_value.__enter__.return_value.read.return_value = json.dumps({"ok": True}).encode()
        with patch.dict(os.environ, {"HERMESDESK_DESKTOP_DELIVERY_URL": "http://127.0.0.1:1/x"}):
            ok = deliver("该喝水啦", title="喝水")
        self.assertTrue(ok)
        persist.assert_called_once_with("喝水", "该喝水啦")

    @patch("desktop_delivery.persist_reminder_session")
    @patch("urllib.request.urlopen")
    def test_deliver_keeps_history_when_bridge_fails(self, urlopen, persist):
        urlopen.return_value.__enter__.return_value.read.return_value = json.dumps({"ok": False}).encode()
        with patch.dict(os.environ, {"HERMESDESK_DESKTOP_DELIVERY_URL": "http://127.0.0.1:1/x"}):
            ok = deliver("该喝水啦", title="喝水")
        self.assertFalse(ok)
        persist.assert_called_once_with("喝水", "该喝水啦")

    @patch("desktop_delivery.persist_reminder_session")
    @patch("urllib.request.urlopen")
    def test_deliver_persists_before_bridge_post_so_event_refresh_sees_history(self, urlopen, persist):
        def _open(*args, **kwargs):
            persist.assert_called_once_with("喝水", "该喝水啦")
            cm = MagicMock()
            cm.__enter__.return_value.read.return_value = json.dumps({"ok": True}).encode()
            return cm

        urlopen.side_effect = _open
        with patch.dict(os.environ, {"HERMESDESK_DESKTOP_DELIVERY_URL": "http://127.0.0.1:1/x"}):
            ok = deliver("该喝水啦", title="喝水")
        self.assertTrue(ok)


if __name__ == "__main__":
    unittest.main()
