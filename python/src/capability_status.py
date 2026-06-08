# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Runtime status computation for first-party product capabilities."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Iterable


def _unique(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        value = str(item or "")
        if value and value not in seen:
            seen.add(value)
            out.append(value)
    return out


def _camel_package(package: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(package.get("id") or ""),
        "title": str(package.get("title") or package.get("id") or ""),
        "description": str(package.get("description") or ""),
        "feature": str(package.get("feature") or ""),
        "modelId": str(package.get("modelId") or package.get("model_id") or ""),
        "sizeMb": int(package.get("sizeMb") or package.get("size_mb") or 0),
        "downloaded": bool(package.get("downloaded")),
        "size": int(package.get("size") or 0),
        "path": str(package.get("path") or ""),
        "sources": deepcopy(package.get("sources") or []),
        "job": deepcopy(package.get("job")),
    }


def _resolve_packages(
    package_ids: Iterable[str],
    packages_by_id: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    resolved = []
    for package_id in package_ids:
        package = packages_by_id.get(package_id)
        if package is None:
            package = {"id": package_id, "title": package_id, "downloaded": False}
        resolved.append(_camel_package(package))
    return resolved


def _status_for_required_packages(packages: list[dict[str, Any]]) -> tuple[str, str]:
    for package in packages:
        job = package.get("job")
        if isinstance(job, dict):
            if job.get("status") == "running":
                return "downloading", f"{package['id']} is downloading"
            if job.get("status") == "error":
                return "package_error", str(job.get("error") or f"{package['id']} download failed")
    for package in packages:
        if not package.get("downloaded"):
            return "missing_package", f"{package['id']} is not installed"
    return "available", ""


def _status_for_required_toolsets(
    definition: dict[str, Any],
    enabled_toolsets: Iterable[str] | None,
) -> tuple[str, str]:
    if enabled_toolsets is None:
        return "available", ""

    enabled = {str(item) for item in enabled_toolsets}
    missing = [
        str(toolset)
        for toolset in definition.get("required_toolsets") or []
        if str(toolset) not in enabled
    ]
    if missing:
        return "disabled_toolset", f"Required toolset disabled: {', '.join(missing)}"
    return "available", ""


def _pipeline_package_ids(pipeline: dict[str, Any], key: str) -> list[str]:
    package_ids: list[str] = [str(item) for item in pipeline.get(key) or []]
    for step in pipeline.get("steps") or []:
        package_ids.extend(str(item) for item in step.get(key) or [])
    return _unique(package_ids)


def _camel_shortcut(shortcut: dict[str, Any]) -> dict[str, Any]:
    item = deepcopy(shortcut)
    if "entry_pipeline" in item:
        item["entryPipeline"] = item["entry_pipeline"]
    if "requires_input" in item:
        item["requiresInput"] = item["requires_input"]
    if "visible_when" in item:
        item["visibleWhen"] = item["visible_when"]
    return item


def _is_candidate(definition: dict[str, Any]) -> bool:
    return str(definition.get("lifecycle") or "").strip().lower() == "candidate"


def _evaluate_pipeline(
    pipeline: dict[str, Any],
    packages_by_id: dict[str, dict[str, Any]],
    definition: dict[str, Any],
    enabled_toolsets: Iterable[str] | None,
) -> dict[str, Any]:
    required = _resolve_packages(_pipeline_package_ids(pipeline, "required_load_packages"), packages_by_id)
    optional = _resolve_packages(_pipeline_package_ids(pipeline, "optional_load_packages"), packages_by_id)

    if _is_candidate(definition):
        status = "candidate"
        reason = "Candidate capability; executable pipeline is not implemented yet"
    else:
        status, reason = _status_for_required_packages(required)
        if status == "available":
            status, reason = _status_for_required_toolsets(definition, enabled_toolsets)

    evaluated = deepcopy(pipeline)
    evaluated["ready"] = status == "available"
    evaluated["status"] = status
    evaluated["statusReason"] = reason
    evaluated["requiredLoadPackages"] = required
    evaluated["optionalLoadPackages"] = optional
    return evaluated


def build_capability_status(
    definition: dict[str, Any],
    packages_by_id: dict[str, dict[str, Any]] | None = None,
    *,
    load_packages: dict[str, dict[str, Any]] | None = None,
    enabled_toolsets: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Build the web-facing product capability payload for one definition."""

    package_lookup = load_packages if load_packages is not None else packages_by_id
    package_lookup = package_lookup or {}

    required = _resolve_packages(
        (str(item) for item in definition.get("required_load_packages") or []),
        package_lookup,
    )
    optional = _resolve_packages(
        (str(item) for item in definition.get("optional_load_packages") or []),
        package_lookup,
    )
    pipelines = [
        _evaluate_pipeline(pipeline, package_lookup, definition, enabled_toolsets)
        for pipeline in definition.get("pipelines") or []
    ]

    if _is_candidate(definition):
        status = "candidate"
        reason = "Candidate capability; executable pipeline is not implemented yet"
    else:
        status, reason = _status_for_required_packages(required)
        if status == "available":
            status, reason = _status_for_required_toolsets(definition, enabled_toolsets)

    return {
        "id": definition["id"],
        "title": definition["title"],
        "description": definition["description"],
        "category": definition["category"],
        "status": status,
        "statusReason": reason,
        "agentHint": definition["agent_hint"],
        "family": str(definition.get("family") or ""),
        "lifecycle": str(definition.get("lifecycle") or "available"),
        "stages": list(definition.get("stages") or []),
        "tools": list(definition.get("tools") or []),
        "requiredToolsets": list(definition.get("required_toolsets") or []),
        "requiredLoadPackages": required,
        "optionalLoadPackages": optional,
        "pipelines": pipelines,
        "shortcuts": [_camel_shortcut(item) for item in definition.get("shortcuts") or []],
        "structureTemplates": deepcopy(definition.get("structure_templates") or []),
        "visualMasters": deepcopy(definition.get("visual_masters") or []),
        "roles": list(definition.get("roles") or []),
        "risk": definition.get("risk", "low"),
        "source": definition.get("source", "builtin"),
        "trust": definition.get("trust", "official"),
    }


def build_all_capability_statuses(
    definitions: list[dict[str, Any]],
    packages: list[dict[str, Any]],
    *,
    enabled_toolsets: Iterable[str] | None = None,
) -> list[dict[str, Any]]:
    packages_by_id = {str(item.get("id")): item for item in packages}
    return [
        build_capability_status(
            definition,
            packages_by_id,
            enabled_toolsets=enabled_toolsets,
        )
        for definition in definitions
    ]
