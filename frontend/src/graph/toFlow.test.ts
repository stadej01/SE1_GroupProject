import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import type { DialogueGraph } from "./contract";
import { NODE_H, NODE_W, findBackEdges, layout, loopClearance, loopPath, nodeHeight, toFlow } from "./toFlow";

// Same fixture the Python tests produce, so both sides are pinned to one contract.
const graph: DialogueGraph = JSON.parse(
  readFileSync(new URL("../../../fixtures/merchant.graph.json", import.meta.url), "utf8"),
);
const { nodes, edges } = toFlow(graph);
const edge = (id: string) => edges.find((e) => e.id === id)!;

test("AC1: choices render solid, jumps render dotted", () => {
  const fromGreeting = edges.filter((e) => e.source === "Node_Merchant_Greeting");
  const jumps = fromGreeting.filter((e) => e.data.kind === "jump");
  const choices = fromGreeting.filter((e) => e.data.kind === "choice");
  assert.equal(jumps.length, 1);
  assert.equal(choices.length, 4);
  for (const e of jumps) assert.ok(e.style.strokeDasharray, `${e.id} should be dotted`);
  for (const e of choices) assert.equal(e.style.strokeDasharray, undefined, `${e.id} should be solid`);
});

test("AC1: labels carry the choice text and condition", () => {
  assert.equal(edge("Node_Merchant_Greeting:jump:0").label, "[if talk_count > 5] jump");
  assert.match(edge("Node_Merchant_Greeting:choice:0").label!, /^\[if gold >= 50\] I'll buy/);
});

test("AC2: loops back to earlier nodes are detected, forward edges are not", () => {
  assert.deepEqual([...findBackEdges(graph)].sort(), [
    "Node_Browse_Shop:choice:0",
    "Node_Browse_Shop:choice:1",
    "Node_Hand_In_Quest:jump:0",
  ]);
});

test("AC2: loop edges use the curved loop edge type", () => {
  const loop = edge("Node_Hand_In_Quest:jump:0");
  assert.equal(loop.type, "loop");
  assert.ok(loop.style.strokeDasharray, "a looping jump is still dotted");
  assert.equal(edge("Node_Merchant_Greeting:choice:0").type, "default");
});

test("AC2: every loop stays clear of all nodes, including ones between", () => {
  const boxes = new Map(nodes.map((n) => [n.id, { ...n.position, width: NODE_W, height: NODE_H }]));
  const loops = edges.filter((x) => x.data.backEdge);
  assert.equal(loops.length, 3);
  for (const e of loops) {
    const s = boxes.get(e.source)!, t = boxes.get(e.target)!;
    // The same handle coordinates React Flow hands to LoopEdge.tsx.
    const [sx, sy] = [s.x + NODE_W, s.y + NODE_H / 2];
    const [tx, ty] = [t.x, t.y + NODE_H / 2];
    const { points } = loopPath(sx, sy, tx, ty, loopClearance(boxes.values(), tx, sx, e.data.lane), e.data.lane);

    for (let i = 0; i < points.length - 1; i++) {
      const [[x1, y1], [x2, y2]] = [points[i], points[i + 1]];
      for (let k = 1; k < 50; k++) {
        const [px, py] = [x1 + ((x2 - x1) * k) / 50, y1 + ((y2 - y1) * k) / 50];
        for (const [id, b] of boxes) {
          const inside = px > b.x && px < b.x + b.width && py > b.y && py < b.y + b.height;
          assert.ok(!inside, `${e.id} crosses ${id} at (${px.toFixed(0)}, ${py.toFixed(0)})`);
        }
      }
    }
  }
});

test("saved positions override auto-layout", () => {
  const { nodes: placed } = toFlow(graph, new Map([["Node_Exit", { x: 5, y: 7 }]]));
  assert.deepEqual(placed.find((n) => n.id === "Node_Exit")!.position, { x: 5, y: 7 });
});

test("the designated starting node is marked in the graph", () => {
  const { nodes: mapped } = toFlow(graph);
  assert.deepEqual(mapped.filter((n) => n.data.is_start).map((n) => n.id), graph.start_nodes);
});

test("multiple conversation entry nodes are all marked", () => {
  const { nodes: mapped } = toFlow({ ...graph, start_nodes: ["Node_Merchant_Greeting", "Node_Exit"] });
  assert.deepEqual(mapped.filter((n) => n.data.is_start).map((n) => n.id), ["Node_Merchant_Greeting", "Node_Exit"]);
});

test("disconnected components and isolated nodes are all retained", () => {
  const isolated: DialogueGraph = { ...graph, edges: [] };
  assert.equal(toFlow(isolated).nodes.length, graph.nodes.length);
  assert.equal(findBackEdges(isolated).size, 0);
});

test("node height reserves space for long dialogue that wraps in the graph", () => {
  const longLine = "Narrator: " + "A".repeat(80);
  const longNode = { ...graph.nodes[0], dialogue_lines: [{ speaker: "Narrator", text: "A".repeat(80), source_line: 1 }] };
  assert.ok(nodeHeight(longNode) > NODE_H);

  const overlapGraph: DialogueGraph = {
    ...graph,
    nodes: [
      longNode,
      { ...longNode, id: "another", dialogue_lines: [{ speaker: "Narrator", text: longLine, source_line: 2 }] },
    ],
    edges: [],
    start_nodes: [],
  };
  const boxes = layout(overlapGraph, new Set());
  const first = boxes.get(longNode.id)!;
  const second = boxes.get("another")!;
  assert.ok(second.y >= first.y + first.height, "wrapped dialogue nodes must not overlap");
});

test("many loop lanes keep gutters outside a self-loop's node", () => {
  for (let lane = 0; lane < 25; lane++) {
    const { points } = loopPath(NODE_W, NODE_H / 2, 0, NODE_H / 2, NODE_H + 30 + lane * 16, lane);
    assert.ok(points[1][0] > NODE_W);
    assert.ok(points[3][0] < 0);
  }
});

test("a 12,000-node conversation maps without recursion overflow", () => {
  const large: DialogueGraph = { snapshot_id: "large", start_nodes: ["0"], diagnostics: [],
    nodes: Array.from({ length: 12_000 }, (_, i) => ({ id: String(i), category: null, color: null,
      preview: "", source_line: i + 1, source_end_line: i + 1 })),
    edges: Array.from({ length: 11_999 }, (_, i) => ({ id: `edge-${i}`, source: String(i), target: String(i + 1),
      kind: "jump", condition: null, label: null, source_line: i + 1 })),
  };
  const mapped = toFlow(large);
  assert.equal(mapped.nodes.length, 12_000);
  assert.ok(mapped.nodes.at(-1)!.position.x > mapped.nodes[0].position.x);
});
