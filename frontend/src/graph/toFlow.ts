/**
 * Converts the dialogue graph contract into the nodes and edges that React Flow draws.
 *
 * Every function here is pure and imports neither React nor @xyflow/react, so
 * the logic runs under `node --test` without a browser. The returned objects
 * match the structure of React Flow's Node and Edge types, so DialogueGraph.tsx
 * can pass them straight to <ReactFlow>.
 * 
 *  - Edge styling: player choices are solid line. Jumps are solid when they are at the 
 *    end of their node or are the node's only way out. Other jumps are dotted.
 *  - Loop detection: a depth-first search from the start node marks edges that
 *    point back to a node already on the current path, including self-loops.
 *  - Layout: a left-to-right layered layout.
 *  - Loop routing: loop edges travel through the gaps between columns
 *    and under every node in their span, so they never cover the nodes in
 *    between (see loopClearance, loopPath).
 */

import type { DialogueGraph, GraphEdge, GraphNode } from "./contract";

export const NODE_W = 240;
export const NODE_H = 96;

// Reserve enough space for every dialogue line, including wrapped text.
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
export const LOOP_MARGIN = 28; 
const LANE_STEP = 16;          

// choices solid; jumps dotted only when they transit through a node mid-dialogue.
export const EDGE_STYLE = {
  choice: { stroke: "#3d5a80", strokeWidth: 1.75 },
  jump: { stroke: "#8a5a00", strokeWidth: 1.75 },
  midJump: { stroke: "#8a5a00", strokeWidth: 1.75, strokeDasharray: "2 5", strokeLinecap: "round" },
} as const;

/**
 * A jump is drawn solid when it ends its node, or when it's the node's only way out.
 * A jump in the middle of a node, with more dialogue or choices after it, stays dotted.
 */
export function edgeStyle(edge: GraphEdge, outgoingCount: number) {
  if (edge.kind === "choice") return EDGE_STYLE.choice;
  return edge.ends_node || outgoingCount === 1 ? EDGE_STYLE.jump : EDGE_STYLE.midJump;
}

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

// Edges that point back to a node already on the DFS path from the start (includes self-loops).
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
  const forward = graph.edges.filter((edge) => !back.has(edge.id));
  const outgoing = new Map<string, GraphEdge[]>();
  const indegree = new Map(graph.nodes.map((n) => [n.id, 0]));
  for (const edge of forward) {
    indegree.set(edge.target, (indegree.get(edge.target) ?? 0) + 1);
    if (!outgoing.has(edge.source)) outgoing.set(edge.source, []);
    outgoing.get(edge.source)!.push(edge);
  }

  const rank = new Map(graph.nodes.map((node) => [node.id, 0]));
  const queue = graph.nodes.filter((node) => indegree.get(node.id) === 0).map((node) => node.id);
  for (let cursor = 0; cursor < queue.length; cursor++) {
    const id = queue[cursor];
    for (const edge of outgoing.get(id) ?? []) {
      rank.set(edge.target, Math.max(rank.get(edge.target)!, rank.get(id)! + 1));
      indegree.set(edge.target, indegree.get(edge.target)! - 1);
      if (indegree.get(edge.target) === 0) queue.push(edge.target);
    }
  }

  const nextYInRank = new Map<number, number>();
  const boxes = new Map<string, Box>();
  for (const node of graph.nodes) {
    const r = rank.get(node.id)!;
    const y = nextYInRank.get(r) ?? 0;
    const height = nodeHeight(node);
    nextYInRank.set(r, y + height + GAP_Y);
    boxes.set(node.id, { x: r * (NODE_W + GAP_X), y, width: NODE_W, height });
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
 * When creating loop: It leaves the source's right side, drops down the empty gap 
 * between columns, runs under every node in the span, and rises up the gap left of the target
 * into its left side.
 */
export function loopPath(sx: number, sy: number, tx: number, ty: number, clearY: number, lane = 0) {
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

function edgeLabel(edge: GraphEdge): string | undefined {
  const cond = edge.condition ? `[if ${edge.condition}]` : "";
  if (edge.kind === "jump") return cond ? `${cond} jump` : "jump";
  const text = edge.label && edge.label.length > 28 ? `${edge.label.slice(0, 27)}…` : edge.label ?? "";
  return [cond, text].filter(Boolean).join(" ");
}

export function toFlow(graph: DialogueGraph, saved: Map<string, { x: number; y: number }> = new Map(), vertical = false, rotateLabels = false) {
  const back = findBackEdges(graph);
  const auto = layout(graph, back);

  const nodes: FlowNode[] = graph.nodes.map((node) => ({
    id: node.id,
    type: "dialogue",
    // Saved NodePosition has higher priority; auto-layout only fills gaps.
    position: saved.get(node.id) ?? (vertical ? { x: auto.get(node.id)!.y * 1.6, y: auto.get(node.id)!.x } : { x: auto.get(node.id)!.x, y: auto.get(node.id)!.y }),
    data: node,
    style: { width: NODE_W, height: nodeHeight(node) },
  }));

  const outgoing = new Map<string, number>();
  for (const edge of graph.edges) outgoing.set(edge.source, (outgoing.get(edge.source) ?? 0) + 1);

  let lane = 0;
  const edges: FlowEdge[] = graph.edges.map((edge) => {
    const isBack = back.has(edge.id);
    const style = edgeStyle(edge, outgoing.get(edge.source)!);
    return {
      id: edge.id,
      source: edge.source,
      target: edge.target,
      sourceHandle: "out",
      targetHandle: "in",
      type: isBack && !vertical ? "loop" : "default",
      label: edgeLabel(edge),
      labelStyle: { transform: rotateLabels ? "rotate(-90deg)" : "none", transformBox: "fill-box", transformOrigin: "center" },
      style: { ...style },
      markerEnd: { type: "arrowclosed", color: style.stroke },
      data: { kind: edge.kind, condition: edge.condition, backEdge: isBack, lane: isBack ? lane++ : 0, rotateLabels },
    };
  });

  return { nodes, edges };
}
