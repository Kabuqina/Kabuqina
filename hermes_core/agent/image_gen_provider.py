# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0
"""Compatibility alias for :mod:`providers.image_gen_provider`."""

from __future__ import annotations

import sys as _sys

from providers import image_gen_provider as _impl

_sys.modules[__name__] = _impl

