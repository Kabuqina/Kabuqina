// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Maximize2, Minus, Network, Plus, RefreshCw } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { AppScaffold } from "../components/AppScaffold";
import { BackButton } from "../components/ui/BackButton";
import { useI18n } from "../lib/i18n";
import {
  cmdStudyKnowledgeGraph,
  type KnowledgeGraphEdge,
  type KnowledgeGraphNode,
  type StudyKnowledgeGraphResponse,
} from "../chat/study/study-api";
import {
  collectGraphNeighborhood,
  GRAPH_VIEWBOX_HEIGHT,
  GRAPH_VIEWBOX_WIDTH,
  layoutKnowledgeNodes,
  type GraphPoint,
  type GraphTransform,
  zoomGraphAt,
} from "./knowledgeGraphLayout";

type Gesture =
  | { kind: "pan"; pointerId: number; start: GraphPoint; origin: GraphPoint; moved: boolean }
  | { kind: "node"; pointerId: number; nodeId: string; start: GraphPoint; origin: GraphPoint; scale: number; moved: boolean };

function moduleColor(module: string): string {
  let hash = 0;
  for (const character of module) hash = (hash * 31 + character.charCodeAt(0)) | 0;
  return `hsl(${Math.abs(hash) % 360} 62% 53%)`;
}

function pointFromPointer(svg: SVGSVGElement, clientX: number, clientY: number): GraphPoint {
  const matrix = svg.getScreenCTM();
  if (matrix) {
    const point = svg.createSVGPoint();
    point.x = clientX;
    point.y = clientY;
    const mapped = point.matrixTransform(matrix.inverse());
    return { x: mapped.x, y: mapped.y };
  }
  const rect = svg.getBoundingClientRect();
  return {
    x: ((clientX - rect.left) / Math.max(1, rect.width)) * GRAPH_VIEWBOX_WIDTH,
    y: ((clientY - rect.top) / Math.max(1, rect.height)) * GRAPH_VIEWBOX_HEIGHT,
  };
}

