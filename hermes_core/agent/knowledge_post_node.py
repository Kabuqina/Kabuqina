# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Bounded zero-call knowledge-point post-node for L-4.

The extractor consumes only visible assistant prose after removing legacy
``kq-kp`` fenced blocks. It recognizes deliberately explicit Markdown
definitions and headings; ordinary prose degrades to no candidates. Candidates
remain review/capture inputs and this module performs no storage or provider
operation.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
import unicodedata
from typing import Any, Mapping


KNOWLEDGE_POST_POLICY_VERSION = "kq-kp-post-v2"
MAX_POST_INPUT_CODEPOINTS = 24_000
MAX_KNOWLEDGE_CANDIDATES = 5
MAX_KNOWLEDGE_NAME = 80
MAX_KNOWLEDGE_GIST = 300
MAX_KNOWLEDGE_SOURCE = 120

_COMPLETE_LEGACY_BLOCK_RE = re.compile(
    r"^```kq-kp[ \t]*\r?\n[\s\S]*?^```[ \t]*(?:\r?\n|$)",
    re.IGNORECASE | re.MULTILINE,
)
_UNTERMINATED_LEGACY_BLOCK_RE = re.compile(
    r"^```kq-kp[ \t]*\r?\n[\s\S]*\Z",
    re.IGNORECASE | re.MULTILINE,
)
_CODE_FENCE_RE = re.compile(r"^\s*```")
_BOLD_DEFINITION_RE = re.compile(
    r"^(?:[-*+]\s+)?\*\*([^*\r\n]{1,100})\*\*\s*(?::|：|—|–|-)\s*(.{1,500})$"
)
_HEADING_RE = re.compile(r"^#{2,4}\s+(.{1,100})\s*$")


class KnowledgePostContractError(ValueError):
    """A v2 knowledge-point post-node value violated its exact contract."""


def _strip_controls(value: str) -> str:
    return "".join(
        char
        for char in value
        if char in "\t\n\r" or not unicodedata.category(char).startswith("C")
    )


def _clean(value: Any, maximum: int) -> str:
    if not isinstance(value, str):
        return ""
    normalized = unicodedata.normalize("NFC", _strip_controls(value))
    return " ".join(normalized.split()).strip()[:maximum]


def strip_legacy_kq_kp_blocks(text: str) -> tuple[str, bool]:
    """Remove complete and final unterminated legacy metadata blocks."""
    if not isinstance(text, str):
        raise KnowledgePostContractError("assistant text must be a string")
    found = bool(
        _COMPLETE_LEGACY_BLOCK_RE.search(text)
        or _UNTERMINATED_LEGACY_BLOCK_RE.search(text)
    )
    visible = _COMPLETE_LEGACY_BLOCK_RE.sub("", text)
    visible = _UNTERMINATED_LEGACY_BLOCK_RE.sub("", visible)
    return re.sub(r"\n{3,}", "\n\n", visible).strip(), found


@dataclass(frozen=True)
class KnowledgePointCandidateV2:
    name: str
    gist: str
    source: str = "model"
    confidence: str = "inferred"
    schema_version: int = 2

    def __post_init__(self) -> None:
        if self.schema_version != 2:
            raise KnowledgePostContractError("knowledge candidate version is invalid")
        object.__setattr__(self, "name", _clean(self.name, MAX_KNOWLEDGE_NAME))
        object.__setattr__(self, "gist", _clean(self.gist, MAX_KNOWLEDGE_GIST))
        object.__setattr__(self, "source", _clean(self.source, MAX_KNOWLEDGE_SOURCE))
        if not self.name or not self.gist or not self.source:
            raise KnowledgePostContractError("knowledge candidate text is invalid")
        if self.confidence not in {"confirmed", "inferred"}:
            raise KnowledgePostContractError("knowledge candidate confidence is invalid")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 2,
            "name": self.name,
            "gist": self.gist,
            "source": self.source,
            "confidence": self.confidence,
        }

    @classmethod
    def from_mapping(cls, value: Any) -> "KnowledgePointCandidateV2":
        if not isinstance(value, Mapping) or set(value) != {
            "schema_version",
            "name",
            "gist",
            "source",
            "confidence",
        }:
            raise KnowledgePostContractError("knowledge candidate fields are invalid")
        return cls(
            schema_version=value.get("schema_version"),
            name=value.get("name"),
            gist=value.get("gist"),
            source=value.get("source"),
            confidence=value.get("confidence"),
        )


