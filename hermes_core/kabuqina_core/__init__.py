# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Kabuqina-owned facade over the legacy Hermes core during migration.

Phase A (v0.3.0 slim & focus) introduces only the agent facade, as a cheap
guardrail that the retained agent entrypoint keeps importing. The config /
web_server facades and the physical ``hermes_core`` -> ``kabuqina_core`` rename
land with the v0.4.0 core rename (refactor plan Phases 1 and 9), not here.
"""

__all__ = ["agent"]