function KnowledgeGraphCanvas({
  nodes,
  edges,
  onOpenNode,
}: {
  nodes: KnowledgeGraphNode[];
  edges: KnowledgeGraphEdge[];
  onOpenNode: (node: KnowledgeGraphNode) => void;
}) {
  const svgRef = useRef<SVGSVGElement | null>(null);
  const gestureRef = useRef<Gesture | null>(null);
  const initialPositions = useMemo(() => layoutKnowledgeNodes(nodes), [nodes]);
  const [positions, setPositions] = useState<Record<string, GraphPoint>>(initialPositions);
  const [transform, setTransform] = useState<GraphTransform>({ x: 0, y: 0, scale: 1 });
  const [draggingNodeId, setDraggingNodeId] = useState<string | null>(null);
  const [settlingNodeId, setSettlingNodeId] = useState<string | null>(null);
  const [hoveredNodeId, setHoveredNodeId] = useState<string | null>(null);
  const [keyboardNodeId, setKeyboardNodeId] = useState<string | null>(null);
  const [isPanning, setIsPanning] = useState(false);
  const settleTimerRef = useRef<number | null>(null);
  const nodeById = useMemo(() => new Map(nodes.map((node) => [node.id, node])), [nodes]);
  const interactionNodeId = draggingNodeId || settlingNodeId || keyboardNodeId || hoveredNodeId;
  const interactionNeighborhood = useMemo(
    () => collectGraphNeighborhood(interactionNodeId, edges),
    [edges, interactionNodeId],
  );

  useEffect(() => setPositions(initialPositions), [initialPositions]);
  useEffect(() => () => {
    if (settleTimerRef.current !== null) window.clearTimeout(settleTimerRef.current);
  }, []);

  const finishNodeDrag = useCallback((nodeId: string) => {
    setDraggingNodeId(null);
    setSettlingNodeId(nodeId);
    if (settleTimerRef.current !== null) window.clearTimeout(settleTimerRef.current);
    settleTimerRef.current = window.setTimeout(() => {
      setSettlingNodeId((current) => current === nodeId ? null : current);
      settleTimerRef.current = null;
    }, 320);
  }, []);

  const resetView = useCallback(() => {
    setPositions(initialPositions);
    setTransform({ x: 0, y: 0, scale: 1 });
    setDraggingNodeId(null);
    setSettlingNodeId(null);
    setHoveredNodeId(null);
    setKeyboardNodeId(null);
    setIsPanning(false);
    if (settleTimerRef.current !== null) {
      window.clearTimeout(settleTimerRef.current);
      settleTimerRef.current = null;
    }
  }, [initialPositions]);

  const zoomAt = useCallback((factor: number, anchor = { x: GRAPH_VIEWBOX_WIDTH / 2, y: GRAPH_VIEWBOX_HEIGHT / 2 }) => {
    setTransform((current) => zoomGraphAt(current, factor, anchor));
  }, []);

  const beginPan = (event: React.PointerEvent<SVGSVGElement>) => {
    if (event.button !== 0 || event.target !== event.currentTarget) return;
    const start = pointFromPointer(event.currentTarget, event.clientX, event.clientY);
    gestureRef.current = {
      kind: "pan",
      pointerId: event.pointerId,
      start,
      origin: { x: transform.x, y: transform.y },
      moved: false,
    };
    setIsPanning(true);
    event.currentTarget.setPointerCapture(event.pointerId);
  };

  const beginNodeDrag = (event: React.PointerEvent<SVGGElement>, nodeId: string) => {
    if (event.button !== 0) return;
    event.preventDefault();
    event.stopPropagation();
    const svg = svgRef.current;
    if (!svg) return;
    const start = pointFromPointer(svg, event.clientX, event.clientY);
    gestureRef.current = {
      kind: "node",
      pointerId: event.pointerId,
      nodeId,
      start,
      origin: positions[nodeId] || { x: 0, y: 0 },
      scale: transform.scale,
      moved: false,
    };
    if (settleTimerRef.current !== null) {
      window.clearTimeout(settleTimerRef.current);
      settleTimerRef.current = null;
    }
    setHoveredNodeId(null);
    setSettlingNodeId(null);
    setDraggingNodeId(nodeId);
    svg.setPointerCapture(event.pointerId);
  };

  const moveGesture = (event: React.PointerEvent<SVGSVGElement>) => {
    const gesture = gestureRef.current;
    if (!gesture || gesture.pointerId !== event.pointerId) return;
    const point = pointFromPointer(event.currentTarget, event.clientX, event.clientY);
    const delta = { x: point.x - gesture.start.x, y: point.y - gesture.start.y };
    if (Math.abs(delta.x) + Math.abs(delta.y) > 4) gesture.moved = true;
    if (gesture.kind === "pan") {
      setTransform((current) => ({ ...current, x: gesture.origin.x + delta.x, y: gesture.origin.y + delta.y }));
    } else {
      setPositions((current) => ({
        ...current,
        [gesture.nodeId]: {
          x: gesture.origin.x + delta.x / gesture.scale,
          y: gesture.origin.y + delta.y / gesture.scale,
        },
      }));
    }
  };

  const endGesture = (event: React.PointerEvent<SVGSVGElement>) => {
    const gesture = gestureRef.current;
    if (!gesture || gesture.pointerId !== event.pointerId) return;
    gestureRef.current = null;
    setIsPanning(false);
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
    if (gesture.kind === "node") {
      finishNodeDrag(gesture.nodeId);
      if (!gesture.moved) {
        const node = nodeById.get(gesture.nodeId);
        if (node) onOpenNode(node);
      }
    }
  };

  const clearCapturedGesture = (event: React.PointerEvent<SVGSVGElement>) => {
    const gesture = gestureRef.current;
    if (!gesture || gesture.pointerId !== event.pointerId) return;
    gestureRef.current = null;
    setIsPanning(false);
    if (gesture.kind === "node") finishNodeDrag(gesture.nodeId);
  };

  const cancelGesture = (event: React.PointerEvent<SVGSVGElement>) => {
    const gesture = gestureRef.current;
    if (!gesture || gesture.pointerId !== event.pointerId) return;
    clearCapturedGesture(event);
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
  };

  return (
    <div className="relative min-h-0 flex-1 overflow-hidden rounded-2xl border border-[var(--kq-color-border)] bg-[var(--kq-glass-bg-subtle)] shadow-sm">
      <svg
        ref={svgRef}
        viewBox={`0 0 ${GRAPH_VIEWBOX_WIDTH} ${GRAPH_VIEWBOX_HEIGHT}`}
        className={`h-full min-h-[520px] w-full touch-none select-none ${isPanning ? "cursor-grabbing" : "cursor-grab"}`}
        role="application"
        aria-label="Knowledge graph"
        onPointerDown={beginPan}
        onPointerMove={moveGesture}
        onPointerUp={endGesture}
        onPointerCancel={cancelGesture}
        onLostPointerCapture={clearCapturedGesture}
        onWheel={(event) => {
          event.preventDefault();
          const svg = svgRef.current;
          if (!svg) return;
          zoomAt(event.deltaY < 0 ? 1.12 : 0.89, pointFromPointer(svg, event.clientX, event.clientY));
        }}
      >
        <defs>
          <pattern id="knowledge-grid" width="32" height="32" patternUnits="userSpaceOnUse">
            <circle cx="1" cy="1" r="1" fill="var(--kq-color-border)" opacity="0.55" />
          </pattern>
          <marker id="knowledge-arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
            <path d="M0,0 L8,4 L0,8 Z" fill="var(--kq-color-muted)" opacity="0.7" />
          </marker>
          <marker id="knowledge-arrow-focused" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
            <path d="M0,0 L8,4 L0,8 Z" fill="var(--kq-color-primary)" opacity="0.95" />
          </marker>
        </defs>
        <rect width="100%" height="100%" fill="url(#knowledge-grid)" pointerEvents="none" />
        <g transform={`translate(${transform.x} ${transform.y}) scale(${transform.scale})`}>
          <g pointerEvents="none" aria-hidden>
          {edges.map((edge) => {
            const source = positions[edge.source];
            const target = positions[edge.target];
            if (!source || !target) return null;
            const isFocused = interactionNodeId !== null
              && (edge.source === interactionNodeId || edge.target === interactionNodeId);
            const isDimmed = interactionNodeId !== null && !isFocused;
            return (
              <line
                key={edge.id}
                x1={source.x}
                y1={source.y}
                x2={target.x}
                y2={target.y}
                className="transition-[opacity,stroke,stroke-width] duration-200 motion-reduce:transition-none"
                stroke={isFocused ? "var(--kq-color-primary)" : "var(--kq-color-muted)"}
                strokeWidth={isFocused ? 2.5 : edge.kind === "prerequisite" ? 1.7 : 1.2}
                strokeDasharray={edge.kind === "related" ? "5 6" : undefined}
                opacity={isDimmed ? 0.09 : isFocused ? 0.92 : edge.kind === "prerequisite" ? 0.62 : 0.42}
                markerEnd={edge.kind === "prerequisite"
                  ? isFocused ? "url(#knowledge-arrow-focused)" : "url(#knowledge-arrow)"
                  : undefined}
              />
            );
          })}
          </g>
          {nodes.map((node) => {
            const point = positions[node.id];
            if (!point) return null;
            const color = moduleColor(node.module || "Other");
            const label = node.label.length > 20 ? `${node.label.slice(0, 19)}…` : node.label;
            const isDragging = draggingNodeId === node.id;
            const isSettling = settlingNodeId === node.id;
            const isPrimary = interactionNodeId === node.id;
            const isConnected = interactionNodeId === null || interactionNeighborhood.has(node.id);
            const nodeScale = isDragging ? 1.16 : isSettling ? 1.03 : isPrimary ? 1.07 : 1;
            return (
              <g
                key={node.id}
                transform={`translate(${point.x} ${point.y})`}
                className="cursor-grab active:cursor-grabbing focus-visible:[filter:drop-shadow(0_0_5px_#2563eb)]"
                role="button"
                tabIndex={0}
                aria-label={node.label}
                onPointerDown={(event) => beginNodeDrag(event, node.id)}
                onPointerEnter={() => {
                  if (!draggingNodeId) setHoveredNodeId(node.id);
                }}
                onPointerLeave={() => setHoveredNodeId((current) => current === node.id ? null : current)}
                onFocus={() => setKeyboardNodeId(node.id)}
                onBlur={() => setKeyboardNodeId((current) => current === node.id ? null : current)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    onOpenNode(node);
                  }
                }}
              >
                <title>{`${node.label}\n${node.summary}`}</title>
                <g
                  className="transition-[opacity,filter,transform] duration-300 motion-reduce:transition-none"
                  style={{
                    opacity: isConnected ? 1 : 0.24,
                    filter: isDragging
                      ? `drop-shadow(0 7px 9px color-mix(in srgb, ${color} 48%, transparent))`
                      : isPrimary
                        ? `drop-shadow(0 3px 5px color-mix(in srgb, ${color} 35%, transparent))`
                        : "none",
                    transform: `scale(${nodeScale})`,
                    transformOrigin: "0px 0px",
                    transitionTimingFunction: "cubic-bezier(0.2, 1.35, 0.35, 1)",
                  }}
                >
                  <circle
                    r="25"
                    fill={color}
                    opacity={isDragging ? 0.2 : isPrimary ? 0.11 : 0}
                    className={isDragging ? "animate-pulse motion-reduce:animate-none" : undefined}
                  />
                  <circle r="18" fill={color} opacity="0.16" />
                  <circle r="7" fill={color} stroke="white" strokeWidth="2" />
                  <text
                    x="13"
                    y="4"
                    fill="var(--kq-color-strong)"
                    fontSize="13"
                    fontWeight="600"
                    paintOrder="stroke"
                    stroke="var(--kq-color-surface,white)"
                    strokeWidth="4"
                    strokeLinejoin="round"
                  >
                    {label}
                  </text>
                </g>
              </g>
            );
          })}
        </g>
      </svg>
      <div className="absolute right-3 top-3 flex items-center gap-1 rounded-xl border border-[var(--kq-color-border)] bg-[var(--kq-glass-bg)] p-1 shadow-sm backdrop-blur">
        <button type="button" className="kq-soft-icon-btn rounded-lg p-2" onClick={() => zoomAt(1.2)} aria-label="Zoom in">
          <Plus className="h-4 w-4" />
        </button>
        <button type="button" className="kq-soft-icon-btn rounded-lg p-2" onClick={() => zoomAt(0.83)} aria-label="Zoom out">
          <Minus className="h-4 w-4" />
        </button>
        <button type="button" className="kq-soft-icon-btn rounded-lg p-2" onClick={resetView} aria-label="Reset graph view">
          <Maximize2 className="h-4 w-4" />
        </button>
      </div>
      <div className="pointer-events-none absolute bottom-3 left-3 rounded-xl border border-[var(--kq-color-border)] bg-[var(--kq-glass-bg)] px-3 py-2 text-xs text-[var(--kq-color-muted)] backdrop-blur">
        <span className="mr-3">→ prerequisite</span>
        <span>┄ related</span>
      </div>
    </div>
  );
}