@dataclass(frozen=True)
class KnowledgePostResultV2:
    visible_text: str
    candidates: tuple[KnowledgePointCandidateV2, ...]
    legacy_block_removed: bool
    analysis_truncated: bool
    visible_sha256: str
    policy_version: str = KNOWLEDGE_POST_POLICY_VERSION
    schema_version: int = 2

    def __post_init__(self) -> None:
        if self.schema_version != 2 or self.policy_version != KNOWLEDGE_POST_POLICY_VERSION:
            raise KnowledgePostContractError("knowledge post result version is invalid")
        if not isinstance(self.visible_text, str):
            raise KnowledgePostContractError("knowledge post visible_text is invalid")
        if (
            not isinstance(self.candidates, tuple)
            or len(self.candidates) > MAX_KNOWLEDGE_CANDIDATES
            or not all(isinstance(item, KnowledgePointCandidateV2) for item in self.candidates)
        ):
            raise KnowledgePostContractError("knowledge post candidates are invalid")
        if type(self.legacy_block_removed) is not bool or type(self.analysis_truncated) is not bool:
            raise KnowledgePostContractError("knowledge post flags are invalid")
        expected = hashlib.sha256(self.visible_text.encode("utf-8")).hexdigest()
        if self.visible_sha256 != expected:
            raise KnowledgePostContractError("knowledge post visible hash is invalid")

    def metadata_dict(self) -> dict[str, Any]:
        """Return bounded metadata; visible prose remains in the normal message."""
        return {
            "schema_version": 2,
            "policy_version": self.policy_version,
            "candidates": [item.to_dict() for item in self.candidates],
            "legacy_block_removed": self.legacy_block_removed,
            "analysis_truncated": self.analysis_truncated,
            "visible_sha256": self.visible_sha256,
        }


def _candidate(name: str, gist: str) -> KnowledgePointCandidateV2 | None:
    clean_name = _clean(name, MAX_KNOWLEDGE_NAME)
    clean_gist = _clean(gist, MAX_KNOWLEDGE_GIST)
    if not 2 <= len(clean_name) <= MAX_KNOWLEDGE_NAME or len(clean_gist) < 8:
        return None
    try:
        return KnowledgePointCandidateV2(name=clean_name, gist=clean_gist)
    except KnowledgePostContractError:
        return None


def _extract_visible_definitions(text: str) -> tuple[KnowledgePointCandidateV2, ...]:
    lines: list[str] = []
    inside_fence = False
    for line in text.splitlines():
        if _CODE_FENCE_RE.match(line):
            inside_fence = not inside_fence
            continue
        if not inside_fence:
            lines.append(line)
    candidates: list[KnowledgePointCandidateV2] = []
    seen: set[str] = set()

    def append(candidate: KnowledgePointCandidateV2 | None) -> None:
        if candidate is None:
            return
        key = candidate.name.casefold()
        if key in seen or len(candidates) >= MAX_KNOWLEDGE_CANDIDATES:
            return
        seen.add(key)
        candidates.append(candidate)

    for index, line in enumerate(lines):
        bold = _BOLD_DEFINITION_RE.match(line.strip())
        if bold:
            append(_candidate(bold.group(1), bold.group(2)))
            continue
        heading = _HEADING_RE.match(line.strip())
        if not heading:
            continue
        gist = ""
        for following in lines[index + 1 : index + 4]:
            stripped = following.strip()
            if not stripped:
                continue
            if stripped.startswith(("#", "```")):
                break
            gist = stripped
            break
        append(_candidate(heading.group(1), gist))
    return tuple(candidates)


def run_knowledge_post_node(assistant_text: str) -> KnowledgePostResultV2:
    """Run the zero-call v2 post-node over bounded visible prose."""
    visible, legacy_removed = strip_legacy_kq_kp_blocks(assistant_text)
    analysis_truncated = len(visible) > MAX_POST_INPUT_CODEPOINTS
    analysis = visible[:MAX_POST_INPUT_CODEPOINTS]
    result = KnowledgePostResultV2(
        visible_text=visible,
        candidates=_extract_visible_definitions(analysis),
        legacy_block_removed=legacy_removed,
        analysis_truncated=analysis_truncated,
        visible_sha256=hashlib.sha256(visible.encode("utf-8")).hexdigest(),
    )
    metadata = json.dumps(
        result.metadata_dict(),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    if len(metadata) > 8 * 1024:
        raise KnowledgePostContractError("knowledge post metadata exceeds 8 KiB")
    return result


__all__ = [
    "KNOWLEDGE_POST_POLICY_VERSION",
    "KnowledgePostContractError",
    "KnowledgePointCandidateV2",
    "KnowledgePostResultV2",
    "run_knowledge_post_node",
    "strip_legacy_kq_kp_blocks",
]
