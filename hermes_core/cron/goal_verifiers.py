"""Deterministic, workspace-confined verifiers for bounded goals."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Callable, Literal, Mapping

from cron.goal_state import GoalReport, JSONValue

__all__ = [
    "VerificationContext",
    "VerifierResult",
    "Verifier",
    "verify",
    "KNOWN_VERIFIER_KINDS",
    "RegistryVerifier",
]


@dataclass(frozen=True)
class VerificationContext:
    workdir: Path
    report: GoalReport
    config: Mapping[str, JSONValue]
    previous_evidence_hash: str | None


@dataclass(frozen=True)
class VerifierResult:
    outcome: Literal["pass", "fail", "error"]
    summary: str
    evidence: Mapping[str, JSONValue]


Verifier = Callable[[VerificationContext], VerifierResult]


class _VerifierConfigError(ValueError):
    pass


_SHA256_RE = re.compile(r"^[a-f0-9]{64}$")


def _workdir(context: VerificationContext) -> Path:
    workdir = context.workdir
    if not workdir.is_absolute():
        raise _VerifierConfigError("workdir must be absolute")
    root = workdir.resolve()
    if not root.exists() or not root.is_dir():
        raise _VerifierConfigError("workdir must exist and be a directory")
    return root


def _confined_path(root: Path, value: object) -> tuple[Path, str]:
    if not isinstance(value, str) or not value:
        raise _VerifierConfigError("artifact paths must be non-empty strings")
    candidate_text = Path(value)
    if candidate_text.is_absolute():
        raise _VerifierConfigError("artifact paths must be relative")
    if ".." in candidate_text.parts:
        raise _VerifierConfigError("artifact path must remain confined to workdir")
    resolved = (root / candidate_text).resolve()
    try:
        relative = resolved.relative_to(root)
    except ValueError as exc:
        raise _VerifierConfigError(
            "artifact path must remain confined to workdir"
        ) from exc
    return resolved, relative.as_posix()


def _string_list(config: Mapping[str, JSONValue], key: str) -> list[str]:
    raw = config.get(key)
    if not isinstance(raw, (list, tuple)) or not raw:
        raise _VerifierConfigError(f"{key} must be a non-empty list")
    if not all(isinstance(item, str) and item for item in raw):
        raise _VerifierConfigError(f"{key} entries must be non-empty strings")
    return list(raw)


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_hash(value: JSONValue) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _artifact_exists(context: VerificationContext) -> VerifierResult:
    root = _workdir(context)
    normalized: list[str] = []
    missing: list[str] = []
    for value in _string_list(context.config, "paths"):
        path, relative = _confined_path(root, value)
        normalized.append(relative)
        if not path.is_file():
            missing.append(relative)
    normalized.sort()
    missing.sort()
    if missing:
        return VerifierResult(
            "fail",
            "one or more required artifacts are missing or not regular files",
            {"paths": normalized, "missing_or_not_file": missing},
        )
    return VerifierResult(
        "pass",
        "all required artifacts exist",
        {"paths": normalized, "missing_or_not_file": []},
    )


def _normalized_manifest_path(value: object) -> str | None:
    if not isinstance(value, str) or not value or "\\" in value:
        return None
    pure = PurePosixPath(value)
    if pure.is_absolute() or ".." in pure.parts or "." in pure.parts:
        return None
    normalized = pure.as_posix()
    return normalized if normalized == value else None


def _manifest_complete(context: VerificationContext) -> VerifierResult:
    root = _workdir(context)
    manifest_value = context.config.get("manifest")
    manifest_path, manifest_relative = _confined_path(root, manifest_value)
    roots = _string_list(context.config, "roots")
    extensions = {item.lower() for item in _string_list(context.config, "extensions")}
    if any(not item.startswith(".") for item in extensions):
        raise _VerifierConfigError("extensions must include a leading dot")
    if not manifest_path.is_file():
        return VerifierResult(
            "fail",
            "manifest file is missing",
            {"manifest_complete": False, "missing_manifest": manifest_relative},
        )

    supported: dict[str, dict[str, JSONValue]] = {}
    for root_value in roots:
        search_root, _ = _confined_path(root, root_value)
        if not search_root.exists() or not search_root.is_dir():
            raise _VerifierConfigError("configured manifest root must be a directory")
        for candidate in search_root.rglob("*"):
            if candidate.suffix.lower() not in extensions:
                continue
            resolved = candidate.resolve()
            try:
                relative = resolved.relative_to(root).as_posix()
            except ValueError as exc:
                raise _VerifierConfigError(
                    "supported file must remain confined to workdir"
                ) from exc
            if resolved.is_file() and relative != manifest_relative:
                supported[relative] = {
                    "path": relative,
                    "sha256": _file_sha256(resolved),
                    "size_bytes": resolved.stat().st_size,
                }

    try:
        raw_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise _VerifierConfigError(f"manifest is not valid UTF-8 JSON: {exc}") from exc
    if not isinstance(raw_manifest, dict) or not isinstance(raw_manifest.get("files"), list):
        raise _VerifierConfigError("manifest must be an object containing a files list")

    records_by_path: dict[str, list[dict]] = {}
    invalid_records: list[int] = []
    for index, record in enumerate(raw_manifest["files"]):
        if not isinstance(record, dict):
            invalid_records.append(index)
            continue
        relative = _normalized_manifest_path(record.get("path"))
        sha256 = record.get("sha256")
        size_bytes = record.get("size_bytes")
        if (
            relative is None
            or not isinstance(sha256, str)
            or _SHA256_RE.fullmatch(sha256) is None
            or not isinstance(size_bytes, int)
            or isinstance(size_bytes, bool)
            or size_bytes < 0
        ):
            invalid_records.append(index)
            continue
        records_by_path.setdefault(relative, []).append(record)

    duplicate_records = sorted(
        path for path, records in records_by_path.items() if len(records) != 1
    )
    supported_paths = set(supported)
    recorded_paths = set(records_by_path)
    missing_records = sorted(supported_paths - recorded_paths)
    out_of_root_records = sorted(recorded_paths - supported_paths)
    mismatched_records: list[str] = []
    for relative in sorted(supported_paths & recorded_paths):
        records = records_by_path[relative]
        if len(records) == 1 and (
            records[0].get("sha256") != supported[relative]["sha256"]
            or records[0].get("size_bytes") != supported[relative]["size_bytes"]
        ):
            mismatched_records.append(relative)
    if mismatched_records:
        invalid_records.extend(
            raw_manifest["files"].index(records_by_path[path][0])
            for path in mismatched_records
        )
    invalid_records = sorted(set(invalid_records))

    paths = sorted(supported)
    evidence: dict[str, JSONValue] = {
        "manifest_complete": not any(
            (invalid_records, duplicate_records, missing_records, out_of_root_records)
        ),
        "paths": paths,
        "invalid_records": invalid_records,
        "duplicate_records": duplicate_records,
        "missing_records": missing_records,
        "out_of_root_records": out_of_root_records,
        "content_hash": _canonical_hash([supported[path] for path in paths]),
    }
    if evidence["manifest_complete"]:
        return VerifierResult("pass", "manifest covers every supported file", evidence)
    return VerifierResult("fail", "manifest is incomplete or invalid", evidence)


def _content_hash_changed(context: VerificationContext) -> VerifierResult:
    root = _workdir(context)
    artifacts: list[dict[str, JSONValue]] = []
    for value in context.report.artifacts:
        path, relative = _confined_path(root, value)
        if not path.is_file():
            return VerifierResult(
                "fail",
                "a reported artifact is missing or not a regular file",
                {"missing_or_not_file": relative},
            )
        artifacts.append({"path": relative, "sha256": _file_sha256(path)})
    artifacts.sort(key=lambda item: str(item["path"]))
    content_hash = _canonical_hash(artifacts)
    evidence: dict[str, JSONValue] = {
        "artifacts": artifacts,
        "content_hash": content_hash,
    }
    if content_hash == context.previous_evidence_hash:
        return VerifierResult("fail", "artifact content has not changed", evidence)
    return VerifierResult("pass", "artifact content changed", evidence)


_VERIFIERS: dict[str, Verifier] = {
    "artifact_exists": _artifact_exists,
    "manifest_complete": _manifest_complete,
    "content_hash_changed": _content_hash_changed,
}


# Public, read-only view of the registered deterministic verifier kinds, so
# job-creation validation can reject an unknown kind without importing the
# private registry.
KNOWN_VERIFIER_KINDS: frozenset[str] = frozenset(_VERIFIERS)


def verify(kind: str, context: VerificationContext) -> VerifierResult:
    """Run a known deterministic verifier; unknown kinds fail closed."""
    verifier = _VERIFIERS.get(kind)
    if verifier is None:
        return VerifierResult("error", f"unknown verifier kind: {kind}", {})
    try:
        return verifier(context)
    except _VerifierConfigError as exc:
        return VerifierResult("error", str(exc), {})
    except OSError as exc:
        return VerifierResult("error", f"verifier filesystem error: {exc}", {})


class RegistryVerifier:
    """Adapt the deterministic verifier registry to the ``GoalVerifier`` port.

    The controller calls ``verify(definition, report, previous_evidence_hash)``;
    this bridges that to the registry's ``verify(kind, context)`` without the
    controller having to know any concrete verifier.
    """

    def verify(
        self,
        definition: "GoalDefinition",  # noqa: F821 — structural, avoids an import cycle
        report: GoalReport,
        previous_evidence_hash: str | None,
    ) -> VerifierResult:
        return verify(
            definition.verifier_kind,
            VerificationContext(
                workdir=definition.workdir,
                report=report,
                config=definition.verifier_config,
                previous_evidence_hash=previous_evidence_hash,
            ),
        )

