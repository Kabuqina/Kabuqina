"""Deprecated package alias for :mod:`kabuqina_cli`.

The compatibility package and every one of its submodules share the canonical
module objects for one release.  A top-level ``sys.modules`` alias alone is not
enough: without the finder below, ``import hermes_cli.config`` executes
``kabuqina_cli/config.py`` a second time under the legacy name and creates
separate registries and caches.
"""

from __future__ import annotations

import importlib
import importlib.abc
import importlib.util
import sys


_LEGACY_PREFIX = f"{__name__}."
_CANONICAL_PREFIX = "kabuqina_cli."


class _LegacyCliAliasLoader(importlib.abc.Loader):
    """Return an existing canonical submodule for a legacy import name."""

    def __init__(self, legacy_name: str, canonical_name: str) -> None:
        self.legacy_name = legacy_name
        self.canonical_name = canonical_name

    def create_module(self, spec):  # noqa: ANN001
        del spec
        return importlib.import_module(self.canonical_name)

    def exec_module(self, module) -> None:  # noqa: ANN001
        sys.modules[self.legacy_name] = module


class _LegacyCliAliasFinder(importlib.abc.MetaPathFinder):
    """Map ``hermes_cli.*`` imports onto the canonical package namespace."""

    kabuqina_legacy_cli_alias_finder = True

    def find_spec(self, fullname, path=None, target=None):  # noqa: ANN001
        del path, target
        if not fullname.startswith(_LEGACY_PREFIX):
            return None

        canonical_name = _CANONICAL_PREFIX + fullname[len(_LEGACY_PREFIX) :]
        canonical_spec = importlib.util.find_spec(canonical_name)
        if canonical_spec is None:
            return None

        loader = _LegacyCliAliasLoader(fullname, canonical_name)
        return importlib.util.spec_from_loader(
            fullname,
            loader,
            origin=canonical_spec.origin,
            is_package=canonical_spec.submodule_search_locations is not None,
        )


if not any(
    getattr(finder, "kabuqina_legacy_cli_alias_finder", False)
    for finder in sys.meta_path
):
    sys.meta_path.insert(0, _LegacyCliAliasFinder())

_canonical = importlib.import_module("kabuqina_cli")
sys.modules[__name__] = _canonical
