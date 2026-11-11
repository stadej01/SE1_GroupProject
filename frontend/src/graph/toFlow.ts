/**
 * Converts the dialogue graph contract into the nodes and edges that React Flow draws.
 *
 * Every function here is pure and imports neither React nor @xyflow/react, so
 * the logic runs under `node --test` without a browser. The returned objects
 * match the structure of React Flow's Node and Edge types, so DialogueGraph.tsx
 * can pass them straight to <ReactFlow>.
 *
 * - Choices are solid. Jumps are solid when they end their node or are its only
 *   exit; other jumps are dotted.
 * - A depth-first search marks edges that point back to a node on the current
 *   path, including self-loops.
 * - Nodes use a left-to-right layered layout, with vertical layout available.
 * - Loop edges travel through column gaps and under every node in their span.
 */

import type { DialogueGraph, GraphEdge, GraphNode } from "./contract";

export const NODE_W = 240;
export const NODE_H = 96;

/** Reserve enough space for dialogue wrapping before React Flow measures nodes. */
export function nodeHeight(node: GraphNode): number {
  const lines = node.dialogue_lines?.length
    ? node.dialogue_lines.map((line) => `${line.speaker}: ${line.text}`)
    : [node.preview || "No dialogue lines"];
  const wrappedLines = lines.reduce(
    (total, line) =>
      total +
      Math.max(
        1,
        ...line.split("\n").map((part) => Math.ceil(part.length / 16))
      ),
    0
  );

  return Math.max(
    NODE_H,
    64 + wrappedLines * 19 + Math.max(0, lines.length - 1) * 5
  );
}

const GAP_X = 120;
const GAP_Y = 48;
export const LOOP_MARGIN = 28;
const LANE_STEP = 16;

export const EDGE_STYLE = {
  choice: { stroke: "#3d5a80", strokeWidth: 1.75 },
  jump: { stroke: "#8a5a00", strokeWidth: 1.75 },
  midJump: {
    stroke: "#8a5a00",
    strokeWidth: 1.75,
    strokeDasharray: "2 5",
    strokeLinecap: "round",
  },
} as const;

/**
 * A jump is solid if it ends its node or is its only exit. Mid-node jumps with
 * dialogue or choices after them are dotted.
 */
export function edgeStyle(edge: GraphEdge, outgoingCount: number) {
  if (edge.kind === "choice") return EDGE_STYLE.choice;
  const endsNode = "ends_node" in edge && edge.ends_node === true;
  return endsNode || outgoingCount === 1
    ? EDGE_STYLE.jump
    : EDGE_STYLE.midJump;
}

export interface Box {
  x: number;
  y: number;
  width: number;
  height: number;
}

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
  data: {
    kind: GraphEdge["kind"];
    condition: string | null;
    backEdge: boolean;
    lane: number;
    rotateLabels: boolean;
  };
}

function startNodeIds(graph: DialogueGraph): Set<string> {
  const starts = Array.isArray(graph.start_nodes) ? graph.start_nodes : [];
  const legacyStart =
    "start" in graph && typeof graph.start === "string" ? [graph.start] : [];
  return new Set([...starts, ...legacyStart]);
}

/** Edges that point back to a node already on the DFS path, including self-loops. */
export function findBackEdges(graph: DialogueGraph): Set<string> {
  const outgoing = new Map<string, GraphEdge[]>();
  for (const edge of graph.edges) {
    if (!outgoing.has(edge.source)) outgoing.set(edge.source, []);
    outgoing.get(edge.source)!.push(edge);
  }

  const backEdges = new Set<string>();
  const state = new Map<string, "active" | "done">();
  const roots = [
    ...startNodeIds(graph),
    ...graph.nodes.map((node) => node.id),
  ];

  // An explicit stack avoids recursion overflow on long conversations.
  for (const id of roots) {
    if (state.has(id)) continue;
    state.set(id, "active");
    const stack = [{ id, next: 0 }];

    while (stack.length) {
      const frame = stack[stack.length - 1];
      const edges = outgoing.get(frame.id) ?? [];
      if (frame.next === edges.length) {
        state.set(frame.id, "done");
        stack.pop();
        continue;
      }

      const edge = edges[frame.next++];
      const targetState = state.get(edge.target);
      if (targetState === "active") {
        backEdges.add(edge.id);
      } else if (targetState === undefined) {
        state.set(edge.target, "active");
        stack.push({ id: edge.target, next: 0 });
      }
    }
  }

  return backEdges;
}

