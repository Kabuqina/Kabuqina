# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""HermesDesk typed bootstrap configuration.

Reads from Tauri-provided env vars. No behavior dependencies — pure data.
Used by the entrypoint and will eventually be injected into policy objects
(Phase 3) instead of the current monkey-patch overlays.
"""

from __future__ import annotations

import enum
import os
from dataclasses import dataclass, field
from pathlib import Path


class RuntimeMode(enum.Enum):
    DEFAULT = "default"
    POWER_USER = "power_user"
    GATEWAY_ENABLED = "gateway_enabled"


@dataclass
class DesktopConfig:
    """All runtime parameters the Tauri shell passes to the Python child."""

    # ── core paths ──────────────────────────────────────────────────────
    bundle_dir: Path
    data_dir: Path
    workspace: Path
    port_file: Path | None

    # ── contract ────────────────────────────────────────────────────────
    contract_version: int = 1

    # ── LLM provider ────────────────────────────────────────────────────
    provider: str = "openrouter"
    llm_host: str = "openrouter.ai"
    api_base_url: str | None = None
    hermes_model: str | None = None
    inference_provider: str | None = None

    # ── bridge ──────────────────────────────────────────────────────────
    secret_url: str | None = None
    approval_url: str | None = None
    bridge_secret: str | None = None
    shell_chat_url: str | None = None

    # ── mode ────────────────────────────────────────────────────────────
    power_user: bool = False
    desk_minimal: bool = False

    @property
    def runtime_mode(self) -> RuntimeMode:
        if self.power_user:
            return RuntimeMode.POWER_USER
        return RuntimeMode.DEFAULT

    # ── computed convenience ────────────────────────────────────────────

    @property
    def hermes_home(self) -> Path:
        return self.data_dir / "hermes-home"


def from_env() -> DesktopConfig:
    return DesktopConfig(
        bundle_dir=Path(os.environ["HERMESDESK_BUNDLE_DIR"]),
        data_dir=Path(os.environ["HERMESDESK_DATA_DIR"]),
        workspace=Path(os.environ["HERMESDESK_WORKSPACE"]),
        port_file=_opt_path("HERMESDESK_PORT_FILE"),
        contract_version=int(os.environ.get("HERMESDESK_CONTRACT_VERSION", "0")),
        provider=os.environ.get("HERMESDESK_PROVIDER", "openrouter"),
        llm_host=os.environ.get("HERMESDESK_LLM_HOST", "openrouter.ai"),
        api_base_url=_opt_str("HERMESDESK_API_BASE_URL"),
        hermes_model=_opt_str("HERMESDESK_MODEL"),
        inference_provider=_opt_str("HERMESDESK_INFERENCE_PROVIDER"),
        secret_url=_opt_str("HERMESDESK_SECRET_URL"),
        approval_url=_opt_str("HERMESDESK_APPROVAL_URL"),
        bridge_secret=_opt_str("HERMESDESK_BRIDGE_SECRET"),
        shell_chat_url=_opt_str("HERMESDESK_SHELL_CHAT_URL"),
        power_user=os.environ.get("HERMESDESK_POWER_USER") == "1",
        desk_minimal=os.environ.get("HERMESDESK_DESK_MINIMAL") == "1",
    )


def _opt_str(key: str) -> str | None:
    v = os.environ.get(key, "").strip()
    return v if v else None


def _opt_path(key: str) -> Path | None:
    v = os.environ.get(key, "").strip()
    return Path(v) if v else None
