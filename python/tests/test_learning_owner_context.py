# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Tests for desk-side owner establishment + injection (python/src/learning_owner.py).

The runtime is the only source of owner_id (design §8.3): Desktop uses a stable
local id; Gateway derives ``gateway:<platform>:<hashed-user-id>`` from a stable
platform user id (never a nickname). A request can never override the injected
owner.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
CORE_DIR = Path(__file__).resolve().parents[2] / "hermes_core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

import tempfile

from learning_owner import (  # noqa: E402
    desktop_owner_id,
    gateway_owner_id,
    establish_desktop_context,
    establish_gateway_context,
    desktop_learning_scope,
)
from learning.learning_store import LearningStore  # noqa: E402
from learning.learning_context import active_learning_context  # noqa: E402


class OwnerIdTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_desktop_owner_id_is_stable_and_prefixed(self):
        first = desktop_owner_id(root=self.root)
        second = desktop_owner_id(root=self.root)
        self.assertEqual(first, second)  # stable across calls
        self.assertTrue(first.startswith("desktop:"))

    def test_desktop_owner_id_persists_to_disk(self):
        owner = desktop_owner_id(root=self.root)
        # A fresh read (new "process") returns the same persisted id.
        self.assertEqual(desktop_owner_id(root=self.root), owner)
        # And it is actually on disk under the given root.
        self.assertTrue(any(self.root.iterdir()))

    def test_gateway_owner_id_shape(self):
        owner = gateway_owner_id("discord", "user-123")
        parts = owner.split(":")
        self.assertEqual(parts[0], "gateway")
        self.assertEqual(parts[1], "discord")
        self.assertEqual(len(parts), 3)
        self.assertTrue(parts[2])

    def test_gateway_owner_id_is_deterministic_and_hashed(self):
        a = gateway_owner_id("discord", "user-123")
        b = gateway_owner_id("discord", "user-123")
        self.assertEqual(a, b)  # deterministic
        # Derived from the stable user id by hashing — the raw id is not leaked,
        # and a nickname (which is not even an input) cannot change it.
        self.assertNotIn("user-123", a)
        self.assertNotEqual(a, gateway_owner_id("discord", "user-999"))

    def test_gateway_platform_is_normalized(self):
        self.assertEqual(
            gateway_owner_id("Discord", "u1"), gateway_owner_id("discord", "u1")
        )

    def test_gateway_requires_platform_and_user(self):
        with self.assertRaises(ValueError):
            gateway_owner_id("", "u1")
        with self.assertRaises(ValueError):
            gateway_owner_id("discord", "")


class OwnerInjectionTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.store = LearningStore(db_path=self.root / "learning.db")

    def tearDown(self):
        self.store.close()
        self._tmp.cleanup()

    def test_desktop_context_uses_runtime_owner(self):
        ctx = establish_desktop_context(self.store, root=self.root)
        self.assertEqual(ctx.owner_id, desktop_owner_id(root=self.root))

    def test_request_cannot_override_injected_owner(self):
        owner = desktop_owner_id(root=self.root)
        ctx = establish_desktop_context(
            self.store, root=self.root, request={"owner_id": "attacker"}
        )
        self.assertEqual(ctx.owner_id, owner)
        self.assertNotEqual(ctx.owner_id, "attacker")
        # And the injected owner is what actually scopes writes.
        ctx.create_space(title="Algebra", space_id="s1")
        ctx.put_artifact(
            kind="flashcard_deck",
            title="D",
            payload={"cards": [{"front": "q", "back": "a"}]},
        )
        from learning.learning_context import LearningExecutionContext

        attacker = LearningExecutionContext(self.store, owner_id="attacker", space_id="s1")
        self.assertEqual(attacker.list_artifacts(), [])

    def test_desktop_scope_binds_active_context(self):
        with desktop_learning_scope(self.store, root=self.root) as ctx:
            active = active_learning_context()
            self.assertIsNotNone(active)
            self.assertEqual(active.owner_id, ctx.owner_id)
            self.assertEqual(active.owner_id, desktop_owner_id(root=self.root))
        # Scope cleaned up.
        self.assertIsNone(active_learning_context())

    def test_gateway_context_owner(self):
        ctx = establish_gateway_context(self.store, platform="discord", user_id="u1")
        self.assertEqual(ctx.owner_id, gateway_owner_id("discord", "u1"))

    def test_desktop_and_gateway_owners_are_isolated(self):
        desk = establish_desktop_context(self.store, root=self.root)
        desk.create_space(title="Algebra", space_id="shared")
        desk.put_artifact(
            kind="flashcard_deck",
            title="D",
            payload={"cards": [{"front": "q", "back": "a"}]},
        )
        gw = establish_gateway_context(self.store, platform="discord", user_id="u1")
        gw.create_space(title="Algebra", space_id="shared")
        # Same space name, different runtime owner → isolated.
        self.assertEqual(gw.list_artifacts(), [])
        self.assertEqual(len(desk.list_artifacts()), 1)


if __name__ == "__main__":
    unittest.main()
