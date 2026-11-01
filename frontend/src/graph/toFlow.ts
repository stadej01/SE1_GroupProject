// Pure functions: dialogue graph contract -> React Flow nodes/edges.
// No React or @xyflow imports, so everything here runs under `node --test`.
// The object shapes are structurally compatible with @xyflow/react's Node and Edge.

import type { DialogueGraph, GraphEdge, GraphNode } from "./contract";

export const NODE_W = 240;
export const NODE_H = 96;

/** Reserve enough space for every dialogue line, including wrapped text. */
export function nodeHeight(n: GraphNode): number {
  const lines = n.dialogue_lines?.length
    ? n.dialogue_lines.map((line) => `${line.speaker}: ${line.text}`)
    : [n.preview || "No dialogue lines"];
  const wrappedLines = lines.reduce((total, line) =>
    total + Math.max(1, ...line.split("\n").map((part) => Math.ceil(part.length / 34))), 0);
  return Math.max(NODE_H, 54 + wrappedLines * 19 + Math.max(0, lines.length - 1) * 5);
}
const GAP_X = 120;
const GAP_Y = 48;
export const LOOP_MARGIN = 28; // clearance below the lowest node a loop passes under
const LANE_STEP = 16;          // extra drop per stacked loop so loops don't overlap

// AC1: choices solid, jumps dotted.
export const EDGE_STYLE = {
  choice: { stroke: "#3d5a80", strokeWidth: 1.75 },
  jump: { stroke: "#8a5a00", strokeWidth: 1.75, strokeDasharray: "2 5", strokeLinecap: "round" },
} as const;

export interface Box { x: number; y: number; width: number; height: number }

export interface FlowNode {
  id: string;
  type: "dialogue";
  position: { x: number; y: number };
  data: GraphNode;
  style: { width: number; height: number };
}

export interface FlowEdge {
  id: string;
  source: string;
  target: string;
  sourceHandle: "out";
  targetHandle: "in";
  type: "default" | "loop";
  label?: string;
  labelStyle?: Record<string, string>;
  style: Record<string, string | number>;
  markerEnd: { type: "arrowclosed"; color: string };
  data: { kind: GraphEdge["kind"]; condition: string | null; backEdge: boolean; lane: number; rotateLabels: boolean };
}

/** Edges that point back to a node already on the DFS path from the start (includes self-loops). */
export function findBackEdges(graph: DialogueGraph): Set<string> {
  const out = new Map<string, GraphEdge[]>();
  for (const e of graph.edges) {
    if (!out.has(e.source)) out.set(e.source, []);
    out.get(e.source)!.push(e);
  }

  const back = new Set<string>();
  const state = new Map<string, "active" | "done">();
  const roots = [graph.start, ...graph.nodes.map((n) => n.id)].filter(Boolean) as string[];
  // Explicit stack avoids a JavaScript recursion overflow on long conversations.
  for (const id of roots) {
    if (state.has(id)) continue;
    state.set(id, "active");
    const stack = [{ id, next: 0 }];
    while (stack.length) {
      const frame = stack[stack.length - 1];
      const edges = out.get(frame.id) ?? [];
      if (frame.next === edges.length) {
        state.set(frame.id, "done");
        stack.pop();
        continue;
      }
      const edge = edges[frame.next++];
      const targetState = state.get(edge.target);
      if (targetState === "active") back.add(edge.id);
      else if (targetState === undefined) {
        state.set(edge.target, "active");
        stack.push({ id: edge.target, next: 0 });
      }
    }
  }
  return back;
}

/** Left-to-right layered layout: rank = longest forward path from a root. */
export function layout(graph: DialogueGraph, back: Set<string>): Map<string, Box> {
  const forward = graph.edges.filter((e) => !back.has(e.id));
  const outgoing = new Map<string, GraphEdge[]>();
  const indegree = new Map(graph.nodes.map((n) => [n.id, 0]));
  for (const e of forward) {
    indegree.set(e.target, (indegree.get(e.target) ?? 0) + 1);
    if (!outgoing.has(e.source)) outgoing.set(e.source, []);
    outgoing.get(e.source)!.push(e);
  }

  const rank = new Map(graph.nodes.map((n) => [n.id, 0]));
  const queue = graph.nodes.filter((n) => indegree.get(n.id) === 0).map((n) => n.id);
  for (let cursor = 0; cursor < queue.length; cursor++) {
    const id = queue[cursor];
    for (const e of outgoing.get(id) ?? []) {
      rank.set(e.target, Math.max(rank.get(e.target)!, rank.get(id)! + 1));
      indegree.set(e.target, indegree.get(e.target)! - 1);
      if (indegree.get(e.target) === 0) queue.push(e.target);
    }
  }

  const nextYInRank = new Map<number, number>();
  const boxes = new Map<string, Box>();
  for (const n of graph.nodes) {
    const r = rank.get(n.id)!;
    const y = nextYInRank.get(r) ?? 0;
    const height = nodeHeight(n);
    nextYInRank.set(r, y + height + GAP_Y);
    boxes.set(n.id, { x: r * (NODE_W + GAP_X), y, width: NODE_W, height });
  }
  return boxes;
}

