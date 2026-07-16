# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Integration tests for bootstrap modes (no Hermes import chain needed)."""

import os
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

import sys
_src = str(Path(__file__).resolve().parent.parent / "src")
if _src not in sys.path:
    sys.path.insert(0, _src)

from desktop_config import DesktopConfig, RuntimeMode, from_env
from kabuqina_env import normalize, resolve_desktop_home


class TestBoostrapModes(unittest.TestCase):
    def _make_env(self, *, power_user=False, provider="openrouter"):
        return {
            "HERMESDESK_BUNDLE_DIR": "/tmp/bundle",
            "HERMESDESK_DATA_DIR": "/tmp/data",
            "HERMESDESK_WORKSPACE": "/tmp/workspace",
            "HERMESDESK_PROVIDER": provider,
            "HERMESDESK_LLM_HOST": "openrouter.ai",
            "HERMESDESK_POWER_USER": "1" if power_user else "0",
            "HERMESDESK_CONTRACT_VERSION": "1",
        }

    def test_default_mode(self):
        with patch.dict(os.environ, self._make_env(power_user=False)):
            cfg = from_env()
            self.assertEqual(cfg.runtime_mode, RuntimeMode.DEFAULT)
            self.assertFalse(cfg.power_user)
            self.assertEqual(cfg.contract_version, 1)
            self.assertEqual(cfg.provider, "openrouter")
            self.assertEqual(cfg.workspace, Path("/tmp/workspace"))

    def test_kabuqina_env_is_accepted_without_legacy_aliases(self):
        env = {
            key.replace("HERMESDESK_", "KABUQINA_"): value
            for key, value in self._make_env(power_user=True).items()
        }
        with patch.dict(os.environ, env, clear=True):
            cfg = from_env()
        self.assertEqual(cfg.workspace, Path("/tmp/workspace"))
        self.assertTrue(cfg.power_user)

    def test_kabuqina_env_wins_over_legacy_alias(self):
        env = self._make_env(provider="legacy")
        env["KABUQINA_PROVIDER"] = "current"
        with patch.dict(os.environ, env, clear=True):
            cfg = from_env()
        self.assertEqual(cfg.provider, "current")

    def test_normalize_overwrites_conflicting_legacy_alias(self):
        with patch.dict(
            os.environ,
            {"KABUQINA_WORKSPACE": "/tmp/new", "HERMESDESK_WORKSPACE": "/tmp/old"},
            clear=True,
        ):
            normalize()
            self.assertEqual(os.environ["HERMESDESK_WORKSPACE"], "/tmp/new")

    def test_power_user_mode(self):
        with patch.dict(os.environ, self._make_env(power_user=True)):
            cfg = from_env()
            self.assertEqual(cfg.runtime_mode, RuntimeMode.POWER_USER)
            self.assertTrue(cfg.power_user)

    def test_custom_provider_with_api_base(self):
        env = self._make_env(provider="custom")
        env["HERMESDESK_API_BASE_URL"] = "https://api.mycorp.com/v1"
        with patch.dict(os.environ, env):
            cfg = from_env()
            self.assertEqual(cfg.provider, "custom")
            self.assertEqual(cfg.api_base_url, "https://api.mycorp.com/v1")

    def test_optional_fields_default_to_none(self):
        env = self._make_env()
        with patch.dict(os.environ, env):
            cfg = from_env()
            self.assertIsNone(cfg.approval_url)
            self.assertIsNone(cfg.bridge_secret)

    def test_kabuqina_home_computed(self):
        with patch.dict(os.environ, self._make_env(), clear=True):
            cfg = from_env()
            self.assertEqual(cfg.kabuqina_home, Path("/tmp/data") / "kabuqina-home")
            self.assertEqual(cfg.hermes_home, cfg.kabuqina_home)

    def test_desktop_home_migrates_populated_legacy_directory(self):
        import tempfile

        with tempfile.TemporaryDirectory() as temp:
            data_dir = Path(temp)
            legacy = data_dir / "hermes-home"
            legacy.mkdir()
            (legacy / "state.db").write_bytes(b"session-sample")
            (legacy / "learning.db").write_bytes(b"learning-sample")

            resolved = resolve_desktop_home(data_dir)

            self.assertEqual(resolved, data_dir / "kabuqina-home")
            self.assertFalse(legacy.exists())
            self.assertEqual((resolved / "state.db").read_bytes(), b"session-sample")
            self.assertEqual((resolved / "learning.db").read_bytes(), b"learning-sample")

    def test_desktop_home_new_directory_wins_when_both_exist(self):
        import tempfile

        with tempfile.TemporaryDirectory() as temp:
            data_dir = Path(temp)
            current = data_dir / "kabuqina-home"
            legacy = data_dir / "hermes-home"
            current.mkdir()
            legacy.mkdir()
            self.assertEqual(resolve_desktop_home(data_dir), current)
            self.assertTrue(legacy.exists())

    def test_desktop_home_falls_back_when_rename_fails(self):
        import tempfile

        with tempfile.TemporaryDirectory() as temp:
            data_dir = Path(temp)
            legacy = data_dir / "hermes-home"
            legacy.mkdir()
            with patch.object(Path, "rename", side_effect=OSError("locked")):
                self.assertEqual(resolve_desktop_home(data_dir), legacy)
            # The filesystem condition has recovered, but this process must
            # keep the first choice so one launch never splits its state.
            self.assertEqual(resolve_desktop_home(data_dir), legacy)
            self.assertTrue(legacy.exists())
            self.assertFalse((data_dir / "kabuqina-home").exists())

    def test_rust_selected_home_is_used_by_fresh_python_child(self):
        import tempfile

        with tempfile.TemporaryDirectory() as temp:
            data_dir = Path(temp)
            legacy = data_dir / "hermes-home"
            current = data_dir / "kabuqina-home"
            legacy.mkdir()
            env = os.environ.copy()
            env.update(
                {
                    "KABUQINA_DATA_DIR": str(data_dir),
                    "KABUQINA_HOME": str(legacy),
                    "HERMES_HOME": str(legacy),
                    "PYTHONPATH": _src,
                }
            )
            script = (
                "import os; from pathlib import Path; "
                "from kabuqina_env import resolve_child_home; "
                "print(resolve_child_home(Path(os.environ['KABUQINA_DATA_DIR'])))"
            )

            result = subprocess.run(
                [sys.executable, "-c", script],
                env=env,
                capture_output=True,
                text=True,
                check=True,
            )

            self.assertEqual(Path(result.stdout.strip()), legacy)
            self.assertTrue(legacy.exists())
            self.assertFalse(current.exists())

    def test_missing_required_env_raises(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(KeyError):
                from_env()

    def test_contract_version_zero_is_invalid(self):
        env = self._make_env()
        env["HERMESDESK_CONTRACT_VERSION"] = "0"
        with patch.dict(os.environ, env):
            cfg = from_env()
            self.assertEqual(cfg.contract_version, 0)

    def test_desk_minimal_flag(self):
        env = self._make_env()
        env["HERMESDESK_DESK_MINIMAL"] = "1"
        with patch.dict(os.environ, env):
            cfg = from_env()
            self.assertTrue(cfg.desk_minimal)


if __name__ == "__main__":
    unittest.main()
