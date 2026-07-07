"""Tiny DAG scheduler for the study team — Kahn topological layering.

Pure stdlib. Produces ordered *layers* of role ids so that every role appears
after all of its dependencies. Roles within the same layer have no ordering
constraint between them (the orchestrator may run them sequentially in M0, or
concurrently later).
"""

from __future__ import annotations

from typing import Dict, List, Mapping, Sequence


class DagError(ValueError):
    """Raised on an unknown dependency or a dependency cycle."""


def toposort_layers(
    nodes: Sequence[str],
    deps: Mapping[str, Sequence[str]],
    *,
    ignore_missing_deps: bool = True,
) -> List[List[str]]:
    """Return dependency-ordered layers for ``nodes``.

    ``deps[n]`` lists the ids that must run before ``n``. Dependencies that are
    not in ``nodes`` are dropped when ``ignore_missing_deps`` is True (lets a
    caller run a subset of the team without dragging in every upstream role);
    otherwise an unknown dependency raises :class:`DagError`.

    Raises :class:`DagError` on a cycle. Ordering within a layer and across
    layers is deterministic (sorted) so tests and the UI are stable.
    """
    node_list = list(nodes)
    node_set = set(node_list)
    if len(node_set) != len(node_list):
        raise DagError("duplicate node ids")

    remaining: Dict[str, set] = {}
    for n in node_list:
        raw = list(deps.get(n, ()))
        pruned = set()
        for d in raw:
            if d not in node_set:
                if ignore_missing_deps:
                    continue
                raise DagError(f"node '{n}' depends on unknown node '{d}'")
            pruned.add(d)
        remaining[n] = pruned

    layers: List[List[str]] = []
    resolved: set = set()
    while remaining:
        ready = sorted(n for n, d in remaining.items() if d <= resolved)
        if not ready:
            raise DagError(f"dependency cycle among: {sorted(remaining)}")
        layers.append(ready)
        for n in ready:
            del remaining[n]
        resolved.update(ready)
    return layers
