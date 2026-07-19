"""Deterministic graph projection for active STUDY knowledge bases."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from learning.learning_context import LearningExecutionContext

MAX_GRAPH_NODES = 800
MAX_GRAPH_EDGES = 4_000
MAX_TEXT = 20_000


def _text(value: Any, limit: int = MAX_TEXT) -> str:
    return value.strip()[:limit] if isinstance(value, str) else ""


def _strings(value: Any, limit: int = 80) -> List[str]:
    if not isinstance(value, list):
        return []
    out: List[str] = []
    seen: set[str] = set()
    for raw in value:
        item = _text(raw, 300)
        key = item.casefold()
        if not item or key in seen:
            continue
        seen.add(key)
        out.append(item)
        if len(out) >= limit:
            break
    return out


class KnowledgeGraphService:
    """Read-only owner/space-scoped knowledge graph and concept details."""

    def __init__(self, context: LearningExecutionContext):
        self._ctx = context

    def build(self) -> Dict[str, Any]:
        artifacts = self._active_bases()
        nodes: List[Dict[str, Any]] = []
        concept_rows: List[tuple[Dict[str, Any], Dict[str, Any], int]] = []
        local_terms: Dict[str, Dict[str, str]] = {}
        global_terms: Dict[str, str] = {}
        courses: List[str] = []

        for artifact in artifacts:
            payload = artifact.get("envelope", {}).get("payload", {})
            if not isinstance(payload, dict):
                continue
            course = _text(payload.get("course"), 300) or _text(
                artifact.get("title"), 300
            )
            if course and course.casefold() not in {item.casefold() for item in courses}:
                courses.append(course)
            concepts = payload.get("concepts")
            if not isinstance(concepts, list):
                continue
            artifact_id = str(artifact.get("artifact_id") or "")
            local_terms[artifact_id] = {}
            for concept_index, raw in enumerate(concepts):
                if len(nodes) >= MAX_GRAPH_NODES or not isinstance(raw, dict):
                    break
                term = _text(raw.get("term"), 300)
                explanation = _text(raw.get("explanation"))
                if not term or not explanation:
                    continue
                node_id = f"{artifact_id}:{concept_index}"
                module = _text(raw.get("module"), 300) or course
                node = {
                    "id": node_id,
                    "artifact_id": artifact_id,
                    "concept_index": concept_index,
                    "label": term,
                    "module": module,
                    "summary": explanation[:360],
                }
                nodes.append(node)
                concept_rows.append((artifact, raw, concept_index))
                key = term.casefold()
                local_terms[artifact_id].setdefault(key, node_id)
                global_terms.setdefault(key, node_id)

        edges: List[Dict[str, str]] = []
        seen_edges: set[tuple[str, str, str]] = set()
        for artifact, concept, concept_index in concept_rows:
            artifact_id = str(artifact.get("artifact_id") or "")
            target = f"{artifact_id}:{concept_index}"

            def resolve(term: str) -> Optional[str]:
                key = term.casefold()
                return local_terms.get(artifact_id, {}).get(key) or global_terms.get(key)

            for term in _strings(concept.get("prerequisites")):
                source = resolve(term)
                if not source or source == target:
                    continue
                key = (source, target, "prerequisite")
                if key in seen_edges:
                    continue
                seen_edges.add(key)
                edges.append(
                    {
                        "id": f"prerequisite:{source}>{target}",
                        "source": source,
                        "target": target,
                        "kind": "prerequisite",
                    }
                )
                if len(edges) >= MAX_GRAPH_EDGES:
                    break
            if len(edges) >= MAX_GRAPH_EDGES:
                break
            for term in _strings(concept.get("related")):
                related = resolve(term)
                if not related or related == target:
                    continue
                source, destination = sorted((target, related))
                key = (source, destination, "related")
                if key in seen_edges:
                    continue
                seen_edges.add(key)
                edges.append(
                    {
                        "id": f"related:{source}<>{destination}",
                        "source": source,
                        "target": destination,
                        "kind": "related",
                    }
                )
                if len(edges) >= MAX_GRAPH_EDGES:
                    break

        return {"nodes": nodes, "edges": edges, "courses": courses}

    def get_concept(self, artifact_id: str, concept_index: int) -> Dict[str, Any]:
        if concept_index < 0:
            raise KeyError("concept not found")
        artifact = next(
            (
                row
                for row in self._active_bases()
                if row.get("artifact_id") == artifact_id
            ),
            None,
        )
        if not artifact:
            raise KeyError(f"active knowledge base {artifact_id!r} not found")
        payload = artifact.get("envelope", {}).get("payload", {})
        concepts = payload.get("concepts") if isinstance(payload, dict) else None
        if not isinstance(concepts, list) or concept_index >= len(concepts):
            raise KeyError("concept not found")
        concept = concepts[concept_index]
        if not isinstance(concept, dict):
            raise KeyError("concept not found")
        term = _text(concept.get("term"), 300)
        explanation = _text(concept.get("explanation"))
        if not term or not explanation:
            raise KeyError("concept not found")
        return {
            "artifact_id": artifact_id,
            "concept_index": concept_index,
            "knowledge_base_title": _text(artifact.get("title"), 300),
            "course": _text(payload.get("course"), 300),
            "specialty": _text(payload.get("specialty"), 300),
            "term": term,
            "module": _text(concept.get("module"), 300),
            "explanation": explanation,
            "content_markdown": _text(concept.get("content_markdown")) or explanation,
            "source_section": _text(concept.get("source_section"), 500),
            "source_locator": _text(concept.get("source_locator"), 1_000),
            "review_prompt": _text(concept.get("review_prompt"), 2_000),
            "prerequisites": _strings(concept.get("prerequisites")),
            "related": _strings(concept.get("related")),
        }

    def _active_bases(self) -> List[Dict[str, Any]]:
        return sorted(
            self._ctx.list_artifacts(kind="knowledge_base", status="active"),
            key=lambda row: (row.get("updated_at", ""), row.get("artifact_id", "")),
        )