/** Left-to-right layered layout: rank is the longest forward path from a root. */
export function layout(
  graph: DialogueGraph,
  backEdges: Set<string>
): Map<string, Box> {
  const forward = graph.edges.filter((edge) => !backEdges.has(edge.id));
  const outgoing = new Map<string, GraphEdge[]>();
  const indegree = new Map(graph.nodes.map((node) => [node.id, 0]));

  for (const edge of forward) {
    indegree.set(edge.target, (indegree.get(edge.target) ?? 0) + 1);
    if (!outgoing.has(edge.source)) outgoing.set(edge.source, []);
    outgoing.get(edge.source)!.push(edge);
  }

  const rank = new Map(graph.nodes.map((node) => [node.id, 0]));
  const queue = graph.nodes
    .filter((node) => indegree.get(node.id) === 0)
    .map((node) => node.id);
  for (let cursor = 0; cursor < queue.length; cursor++) {
    const id = queue[cursor];
    for (const edge of outgoing.get(id) ?? []) {
      rank.set(
        edge.target,
        Math.max(rank.get(edge.target)!, rank.get(id)! + 1)
      );
      indegree.set(edge.target, indegree.get(edge.target)! - 1);
      if (indegree.get(edge.target) === 0) queue.push(edge.target);
    }
  }

  const nextYInRank = new Map<number, number>();
  const boxes = new Map<string, Box>();
  for (const node of graph.nodes) {
    const nodeRank = rank.get(node.id)!;
    const y = nextYInRank.get(nodeRank) ?? 0;
    const height = nodeHeight(node);
    nextYInRank.set(nodeRank, y + height + GAP_Y);
    boxes.set(node.id, {
      x: nodeRank * (NODE_W + GAP_X),
      y,
      width: NODE_W,
      height,
    });
  }

  return boxes;
}

/** Lowest y a loop must pass to avoid nodes in the horizontal span. */
export function loopClearance(
  boxes: Iterable<Box>,
  x1: number,
  x2: number,
  lane = 0
): number {
  const [lo, hi] = x1 < x2 ? [x1, x2] : [x2, x1];
  let bottom = -Infinity;
  for (const box of boxes) {
    if (box.x <= hi && box.x + box.width >= lo) {
      bottom = Math.max(bottom, box.y + box.height);
    }
  }
  return bottom + LOOP_MARGIN + lane * LANE_STEP;
}

export const LOOP_GUTTER = GAP_X / 2 - 12;
const RADIUS = 14;

/**
 * Route a loop out the source's right side, under every node in its span, and
 * back through the gap left of the target. `points` are the corners used by
 * tests to check that no nodes are crossed.
 */
export function loopPath(
  sx: number,
  sy: number,
  tx: number,
  ty: number,
  clearY: number,
  lane = 0
) {
  // Additional loops get deeper lanes without moving a side gutter into a node.
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
  const points = [
    [sx, sy],
    [xr, sy],
    [xr, clearY],
    [xl, clearY],
    [xl, ty],
    [tx, ty],
  ] as const;

  return { path, points, labelX: (xr + xl) / 2, labelY: clearY };
}

function edgeLabel(edge: GraphEdge): string | undefined {
  const condition = edge.condition ? `[if ${edge.condition}]` : "";
  if (edge.kind === "jump") return condition ? `${condition} jump` : "jump";

  const text =
    edge.label && edge.label.length > 28
      ? `${edge.label.slice(0, 27)}…`
      : edge.label ?? "";
  return [condition, text].filter(Boolean).join(" ");
}

export function toFlow(
  graph: DialogueGraph,
  saved: Map<string, { x: number; y: number }> = new Map(),
  vertical = false,
  rotateLabels = false
) {
  const backEdges = findBackEdges(graph);
  const auto = layout(graph, backEdges);
  const starts = startNodeIds(graph);
  const ends = new Set(graph.end_nodes);

  const nodes: FlowNode[] = graph.nodes.map((node) => {
    const position = auto.get(node.id)!;
    return {
      id: node.id,
      type: "dialogue",
      // Saved positions take priority; auto-layout fills nodes without one.
      position:
        saved.get(node.id) ??
        (vertical
          ? { x: position.y * 1.6, y: position.x }
          : { x: position.x, y: position.y }),
      data: {
        ...node,
        is_start: starts.has(node.id),
        is_end: ends.has(node.id),
      },
      style: { width: NODE_W, height: nodeHeight(node) },
    };
  });

  const outgoingCount = new Map<string, number>();
  for (const edge of graph.edges) {
    outgoingCount.set(
      edge.source,
      (outgoingCount.get(edge.source) ?? 0) + 1
    );
  }

  let lane = 0;
  const edges: FlowEdge[] = graph.edges.map((edge) => {
    const isBackEdge = backEdges.has(edge.id);
    const style = edgeStyle(edge, outgoingCount.get(edge.source)!);
    return {
      id: edge.id,
      source: edge.source,
      target: edge.target,
      sourceHandle: "out",
      targetHandle: "in",
      type: isBackEdge && !vertical ? "loop" : "default",
      label: edgeLabel(edge),
      labelStyle: {
        transform: rotateLabels ? "rotate(-90deg)" : "none",
        transformBox: "fill-box",
        transformOrigin: "center",
      },
      style: { ...style },
      markerEnd: { type: "arrowclosed", color: style.stroke },
      data: {
        kind: edge.kind,
        condition: edge.condition,
        backEdge: isBackEdge,
        lane: isBackEdge ? lane++ : 0,
        rotateLabels,
      },
    };
  });

  return { nodes, edges };
}
