# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def test_docling_warmup_is_disabled_by_default(monkeypatch, caplog):
    import desktop_entrypoint

    monkeypatch.delenv("HERMESDESK_DOCLING_WARMUP", raising=False)
    desktop_entrypoint._docling_warm_thread = None

    with caplog.at_level(logging.INFO):
        desktop_entrypoint._warm_docling_async(logging.getLogger("test"))

    assert desktop_entrypoint._docling_warm_thread is None
    assert "Docling warmup disabled" in caplog.text


def test_torch_prime_is_opt_in_by_default(monkeypatch, caplog):
    import desktop_entrypoint

    monkeypatch.delenv("HERMESDESK_TORCH_PRIME", raising=False)

    with caplog.at_level(logging.INFO):
        did_prime = desktop_entrypoint._prime_torch_main_thread(logging.getLogger("test"))

    assert did_prime is False
    assert "Docling torch prime disabled" in caplog.text
