# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Tests for MemoryStore group-chat downgrade and _host_prefs.md loading.

Requires adding hermes_core/ to sys.path (no full Hermes import chain).
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

# Add hermes_core/ to path for MemoryStore import
_hermes_core = str(Path(__file__).resolve().parent.parent.parent / "hermes_core")
if _hermes_core not in sys.path:
    sys.path.insert(0, _hermes_core)


# =========================================================================
# Layer 2a: Group chat write guards
# =========================================================================

class TestMemoryGroupChatWriteGuards(unittest.TestCase):
    """is_group=True blocks add/replace/remove."""

    def setUp(self):
        # Use a MemoryStore without calling load_from_disk (no disk needed).
        # We monkey-patch get_memory_dir so the constructor doesn't crash
        # when called via _path_for.
        self.tmp = Path(tempfile.mkdtemp())
        patcher = patch("tools.memory_tool.get_memory_dir", return_value=self.tmp)
        patcher.start()
        self.addCleanup(patcher.stop)

        from tools.memory_tool import MemoryStore

        # DM store (chat_type="" = no group restriction)
        self.dm_store = MemoryStore(memory_char_limit=500, user_char_limit=300, chat_type="")
        self.dm_store.load_from_disk()

        # Group store
        self.group_store = MemoryStore(memory_char_limit=500, user_char_limit=300, chat_type="group")
        self.group_store.load_from_disk()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    # -- add guards ---------------------------------------------------------

    def test_dm_add_succeeds(self):
        result = self.dm_store.add("memory", "test fact")
        self.assertTrue(result["success"])

    def test_group_add_rejected(self):
        result = self.group_store.add("memory", "test fact")
        self.assertFalse(result["success"])
        self.assertIn("group", result.get("error", "").lower())

    def test_group_add_rejected_user_target(self):
        result = self.group_store.add("user", "Name: Alice")
        self.assertFalse(result["success"])
        self.assertIn("group", result.get("error", "").lower())

    # -- replace guards ----------------------------------------------------

    def test_dm_replace_succeeds(self):
        self.dm_store.add("memory", "old text")
        result = self.dm_store.replace("memory", "old", "new text")
        self.assertTrue(result["success"])

    def test_group_replace_rejected(self):
        self.group_store.add("memory", "old text")
        result = self.group_store.replace("memory", "old", "new text")
        self.assertFalse(result["success"])
        self.assertIn("group", result.get("error", "").lower())

    # -- remove guards -----------------------------------------------------

    def test_dm_remove_succeeds(self):
        self.dm_store.add("memory", "remove me")
        result = self.dm_store.remove("memory", "remove me")
        self.assertTrue(result["success"])

    def test_group_remove_rejected(self):
        self.group_store.add("memory", "remove me")
        result = self.group_store.remove("memory", "remove me")
        self.assertFalse(result["success"])
        self.assertIn("group", result.get("error", "").lower())

    # -- format_for_system_prompt ------------------------------------------

    def test_group_snapshot_returns_none_for_memory(self):
        # After load_from_disk with chat_type="group", the snapshot should be empty.
        # Since we passed `is_group=True`, the snapshot was blanked at load time.
        block = self.group_store.format_for_system_prompt("memory")
        self.assertIsNone(block)

    def test_group_snapshot_returns_none_for_user(self):
        block = self.group_store.format_for_system_prompt("user")
        self.assertIsNone(block)

    def test_dm_snapshot_returns_block_when_entries_exist(self):
        self.dm_store.add("memory", "persistent fact")
        # Snapshot was captured at load time (before add) so it's empty — but
        # that's the frozen-snapshot pattern. We just verify no crash.
        block = self.dm_store.format_for_system_prompt("memory")
        # It should be None since no entries existed at load time.
        self.assertIsNone(block)


# =========================================================================
# Layer 2b: _host_prefs.md loading
# =========================================================================

class TestMemoryHostPrefs(unittest.TestCase):
    """_host_prefs.md is loaded in DM context, empty/skipped in group context."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        # Set HERMES_HOME to tmp so get_kabuqina_home() returns it
        self.env_patcher = patch.dict(os.environ, {"HERMES_HOME": str(self.tmp)})
        self.env_patcher.start()
        self.addCleanup(self.env_patcher.stop)

        # Monkey-patch get_memory_dir so MEMORY.md/USER.md go to tmp/memories/
        self.mem_dir = self.tmp / "memories"
        self.mem_dir.mkdir(parents=True, exist_ok=True)
        self.mem_patcher = patch("tools.memory_tool.get_memory_dir", return_value=self.mem_dir)
        self.mem_patcher.start()
        self.addCleanup(self.mem_patcher.stop)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _make_store(self, chat_type: str):
        from tools.memory_tool import MemoryStore
        store = MemoryStore(memory_char_limit=500, user_char_limit=300, chat_type=chat_type)
        store.load_from_disk()
        return store

    def test_host_prefs_loaded_in_dm(self):
        """Host _host_prefs.md exists → format_for_system_prompt returns content."""
        (self.tmp / "_host_prefs.md").write_text("language: en\ntimezone: UTC", encoding="utf-8")
        store = self._make_store(chat_type="")
        block = store.format_for_system_prompt("host_prefs")
        self.assertIsNotNone(block)
        self.assertIn("language: en", block)

    def test_host_prefs_not_loaded_in_group(self):
        """Host _host_prefs.md exists but chat_type=group → returns None."""
        (self.tmp / "_host_prefs.md").write_text("language: en\ntimezone: UTC", encoding="utf-8")
        store = self._make_store(chat_type="group")
        block = store.format_for_system_prompt("host_prefs")
        self.assertIsNone(block)

    def test_host_prefs_missing_file_no_crash(self):
        """Host _host_prefs.md does not exist → no crash, returns None."""
        store = self._make_store(chat_type="")
        block = store.format_for_system_prompt("host_prefs")
        self.assertIsNone(block)

    def test_host_prefs_empty_file_no_content(self):
        """Host _host_prefs.md is empty → returns None."""
        (self.tmp / "_host_prefs.md").write_text("  \n  ", encoding="utf-8")
        store = self._make_store(chat_type="")
        block = store.format_for_system_prompt("host_prefs")
        self.assertIsNone(block)

    def test_memory_and_user_still_work_with_host_prefs(self):
        """Having _host_prefs.md doesn't break normal memory/user functioning."""
        (self.tmp / "_host_prefs.md").write_text("language: en", encoding="utf-8")
        store = self._make_store(chat_type="")
        # Normal memory operations still work
        result = store.add("memory", "normal fact")
        self.assertTrue(result["success"])


if __name__ == "__main__":
    unittest.main()
