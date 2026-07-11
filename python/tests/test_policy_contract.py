# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for policy objects (no Hermes import chain needed)."""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

# Add python/src to path for test-time imports
_src = str(Path(__file__).resolve().parent.parent / "src")
if _src not in sys.path:
    sys.path.insert(0, _src)

from path_policy import PathPolicy, PathPolicyError, _HOST_PREFS_FILENAME
from network_policy import NetworkPolicy
from tool_policy import ToolPolicy
from secret_store import SecretStore
from approval_backend import _auto_approve_workspace_read
from capability_policy import CapabilityPolicy, ROLE_ADVANCED, ROLE_DEFAULT, ROLE_POWER


class TestPathPolicy(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.gettempdir()) / "hermesdesk-test-workspace"
        self.read_dir = Path(tempfile.gettempdir()) / "hermesdesk-test-readonly"
        self.write_dir = Path(tempfile.gettempdir()) / "hermesdesk-test-writable"
        self.policy = PathPolicy(
            self.root,
            extra_read=[self.read_dir],
            extra_write=[self.write_dir],
        )

    def test_workspace_root(self):
        self.assertEqual(self.policy.workspace_root, self.root)

    def test_valid_path_under_root(self):
        result = self.policy.enforce(self.root / "file.txt", write=True)
        self.assertEqual(result, self.root / "file.txt")

    def test_valid_path_extra_read(self):
        result = self.policy.enforce(self.read_dir / "data.txt", write=False)
        self.assertEqual(result, self.read_dir / "data.txt")

    def test_valid_path_extra_write(self):
        result = self.policy.enforce(self.write_dir / "out.txt", write=True)
        self.assertEqual(result, self.write_dir / "out.txt")

    def test_block_escaped_path(self):
        with self.assertRaises(PathPolicyError):
            self.policy.enforce(Path(os.sep) / "etc" / "passwd", write=True)

    def test_read_only_on_write_extra(self):
        result = self.policy.enforce(self.write_dir / "out.txt", write=False)
        self.assertEqual(result, self.write_dir / "out.txt")

    # -- _host_prefs.md write guard for gateway children -------------------

    def test_gateway_child_cannot_write_host_prefs(self):
        """HERMESDESK_GATEWAY_PLATFORM set → write to _host_prefs.md blocked."""
        with patch.dict(os.environ, {"HERMESDESK_GATEWAY_PLATFORM": "weixin"}, clear=True):
            # Reset class-level cache
            PathPolicy._is_gateway_child = None
            self.addCleanup(lambda: setattr(PathPolicy, "_is_gateway_child", None))
            with self.assertRaises(PathPolicyError) as ctx:
                self.policy.enforce(self.root / _HOST_PREFS_FILENAME, write=True)
            self.assertIn(_HOST_PREFS_FILENAME, str(ctx.exception))

    def test_host_can_write_host_prefs(self):
        """HERMESDESK_GATEWAY_PLATFORM not set → write to _host_prefs.md allowed."""
        with patch.dict(os.environ, {}, clear=True):
            PathPolicy._is_gateway_child = None
            self.addCleanup(lambda: setattr(PathPolicy, "_is_gateway_child", None))
            result = self.policy.enforce(self.root / _HOST_PREFS_FILENAME, write=True)
            self.assertEqual(result, self.root / _HOST_PREFS_FILENAME)

    def test_gateway_child_can_write_normal_file(self):
        """Gateway env set, but other files are NOT blocked."""
        with patch.dict(os.environ, {"HERMESDESK_GATEWAY_PLATFORM": "weixin"}, clear=True):
            PathPolicy._is_gateway_child = None
            self.addCleanup(lambda: setattr(PathPolicy, "_is_gateway_child", None))
            result = self.policy.enforce(self.root / "MEMORY.md", write=True)
            self.assertEqual(result, self.root / "MEMORY.md")

    def test_gateway_child_can_read_host_prefs(self):
        """Reading _host_prefs.md is NOT blocked (only writes are)."""
        with patch.dict(os.environ, {"HERMESDESK_GATEWAY_PLATFORM": "weixin"}, clear=True):
            PathPolicy._is_gateway_child = None
            self.addCleanup(lambda: setattr(PathPolicy, "_is_gateway_child", None))
            result = self.policy.enforce(self.root / _HOST_PREFS_FILENAME, write=False)
            self.assertEqual(result, self.root / _HOST_PREFS_FILENAME)

    @unittest.skipUnless(os.name == "nt", "Windows device paths")
    def test_allows_windows_nul_device(self):
        for spec in (r"\\.\nul", r"\\.\nul\\", r"\\.\NUL", r"\\.\NUL:", "NUL", "NUL:", b"NUL"):
            self.policy.enforce(spec, write=False)
            self.policy.enforce(spec, write=True)

    @unittest.skipUnless(os.name == "nt", "Windows device paths")
    def test_still_blocks_other_windows_devices(self):
        with self.assertRaises(PathPolicyError):
            self.policy.enforce(r"\\.\C:\Windows\System32\drivers\etc\hosts", write=False)


