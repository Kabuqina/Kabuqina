# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Write an artifact-level Python/Node dependency and license inventory."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _canonical_name(value: str) -> str:
    return re.sub(r"[-_.]+", "-", value).lower()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _direct_requirements(path: Path) -> list[str]:
    names: list[str] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        match = re.match(r"([A-Za-z0-9_.-]+)(?:\[[^\]]+\])?", line)
        if not match:
            raise ValueError(f"unsupported desktop requirement: {raw_line!r}")
        names.append(_canonical_name(match.group(1)))
    return sorted(set(names))


def _compact_metadata(value: str | None, limit: int = 512) -> str | None:
    compact = " ".join(str(value or "").split())
    if not compact:
        return None
    return compact if len(compact) <= limit else compact[:limit] + "…"


def _python_inventory(site_packages: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for distribution in importlib.metadata.Distribution.discover(path=[str(site_packages)]):
        metadata = distribution.metadata
        name = str(metadata.get("Name") or "").strip()
        if not name:
            continue
        classifiers = metadata.get_all("Classifier") or []
        license_classifiers = sorted(
            item.removeprefix("License :: ").strip()
            for item in classifiers
            if item.startswith("License :: ")
        )
        records.append({
            "name": name,
            "canonical_name": _canonical_name(name),
            "version": distribution.version,
            "license_expression": _compact_metadata(metadata.get("License-Expression")),
            "license_metadata": _compact_metadata(metadata.get("License")),
            "license_classifiers": license_classifiers,
        })
    return sorted(records, key=lambda item: item["canonical_name"])


def _node_inventory(lock_path: Path) -> list[dict[str, Any]]:
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    records: list[dict[str, Any]] = []
    for package_path, package in sorted((lock.get("packages") or {}).items()):
        if not package_path or not package_path.startswith("node_modules/"):
            continue
        name = package_path.removeprefix("node_modules/")
        records.append({
            "name": name,
            "version": package.get("version"),
            "license": package.get("license"),
            "resolved": package.get("resolved"),
            "integrity": package.get("integrity"),
        })
    return records


def generate(
    runtime: Path,
    requirements_path: Path,
    node_lock_path: Path,
) -> dict[str, Any]:
    site_packages = runtime / "site-packages"
    if not site_packages.is_dir():
        raise ValueError(f"missing runtime site-packages: {site_packages}")
    python_packages = _python_inventory(site_packages)
    installed = {item["canonical_name"] for item in python_packages}
    direct = _direct_requirements(requirements_path)
    missing_direct = sorted(set(direct) - installed)
    if missing_direct:
        raise ValueError(
            "desktop direct requirements missing from runtime: "
            + ", ".join(missing_direct)
        )

    node_packages = _node_inventory(node_lock_path)
    required_node = {
        "@whiskeysockets/baileys",
        "express",
        "pino",
        "qrcode-terminal",
    }
    locked_node = {item["name"] for item in node_packages}
    missing_node = sorted(required_node - locked_node)
    if missing_node:
        raise ValueError(
            "retained WhatsApp dependencies missing from package-lock: "
            + ", ".join(missing_node)
        )

    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "inputs": {
            "desktop_requirements": {
                "path": "python/requirements-desktop.txt",
                "sha256": _sha256(requirements_path),
                "direct_packages": direct,
            },
            "whatsapp_package_lock": {
                "path": "hermes_core/scripts/whatsapp-bridge/package-lock.json",
                "sha256": _sha256(node_lock_path),
            },
        },
        "python_packages": python_packages,
        "node_packages": node_packages,
    }


def main(argv: list[str]) -> int:
    if len(argv) != 4:
        print(
            "usage: generate_dependency_inventory.py "
            "<runtime-root> <requirements.txt> <whatsapp-package-lock.json>",
            file=sys.stderr,
        )
        return 2
    runtime, requirements_path, node_lock_path = map(
        lambda item: Path(item).resolve(),
        argv[1:],
    )
    try:
        inventory = generate(runtime, requirements_path, node_lock_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"dependency inventory failed: {exc}", file=sys.stderr)
        return 1
    output = runtime / "DEPENDENCY_INVENTORY.json"
    output.write_text(
        json.dumps(inventory, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        "dependency inventory ok: "
        f"python={len(inventory['python_packages'])} "
        f"node={len(inventory['node_packages'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
