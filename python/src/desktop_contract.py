# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Versioned Tauri <-> Python contract.

The Tauri shell sets ``HERMESDESK_CONTRACT_VERSION`` before spawning the
Python child.  The child validates this at startup and refuses to run if
the versions don't match — this prevents a stale or mis-built Python
bundle from booting with mismatched env-var assumptions.

Add new fields to ``HEALTH_SCHEMA`` or ``CONFIG_SCHEMA`` when the
surface area changes; bump ``CONTRACT_VERSION``.
"""

CONTRACT_VERSION = 1

HEALTH_SCHEMA: dict = {
    "version": CONTRACT_VERSION,
    "fields": ["pid", "port", "uptime_seconds", "overlays_ok", "hermes_importable"],
}

CONFIG_SCHEMA: dict = {
    "version": CONTRACT_VERSION,
    "fields": [
        "provider",
        "llm_host",
        "power_user",
        "workspace",
        "bundle_dir",
        "data_dir",
    ],
}

STATUS_SCHEMA: dict = {
    "version": CONTRACT_VERSION,
    "fields": ["running", "pid", "port", "runtime_mode"],
}
