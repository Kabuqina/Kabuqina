# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Integration test: network allowlist overlay + httpx permits STT model hosts.

Verifies that after ``overlays.network_allowlist.install()`` patches httpx,
requests to Kabuqina's package host, ``huggingface.co``, and ``hf-mirror.com``
are NOT blocked — which is required for lazy model downloads.
"""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

_REPO = Path(__file__).resolve().parents[2]
_PYTHON = _REPO / "python"
_HERMES = _REPO / "hermes_core"

# Ensure python/src is importable for network_policy
_src = str(_PYTHON / "src")
if _src not in sys.path:
    sys.path.insert(0, _src)
# Ensure python/ is importable for overlays
_py = str(_PYTHON)
if _py not in sys.path:
    sys.path.insert(0, _py)


class TestNetworkAllowlistOverlayWithHttpx(unittest.TestCase):
    """Test that the installed overlay permits STT model download URLs."""

    @classmethod
    def setUpClass(cls) -> None:
        # Install the network allowlist overlay (patches httpx.Client.send etc.)
        from overlays import network_allowlist

        network_allowlist.install()
        cls._policy = network_allowlist._policy

    def test_policy_includes_stt_hosts(self) -> None:
        """DEFAULT_ALLOW must include official and fallback model hosts."""
        hosts = self._policy.allowed_hosts
        self.assertIn("kabuqina.com", hosts, "kabuqina.com missing from allowlist")
        self.assertIn("huggingface.co", hosts, "huggingface.co missing from allowlist")
        self.assertIn("hf-mirror.com", hosts, "hf-mirror.com missing from allowlist")

    def test_check_url_permits_huggingface(self) -> None:
        """NetworkPolicy.check_url must NOT raise for STT URLs."""
        self._policy.check_url(
            "https://kabuqina.com/packages/stt/ggml-base-q5_1.bin"
        )
        self._policy.check_url(
            "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base-q5_1.bin"
        )
        self._policy.check_url(
            "https://hf-mirror.com/ggerganov/whisper.cpp/resolve/main/ggml-base-q5_1.bin"
        )

    def test_httpx_send_not_blocked_for_stt_url(self) -> None:
        """Patched httpx.Client.send must not block STT model URLs.

        The overlay installs safe_send which calls _check_url first.
        We only verify the allowlist check passes — the actual network
        call may fail with ConnectError etc., which is fine; the test
        target is that PermissionError is NOT raised.
        """
        import httpx

        request = httpx.Request(
            "GET",
            "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base-q5_1.bin",
        )
        client = httpx.Client()
        try:
            client.send(request)
        except PermissionError:
            client.close()
            self.fail("httpx.Client.send raised PermissionError for huggingface.co")
        except (httpx.ConnectError, httpx.ConnectTimeout, OSError):
            pass  # Network unavailable in CI — allowlist check passed, that's enough
        finally:
            client.close()

    def test_httpx_send_not_blocked_for_hf_mirror(self) -> None:
        """Same as above but for the hf-mirror.com fallback URL."""
        import httpx

        request = httpx.Request(
            "GET",
            "https://hf-mirror.com/ggerganov/whisper.cpp/resolve/main/ggml-base-q5_1.bin",
        )
        client = httpx.Client()
        try:
            client.send(request)
        except PermissionError:
            client.close()
            self.fail("httpx.Client.send raised PermissionError for hf-mirror.com")
        except (httpx.ConnectError, httpx.ConnectTimeout, OSError):
            pass
        finally:
            client.close()

    def test_httpx_send_still_blocks_unknown_host(self) -> None:
        """The allowlist must still block non-allowlisted hosts."""
        import httpx

        request = httpx.Request("GET", "https://evil-phishing.example.com/steal")
        client = httpx.Client()
        with self.assertRaises(PermissionError):
            client.send(request)
        client.close()

    def test_net_open_env_disables_allowlist(self) -> None:
        """HERMESDESK_NET_OPEN=1 bypasses the allowlist entirely."""
        from overlays.network_allowlist import _check_url

        with patch.dict(os.environ, {"HERMESDESK_NET_OPEN": "1"}):
            # Should not raise for any host when NET_OPEN is set
            _check_url("https://any-random-host.example.com/data")


if __name__ == "__main__":
    unittest.main()
