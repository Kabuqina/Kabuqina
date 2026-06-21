# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0
"""Compatibility alias for :mod:`providers.transports`."""

from __future__ import annotations

import importlib as _importlib
import sys as _sys

_impl = _importlib.import_module("providers.transports")

for _submodule in (
    "types",
    "base",
    "anthropic",
    "bedrock",
    "chat_completions",
    "codex",
):
    _sub_impl = _importlib.import_module(f"providers.transports.{_submodule}")
    _sys.modules[f"{__name__}.{_submodule}"] = _sub_impl

_sys.modules[__name__] = _impl