export function KnowledgeGraphPage() {
  const { locale } = useI18n();
  const nav = useNavigate();
  const [graph, setGraph] = useState<StudyKnowledgeGraphResponse>({ nodes: [], edges: [], courses: [] });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const refresh = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setGraph(await cmdStudyKnowledgeGraph());
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => void refresh(), [refresh]);

  return (
    <AppScaffold surface="chat" className="flex h-full min-h-0 flex-col">
      <header className="hd-topbar flex h-12 shrink-0 items-center gap-3 border-b px-3">
        <BackButton onClick={() => nav("/chat")} className="-ml-1">
          {locale === "zh" ? "返回学习" : "Back to study"}
        </BackButton>
        <Network className="h-4 w-4 text-[var(--kq-color-primary-dark)]" />
        <div className="min-w-0 flex-1">
          <h1 className="truncate text-sm font-semibold text-[var(--kq-color-strong)]">
            {locale === "zh" ? "知识图谱" : "Knowledge graph"}
          </h1>
          <p className="truncate text-[11px] text-[var(--kq-color-muted)]">
            {graph.nodes.length} {locale === "zh" ? "个知识点" : "concepts"} · {graph.edges.length} {locale === "zh" ? "条关系" : "relations"}
          </p>
        </div>
        <button type="button" onClick={() => void refresh()} className="kq-soft-icon-btn rounded-lg p-2" aria-label="Refresh graph">
          <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
        </button>
      </header>
      <div className="flex min-h-0 flex-1 flex-col p-3 sm:p-5">
        {error ? (
          <div className="m-auto max-w-lg rounded-2xl border border-red-300/60 bg-red-50/80 p-5 text-sm text-red-700 dark:bg-red-500/10 dark:text-red-200">
            {error}
          </div>
        ) : loading ? (
          <div className="m-auto text-sm text-[var(--kq-color-muted)]">
            {locale === "zh" ? "正在构建知识图谱…" : "Building knowledge graph…"}
          </div>
        ) : graph.nodes.length === 0 ? (
          <div className="m-auto max-w-lg rounded-3xl border border-[var(--kq-color-border)] bg-[var(--kq-glass-bg-subtle)] p-8 text-center shadow-sm">
            <Network className="mx-auto h-10 w-10 text-[var(--kq-color-primary)]" />
            <h2 className="mt-4 text-lg font-semibold text-[var(--kq-color-strong)]">
              {locale === "zh" ? "还没有已激活的课程知识库" : "No active course knowledge base yet"}
            </h2>
            <p className="mt-2 text-sm leading-6 text-[var(--kq-color-muted)]">
              {locale === "zh"
                ? "回到 STUDY 生成完整课程知识库并审核激活后，知识点及其前置、关联关系会自动显示在这里。"
                : "Generate and activate a complete course knowledge base in STUDY; concepts and their prerequisite and related links will appear here."}
            </p>
            <button type="button" onClick={() => nav("/chat")} className="kq-btn-primary mt-5 rounded-xl px-4 py-2 text-sm">
              {locale === "zh" ? "前往 STUDY" : "Open STUDY"}
            </button>
          </div>
        ) : (
          <KnowledgeGraphCanvas
            nodes={graph.nodes}
            edges={graph.edges}
            onOpenNode={(node) => nav(`/study/knowledge/${encodeURIComponent(node.artifact_id)}/${node.concept_index}`)}
          />
        )}
      </div>
    </AppScaffold>
  );
}