/** Lowest y a loop between x1 and x2 must stay below so it doesn't cross any node in that span. */
export function loopClearance(boxes: Iterable<Box>, x1: number, x2: number, lane = 0): number {
  const [lo, hi] = x1 < x2 ? [x1, x2] : [x2, x1];
  let bottom = -Infinity;
  for (const b of boxes) {
    if (b.x <= hi && b.x + b.width >= lo) bottom = Math.max(bottom, b.y + b.height);
  }
  return bottom + LOOP_MARGIN + lane * LANE_STEP;
}

export const LOOP_GUTTER = GAP_X / 2 - 12; // how far into the column gap a loop travels
const RADIUS = 14;

/**
 * AC2: route a loop around the nodes instead of through them. It leaves the
 * source's right side, drops down the empty gap between columns, runs under
 * every node in the span (at clearY), and rises up the gap left of the target
 * into its left side. Corners are rounded so the edge reads as one curve.
 * `points` are the corners, used by tests to prove nothing is crossed.
 */
export function loopPath(sx: number, sy: number, tx: number, ty: number, clearY: number, lane = 0) {
  // Extra loops get vertical lanes; never shift a side gutter inside a node.
  const gutter = Math.max(RADIUS + 4, LOOP_GUTTER - lane * 12);
  const xr = sx + gutter;
  const xl = tx - gutter;
  const r = RADIUS;
  const path = [
    `M ${sx},${sy}`,
    `L ${xr - r},${sy} Q ${xr},${sy} ${xr},${sy + r}`,
    `L ${xr},${clearY - r} Q ${xr},${clearY} ${xr - r},${clearY}`,
    `L ${xl + r},${clearY} Q ${xl},${clearY} ${xl},${clearY - r}`,
    `L ${xl},${ty + r} Q ${xl},${ty} ${xl + r},${ty}`,
    `L ${tx},${ty}`,
  ].join(" ");
  const points = [[sx, sy], [xr, sy], [xr, clearY], [xl, clearY], [xl, ty], [tx, ty]] as const;
  return { path, points, labelX: (xr + xl) / 2, labelY: clearY };
}

function edgeLabel(e: GraphEdge): string | undefined {
  const cond = e.condition ? `[if ${e.condition}]` : "";
  if (e.kind === "jump") return cond ? `${cond} jump` : "jump";
  const text = e.label && e.label.length > 28 ? `${e.label.slice(0, 27)}…` : e.label ?? "";
  return [cond, text].filter(Boolean).join(" ");
}

export function toFlow(graph: DialogueGraph, saved: Map<string, { x: number; y: number }> = new Map(), vertical = false, rotateLabels = false) {
  const back = findBackEdges(graph);
  const auto = layout(graph, back);

  const nodes: FlowNode[] = graph.nodes.map((n) => ({
    id: n.id,
    type: "dialogue",
    // Saved NodePosition wins; auto-layout only fills gaps (design doc 3.2.3).
    position: saved.get(n.id) ?? (vertical ? { x: auto.get(n.id)!.y * 1.6, y: auto.get(n.id)!.x } : { x: auto.get(n.id)!.x, y: auto.get(n.id)!.y }),
    data: n,
    style: { width: NODE_W, height: nodeHeight(n) },
  }));

  let lane = 0;
  const edges: FlowEdge[] = graph.edges.map((e) => {
    const isBack = back.has(e.id);
    const style = EDGE_STYLE[e.kind];
    return {
      id: e.id,
      source: e.source,
      target: e.target,
      sourceHandle: "out",
      targetHandle: "in",
      type: isBack && !vertical ? "loop" : "default",
      label: edgeLabel(e),
      labelStyle: { transform: rotateLabels ? "rotate(-90deg)" : "none", transformBox: "fill-box", transformOrigin: "center" },
      style: { ...style },
      markerEnd: { type: "arrowclosed", color: style.stroke },
      data: { kind: e.kind, condition: e.condition, backEdge: isBack, lane: isBack ? lane++ : 0, rotateLabels },
    };
  });

  return { nodes, edges };
}