class TestNetworkPolicy(unittest.TestCase):
    def setUp(self):
        self.policy = NetworkPolicy(llm_host="openrouter.ai", extra_hosts="example.com")

    def test_allows_localhost(self):
        self.policy.check_url("http://127.0.0.1:8080/api")
        self.policy.check_url("http://localhost:8080/api")
        self.policy.check_url("http://[::1]:8080/api")

    def test_allows_default_allow_hosts(self):
        self.policy.check_url("https://speech.platform.bing.com/tts")

    def test_allows_llm_host(self):
        self.policy.check_url("https://openrouter.ai/api/v1/chat/completions")

    def test_allows_extra_host(self):
        self.policy.check_url("https://example.com/data")

    def test_blocks_unknown_host(self):
        with self.assertRaises(PermissionError):
            self.policy.check_url("https://evil.example.com/data")

    def test_default_policy_blocks_unknown(self):
        policy = NetworkPolicy()
        with self.assertRaises(PermissionError):
            policy.check_url("https://unknown.host/data")

    def test_default_policy_allows_localhost(self):
        policy = NetworkPolicy()
        policy.check_url("http://127.0.0.1:8080/api")

    def test_allows_stt_model_hosts(self):
        """STT model download URLs must be reachable."""
        policy = NetworkPolicy()
        policy.check_url("https://kabuqina.com/packages/stt/ggml-base-q5_1.bin")
        policy.check_url("https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base-q5_1.bin")
        policy.check_url("https://hf-mirror.com/ggerganov/whisper.cpp/resolve/main/ggml-base-q5_1.bin")

    def test_allows_mainland_provider_hosts_by_default(self):
        """The active profile seeds retained China provider hosts (mainland_cn)."""
        with patch.dict(os.environ, {"KABUQINA_PRODUCT_PROFILE": "mainland_cn"}):
            policy = NetworkPolicy()
            policy.check_url("https://api.deepseek.com/v1/chat/completions")
            policy.check_url("https://api.kimi.com/coding/v1/models")
            policy.check_url("https://dashscope-intl.aliyuncs.com/api/v1")


