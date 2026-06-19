# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Agent facade for Kabuqina callers.

A thin name redirect to the legacy ``run_agent`` entrypoint. Keeping it as a
re-export (not a copy) means ``kabuqina_core.agent.AIAgent is run_agent.AIAgent``
stays true through the migration, which the compat guardrail asserts.
"""

from run_agent import AIAgent

__all__ = ["AIAgent"]
