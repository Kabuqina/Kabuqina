# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0
"""Structured auth error type and its user-facing formatter.

Zero-dependency leaf: a provider runtime module can ``raise AuthError(...)``
without importing the CLI ``kabuqina_cli.auth`` facade, so the per-provider
credential resolvers can live in their own ``providers/*`` modules without an
import cycle. ``kabuqina_cli.auth`` re-exports both names for existing callers.
"""

from __future__ import annotations

from typing import Optional


class AuthError(RuntimeError):
    """Structured auth error with UX mapping hints."""

    def __init__(
        self,
        message: str,
        *,
        provider: str = "",
        code: Optional[str] = None,
        relogin_required: bool = False,
    ) -> None:
        super().__init__(message)
        self.provider = provider
        self.code = code
        self.relogin_required = relogin_required


def format_auth_error(error: Exception) -> str:
    """Map auth failures to concise user-facing guidance."""
    if not isinstance(error, AuthError):
        return str(error)

    if error.relogin_required:
        return f"{error} Run `kabuqina model` to re-authenticate."

    if error.code == "subscription_required":
        return (
            "No active paid subscription found on Nous Portal. "
            "Please purchase/activate a subscription, then retry."
        )

    if error.code == "insufficient_credits":
        return (
            "Subscription credits are exhausted. "
            "Top up/renew credits in Nous Portal, then retry."
        )

    if error.code == "temporarily_unavailable":
        return f"{error} Please retry in a few seconds."

    return str(error)