class TestToolPolicy(unittest.TestCase):
    def test_default_mode_tools(self):
        # mainland_cn drops image_gen (FAL.ai-only backend, no China backend).
        with patch.dict(os.environ, {"KABUQINA_PRODUCT_PROFILE": "mainland_cn"}):
            tools = ToolPolicy.resolve(power_user=False)
        self.assertEqual(
            tools,
            [
                "web", "file", "vision", "tts", "skills", "clock", "todo", "browser",
                "clarify", "documents", "math", "learning", "cronjob", "messaging",
            ],
        )
        self.assertNotIn("image_gen", tools)

    def test_power_user_mode_tools(self):
        with patch.dict(os.environ, {"KABUQINA_PRODUCT_PROFILE": "mainland_cn"}):
            tools = ToolPolicy.resolve(power_user=True)
        self.assertEqual(len(tools), 17)
        self.assertTrue("terminal" in tools)
        self.assertTrue("browser" in tools)
        self.assertTrue("cronjob" in tools)
        self.assertTrue("messaging" in tools)
        self.assertTrue("learning" in tools)
        self.assertTrue("code_execution" in tools)
        self.assertTrue("moa" in tools)
        self.assertNotIn("image_gen", tools)

    def test_default_keeps_safe_tools(self):
        tools = ToolPolicy.resolve(power_user=False)
        self.assertNotIn("terminal", tools)
        self.assertNotIn("code_execution", tools)
        self.assertIn("learning", tools)

    def test_gateway_keep_list_includes_default_delivery_tools(self):
        with patch.dict(os.environ, {"KABUQINA_PRODUCT_PROFILE": "mainland_cn"}):
            tools = ToolPolicy.gateway_keep_list()
        self.assertEqual(
            tools,
            [
                "web", "file", "vision", "tts", "skills", "clock", "todo", "browser",
                "clarify", "documents", "math", "learning", "cronjob", "messaging",
            ],
        )

    def test_is_power_user_from_env(self):
        with patch.dict(os.environ, {"HERMESDESK_POWER_USER": "1"}):
            self.assertTrue(ToolPolicy.is_power_user())
        with patch.dict(os.environ, {"HERMESDESK_POWER_USER": "0"}):
            self.assertFalse(ToolPolicy.is_power_user())

    def test_is_power_user_default(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(ToolPolicy.is_power_user())


class TestCapabilityPolicy(unittest.TestCase):
    def test_effective_role(self):
        self.assertEqual(
            CapabilityPolicy.effective_role(power_user=False, show_recipe_market=False),
            ROLE_DEFAULT,
        )
        self.assertEqual(
            CapabilityPolicy.effective_role(power_user=False, show_recipe_market=True),
            ROLE_ADVANCED,
        )
        self.assertEqual(
            CapabilityPolicy.effective_role(power_user=True, show_recipe_market=False),
            ROLE_POWER,
        )

    def test_show_recipe_market_reads_data_file_when_env_is_missing(self):
        with tempfile.TemporaryDirectory() as data_dir:
            Path(data_dir, "kabuqina_show_recipe_market.txt").write_text(
                "1\n", encoding="utf-8"
            )
            with patch.dict(
                os.environ, {"KABUQINA_DATA_DIR": data_dir}, clear=True
            ):
                self.assertTrue(CapabilityPolicy._read_show_recipe_market())

    def test_show_recipe_market_explicit_empty_env_beats_data_file(self):
        with tempfile.TemporaryDirectory() as data_dir:
            Path(data_dir, "kabuqina_show_recipe_market.txt").write_text(
                "1\n", encoding="utf-8"
            )
            with patch.dict(
                os.environ,
                {
                    "KABUQINA_DATA_DIR": data_dir,
                    "KABUQINA_SHOW_RECIPE_MARKET": "",
                },
                clear=True,
            ):
                self.assertFalse(CapabilityPolicy._read_show_recipe_market())

    def test_untagged_skill_is_visible_to_default(self):
        policy = CapabilityPolicy(ROLE_DEFAULT)
        visibility = policy.skill_visibility({"name": "built-in"})
        self.assertTrue(visibility["visible"])
        self.assertEqual(visibility["roles"], [ROLE_DEFAULT, ROLE_ADVANCED, ROLE_POWER])

    def test_community_skill_defaults_to_power_only(self):
        policy = CapabilityPolicy(ROLE_DEFAULT)
        visibility = policy.skill_visibility({"name": "external", "source": "github"})
        self.assertFalse(visibility["visible"])
        self.assertEqual(visibility["roles"], [ROLE_POWER])

    def test_metadata_roles_are_respected(self):
        policy = CapabilityPolicy(ROLE_ADVANCED)
        visibility = policy.skill_visibility(
            {
                "name": "signed-recipe",
                "metadata": {
                    "hermesdesk": {
                        "visibility": {"roles": ["advanced", "power"]},
                        "trust": "official",
                        "recommended": True,
                    }
                },
            }
        )
        self.assertTrue(visibility["visible"])
        self.assertTrue(visibility["recommended"])
        self.assertEqual(visibility["risk"], "medium")

    def test_power_toolsets_are_locked_outside_power(self):
        policy = CapabilityPolicy(ROLE_DEFAULT)
        terminal = policy.tool_visibility({"name": "terminal"})
        web = policy.tool_visibility({"name": "web"})
        self.assertTrue(terminal["locked"])
        self.assertEqual(terminal["roles"], [ROLE_POWER])
        self.assertEqual(web["trust"], "official")
        self.assertFalse(web["locked"])

    def test_default_product_toolsets_are_visible_to_default_role(self):
        policy = CapabilityPolicy(ROLE_DEFAULT)
        for name in ToolPolicy.resolve(power_user=False):
            with self.subTest(toolset=name):
                visibility = policy.tool_visibility({"name": name})
                self.assertIn(ROLE_DEFAULT, visibility["roles"])
                self.assertFalse(visibility["locked"])

    def test_plugins_default_to_advanced(self):
        policy = CapabilityPolicy(ROLE_DEFAULT)
        visibility = policy.plugin_visibility({"name": "example"})
        self.assertFalse(visibility["visible"])
        self.assertEqual(visibility["roles"], [ROLE_ADVANCED, ROLE_POWER])
        self.assertEqual(visibility["trust"], "official")

    def test_bundled_plugin_defaults_to_official_trust(self):
        policy = CapabilityPolicy(ROLE_ADVANCED)
        visibility = policy.plugin_visibility({"name": "builtin-plugin", "source": "bundled"})
        self.assertTrue(visibility["visible"])
        self.assertEqual(visibility["trust"], "official")


class TestSecretStore(unittest.TestCase):
    def test_no_op_when_no_url(self):
        with patch.dict(os.environ, {}, clear=True):
            store = SecretStore()
            result = store.fetch()
            self.assertIsNone(result)

    def test_no_op_with_url_but_no_provider(self):
        with patch.dict(os.environ, {"HERMESDESK_SECRET_URL": "http://127.0.0.1:1234/secret/token"}, clear=True):
            store = SecretStore()
            result = store.fetch()
            self.assertIsNone(result)

    def test_provider_env_map_covers_native_hermes_providers(self):
        from secret_store import _PROVIDER_ENV

        self.assertEqual(_PROVIDER_ENV["alibaba"], "DASHSCOPE_API_KEY")
        self.assertEqual(_PROVIDER_ENV["zai"], "GLM_API_KEY")
        self.assertEqual(_PROVIDER_ENV["kimi-coding"], "KIMI_API_KEY")
        self.assertEqual(_PROVIDER_ENV["kimi-coding-cn"], "KIMI_CN_API_KEY")
        self.assertEqual(_PROVIDER_ENV["minimax"], "MINIMAX_API_KEY")
        self.assertEqual(_PROVIDER_ENV["minimax-cn"], "MINIMAX_CN_API_KEY")


class TestApprovalBackendPolicy(unittest.TestCase):
    def setUp(self):
        self.workspace = Path(tempfile.gettempdir()) / "hermesdesk-approval-workspace"

    def test_auto_approves_simple_workspace_read(self):
        with patch.dict(os.environ, {"HERMESDESK_WORKSPACE": str(self.workspace)}):
            self.assertTrue(_auto_approve_workspace_read("Get-Content notes.txt"))
            self.assertTrue(_auto_approve_workspace_read("type notes.txt"))

    def test_blocks_workspace_read_with_shell_composition(self):
        with patch.dict(os.environ, {"HERMESDESK_WORKSPACE": str(self.workspace)}):
            self.assertFalse(_auto_approve_workspace_read("Get-Content notes.txt | powershell -c whoami"))
            self.assertFalse(_auto_approve_workspace_read("type notes.txt > copy.txt"))

    def test_blocks_reads_outside_workspace(self):
        outside = Path(tempfile.gettempdir()).parent / "outside.txt"
        with patch.dict(os.environ, {"HERMESDESK_WORKSPACE": str(self.workspace)}):
            self.assertFalse(_auto_approve_workspace_read(f"Get-Content {outside}"))

    def test_auto_approves_literal_python_workspace_read(self):
        with patch.dict(os.environ, {"HERMESDESK_WORKSPACE": str(self.workspace)}):
            self.assertTrue(
                _auto_approve_workspace_read(
                    'python -c "from pathlib import Path; print(Path(\'notes.txt\').read_text())"'
                )
            )

    def test_auto_approves_python_presentation_readers(self):
        with patch.dict(os.environ, {"HERMESDESK_WORKSPACE": str(self.workspace)}):
            self.assertTrue(
                _auto_approve_workspace_read(
                    'python -c "from pptx import Presentation; ppt_path = \'deck.pptx\'; '
                    'prs = Presentation(ppt_path); print(len(prs.slides))"'
                )
            )
            self.assertTrue(
                _auto_approve_workspace_read(
                    'python -c "import zipfile; z = zipfile.ZipFile(\'.hermesdesk_uploads/s1/deck.pptx\'); '
                    'print(z.namelist())"'
                )
            )

    def test_blocks_python_presentation_readers_outside_workspace(self):
        outside = Path(tempfile.gettempdir()).parent / "deck.pptx"
        with patch.dict(os.environ, {"HERMESDESK_WORKSPACE": str(self.workspace)}):
            self.assertFalse(
                _auto_approve_workspace_read(
                    f'python -c "from pptx import Presentation; Presentation(r\'{outside}\')"'
                )
            )

    def test_auto_approves_python_read_with_workspace_alias_env(self):
        with patch.dict(os.environ, {"HERMES_WORKSPACE": str(self.workspace)}, clear=True):
            self.assertTrue(
                _auto_approve_workspace_read(
                    'python -c "from pathlib import Path; p = \'notes.txt\'; print(Path(p).read_text())"'
                )
            )

    def test_blocks_python_write_and_subprocess(self):
        with patch.dict(os.environ, {"HERMESDESK_WORKSPACE": str(self.workspace)}):
            self.assertFalse(
                _auto_approve_workspace_read(
                    'python -c "from pathlib import Path; Path(\'notes.txt\').write_text(\'x\')"'
                )
            )
            self.assertFalse(
                _auto_approve_workspace_read(
                    'python -c "import subprocess; subprocess.run([\'cmd\', \'/c\', \'type\', \'notes.txt\'])"'
                )
            )


    def test_auto_approves_copy_into_workspace(self):
        dest = self.workspace / "imported.pdf"
        outside = Path(tempfile.gettempdir()).parent / "outside.pdf"
        with patch.dict(os.environ, {"HERMESDESK_WORKSPACE": str(self.workspace)}):
            self.assertTrue(
                _auto_approve_workspace_read(f'cp "{outside}" "{dest}"')
            )
            self.assertTrue(
                _auto_approve_workspace_read(f'copy "{outside}" "{dest}"')
            )
            self.assertTrue(
                _auto_approve_workspace_read(
                    f'Copy-Item -Path "{outside}" -Destination "{dest}"'
                )
            )

    def test_auto_approves_git_bash_copy_into_workspace(self):
        dest = self.workspace / "report.pdf"
        with patch.dict(os.environ, {"HERMESDESK_WORKSPACE": str(self.workspace)}):
            self.assertTrue(
                _auto_approve_workspace_read(
                    f'cp "/d/tmp/report.pdf" "/c{str(dest)[2:].replace(chr(92), "/")}"'
                )
            )

    def test_blocks_copy_outside_workspace(self):
        outside_dest = Path(tempfile.gettempdir()).parent / "leak.pdf"
        src = self.workspace / "notes.txt"
        with patch.dict(os.environ, {"HERMESDESK_WORKSPACE": str(self.workspace)}):
            self.assertFalse(
                _auto_approve_workspace_read(f'cp "{src}" "{outside_dest}"')
            )
            self.assertFalse(
                _auto_approve_workspace_read('cp "/d/tmp/report.pdf" "/d/tmp/report-copy.pdf"')
            )

    def test_power_user_auto_approves_read_outside_workspace(self):
        outside = Path(tempfile.gettempdir()).parent / "report.txt"
        env = {
            "HERMESDESK_WORKSPACE": str(self.workspace),
            "HERMESDESK_POWER_USER": "1",
        }
        with patch.dict(os.environ, env):
            self.assertTrue(_auto_approve_workspace_read(f"Get-Content {outside}"))
            self.assertTrue(_auto_approve_workspace_read(f"type {outside}"))

    def test_power_user_auto_approves_python_read_outside_workspace(self):
        outside = Path(tempfile.gettempdir()).parent / "deck.pptx"
        env = {
            "HERMESDESK_WORKSPACE": str(self.workspace),
            "HERMESDESK_POWER_USER": "1",
        }
        with patch.dict(os.environ, env):
            self.assertTrue(
                _auto_approve_workspace_read(
                    f'python -c "from pptx import Presentation; Presentation(r\'{outside}\')"'
                )
            )

    def test_power_user_still_blocks_writes_and_copy_outside(self):
        outside_dest = Path(tempfile.gettempdir()).parent / "leak.pdf"
        src = self.workspace / "notes.txt"
        env = {
            "HERMESDESK_WORKSPACE": str(self.workspace),
            "HERMESDESK_POWER_USER": "1",
        }
        with patch.dict(os.environ, env):
            # Reads broaden, but data must not leave the workspace via copy …
            self.assertFalse(
                _auto_approve_workspace_read(f'cp "{src}" "{outside_dest}"')
            )
            # … nor via a Python write call.
            self.assertFalse(
                _auto_approve_workspace_read(
                    'python -c "from pathlib import Path; Path(\'notes.txt\').write_text(\'x\')"'
                )
            )
            # Shell composition stays gated regardless of mode.
            self.assertFalse(
                _auto_approve_workspace_read("Get-Content notes.txt | powershell -c whoami")
            )


if __name__ == "__main__":
    unittest.main()
