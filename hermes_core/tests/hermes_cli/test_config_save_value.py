# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Tests for hermes_cli.config.save_config_value.

Relocated from cli.py so the gateway/desktop runtime no longer imports the CLI
to persist a config value. Mirrors the behaviour the old
tests/cli/test_cli_save_config_value.py pinned, but against the retained module.
"""

import yaml


def _read(path):
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def test_creates_nested_keys(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    from hermes_cli.config import save_config_value, get_config_path

    assert save_config_value("approvals.mcp_reload_confirm", False) is True
    data = _read(get_config_path())
    assert data["approvals"]["mcp_reload_confirm"] is False


def test_overwrites_and_preserves_siblings(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    from hermes_cli.config import save_config_value, get_config_path

    cfg = get_config_path()
    cfg.write_text(yaml.safe_dump({"model": "keep/me", "approvals": {"other": 1}}), encoding="utf-8")

    assert save_config_value("approvals.mcp_reload_confirm", True) is True
    data = _read(cfg)
    assert data["model"] == "keep/me"          # unrelated key preserved
    assert data["approvals"]["other"] == 1      # sibling preserved
    assert data["approvals"]["mcp_reload_confirm"] is True
