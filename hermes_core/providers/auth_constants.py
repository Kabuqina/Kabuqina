# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0
"""Provider OAuth constants (Nous Portal, MiniMax) — a zero-import leaf.

Shared by the provider runtime resolver modules (``providers.nous_auth``,
``providers.minimax_auth``) and the ``kabuqina_cli.auth`` facade. Living here (with
no imports of its own) lets both sides import these values *downward* without
``providers.*_auth`` and ``kabuqina_cli.auth`` importing each other at module load
(which is a circular import). ``kabuqina_cli.auth`` re-exports every name.
"""

from __future__ import annotations

# Nous Portal defaults
DEFAULT_NOUS_PORTAL_URL = "https://portal.nousresearch.com"
DEFAULT_NOUS_INFERENCE_URL = "https://inference-api.nousresearch.com/v1"
DEFAULT_NOUS_CLIENT_ID = "kabuqina-cli"
DEFAULT_NOUS_SCOPE = "inference:mint_agent_key"
DEFAULT_AGENT_KEY_MIN_TTL_SECONDS = 30 * 60  # 30 minutes
ACCESS_TOKEN_REFRESH_SKEW_SECONDS = 120       # refresh 2 min before expiry
DEVICE_AUTH_POLL_INTERVAL_CAP_SECONDS = 1     # poll at most every 1s

# MiniMax Portal OAuth
MINIMAX_OAUTH_CLIENT_ID = "78257093-7e40-4613-99e0-527b14b39113"
MINIMAX_OAUTH_SCOPE = "group_id profile model.completion"
MINIMAX_OAUTH_GRANT_TYPE = "urn:ietf:params:oauth:grant-type:user_code"
MINIMAX_OAUTH_GLOBAL_BASE = "https://api.minimax.io"
MINIMAX_OAUTH_CN_BASE = "https://api.minimaxi.com"
MINIMAX_OAUTH_GLOBAL_INFERENCE = "https://api.minimax.io/anthropic"
MINIMAX_OAUTH_CN_INFERENCE = "https://api.minimaxi.com/anthropic"
MINIMAX_OAUTH_REFRESH_SKEW_SECONDS = 60
