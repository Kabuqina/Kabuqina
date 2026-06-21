# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0
"""Compatibility alias for :mod:`providers.chat_completions`."""

from __future__ import annotations

import sys as _sys

from providers import chat_completions as _impl

_sys.modules[__name__] = _impl

