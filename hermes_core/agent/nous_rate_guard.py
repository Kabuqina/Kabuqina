# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0
"""Compatibility alias for :mod:`providers.nous_rate_guard`."""

from __future__ import annotations

import sys as _sys

from providers import nous_rate_guard as _impl

_sys.modules[__name__] = _impl

