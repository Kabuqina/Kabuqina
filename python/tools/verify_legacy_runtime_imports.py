# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Verify legacy import aliases inside an assembled desktop runtime.

Each import order runs in its own process so interpreter state from one order
cannot make the other pass accidentally.
"""

from __future__ import annotations

import importlib
import subprocess
import sys
from pathlib import Path

from verify_runtime_imports import _add_runtime_paths, _seed_import_environment


STATEFUL_SUBMODULES = ("config", "config_home", "auth")
TOP_LEVEL_ALIASES = (
    ("hermes_constants", "kabuqina_constants"),
    ("hermes_logging", "kabuqina_logging"),
    ("hermes_state", "kabuqina_state"),
    ("hermes_time", "kabuqina_time"),
)
IMPORT_ORDERS = ("legacy-first", "canonical-first")


def _verify_order(root: Path, order: str) -> None:
    _add_runtime_paths(root)
    _seed_import_environment(root)

    if order == "legacy-first":
        legacy = {
            name: importlib.import_module(f"hermes_cli.{name}")
            for name in STATEFUL_SUBMODULES
        }
        canonical = {
            name: importlib.import_module(f"kabuqina_cli.{name}")
            for name in STATEFUL_SUBMODULES
        }
    else:
        canonical = {
            name: importlib.import_module(f"kabuqina_cli.{name}")
            for name in STATEFUL_SUBMODULES
        }
        legacy = {
            name: importlib.import_module(f"hermes_cli.{name}")
            for name in STATEFUL_SUBMODULES
        }

    legacy_package = importlib.import_module("hermes_cli")
    canonical_package = importlib.import_module("kabuqina_cli")
    if legacy_package is not canonical_package:
        raise AssertionError("hermes_cli package is not the canonical package object")

    for name in STATEFUL_SUBMODULES:
        if legacy[name] is not canonical[name]:
            raise AssertionError(f"hermes_cli.{name} has separate module state")
        if sys.modules[f"hermes_cli.{name}"] is not canonical[name]:
            raise AssertionError(f"legacy sys.modules entry differs for {name}")

    marker = object()
    canonical["auth"].PROVIDER_REGISTRY["__embedded_alias_probe__"] = marker
    if legacy["auth"].PROVIDER_REGISTRY["__embedded_alias_probe__"] is not marker:
        raise AssertionError("legacy auth registry does not share canonical state")

    for legacy_name, canonical_name in TOP_LEVEL_ALIASES:
        if importlib.import_module(legacy_name) is not importlib.import_module(
            canonical_name
        ):
            raise AssertionError(f"{legacy_name} is not {canonical_name}")


def _run_isolated_orders(root: Path) -> int:
    for order in IMPORT_ORDERS:
        result = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), str(root), "--order", order],
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            print(
                f"legacy runtime identity failed ({order}):\n"
                f"{result.stdout}{result.stderr}",
                file=sys.stderr,
            )
            return result.returncode
    print(
        "legacy runtime identity ok: "
        + ", ".join(STATEFUL_SUBMODULES)
        + "; orders: "
        + ", ".join(IMPORT_ORDERS)
    )
    return 0


def main(argv: list[str]) -> int:
    if len(argv) not in (2, 4):
        print(
            "usage: verify_legacy_runtime_imports.py <runtime-root> "
            "[--order legacy-first|canonical-first]",
            file=sys.stderr,
        )
        return 2

    root = Path(argv[1]).resolve()
    if not root.is_dir():
        print(f"runtime root not found: {root}", file=sys.stderr)
        return 2

    if len(argv) == 4:
        if argv[2] != "--order" or argv[3] not in IMPORT_ORDERS:
            print("invalid import order", file=sys.stderr)
            return 2
        try:
            _verify_order(root, argv[3])
        except Exception as exc:
            print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
            return 1
        return 0

    return _run_isolated_orders(root)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
