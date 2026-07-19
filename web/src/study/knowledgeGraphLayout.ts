// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

export type GraphLayoutNode = { id: string; module?: string };
export type GraphPoint = { x: number; y: number };
export type GraphTransform = GraphPoint & { scale: number };

export const GRAPH_VIEWBOX_WIDTH = 1200;
export const GRAPH_VIEWBOX_HEIGHT = 760;

export function clampGraphScale(value: number): number {
  return Math.max(0.35, Math.min(2.8, value));
}

export function zoomGraphAt(
  current: GraphTransform,
  factor: number,
  anchor: GraphPoint,
): GraphTransform {
  const scale = clampGraphScale(current.scale * factor);
  const worldX = (anchor.x - current.x) / current.scale;
  const worldY = (anchor.y - current.y) / current.scale;
  return {
    scale,
    x: anchor.x - worldX * scale,
    y: anchor.y - worldY * scale,
  };
}

function keepNodeVisible(point: GraphPoint): GraphPoint {
  return {
    // Reserve extra room on the right for the node label.
    x: Math.max(55, Math.min(GRAPH_VIEWBOX_WIDTH - 190, point.x)),
    y: Math.max(45, Math.min(GRAPH_VIEWBOX_HEIGHT - 45, point.y)),
  };
}

/** Deterministic module-clustered layout; node drag state can override it. */
export function layoutKnowledgeNodes(nodes: GraphLayoutNode[]): Record<string, GraphPoint> {
  const modules = new Map<string, GraphLayoutNode[]>();
  for (const node of nodes) {
    const key = node.module?.trim() || "Other";
    const rows = modules.get(key) || [];
    rows.push(node);
    modules.set(key, rows);
  }
  const groups = [...modules.entries()].sort(([left], [right]) => left.localeCompare(right));
  const center = { x: GRAPH_VIEWBOX_WIDTH / 2, y: GRAPH_VIEWBOX_HEIGHT / 2 };
  const groupRadius = groups.length <= 1 ? 0 : Math.min(270, 95 + groups.length * 24);
  const result: Record<string, GraphPoint> = {};
  groups.forEach(([, rows], groupIndex) => {
    const angle = -Math.PI / 2 + (groupIndex * Math.PI * 2) / Math.max(1, groups.length);
    const groupCenter = {
      x: center.x + Math.cos(angle) * groupRadius,
      y: center.y + Math.sin(angle) * groupRadius,
    };
    const sorted = [...rows].sort((left, right) => left.id.localeCompare(right.id));
    const localRadius = Math.min(145, Math.max(42, sorted.length * 11));
    sorted.forEach((node, nodeIndex) => {
      const nodeAngle = -Math.PI / 2 + (nodeIndex * Math.PI * 2) / Math.max(1, sorted.length);
      result[node.id] = keepNodeVisible(sorted.length === 1
        ? groupCenter
        : {
            x: groupCenter.x + Math.cos(nodeAngle) * localRadius,
            y: groupCenter.y + Math.sin(nodeAngle) * localRadius,
          });
    });
  });
  return result;
}
