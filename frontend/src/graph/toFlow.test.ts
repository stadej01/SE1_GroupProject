import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import type { DialogueGraph } from "./contract";
import { NODE_H, NODE_W, findBackEdges, loopClearance, loopPath, toFlow } from "./toFlow";

const graph: DialogueGraph = JSON.parse(
  readFileSync(new URL("../../../fixtures/merchant.graph.json", import.meta.url), "utf8"),
);
const { nodes, edges } = toFlow(graph);
const edge = (id: string) => edges.find((edge) => edge.id === id)!;

test("US-29 AC1: choices render solid, mid-dialogue jumps render dotted", () => {
  const fromGreeting = edges.filter((edge) => edge.source === "Node_Merchant_Greeting");
  const jumps = fromGreeting.filter((edge) => edge.data.kind === "jump");
  const choices = fromGreeting.filter((edge) => edge.data.kind === "choice");
  assert.equal(jumps.length, 1);
  assert.equal(choices.length, 4);
  for (const edge of jumps) assert.ok(edge.style.strokeDasharray, `${edge.id} should be dotted`);
  for (const edge of choices) assert.equal(edge.style.strokeDasharray, undefined, `${edge.id} should be solid`);
});
  
test("US-29 AC1: a jump that ends its node renders solid", () => {
  const ending = edge("Node_Merchant_Annoyed:jump:0");
  assert.equal(ending.style.strokeDasharray, undefined);
  assert.equal(ending.style.stroke, "#8a5a00", "still jump-colored, not choice-colored");
});

test("US-29 AC1: a jump that is the node's only way out renders solid", () => {
  const only: DialogueGraph = {
    snapshot_id: "only-exit", start: "A", diagnostics: [],
    nodes: ["A", "B"].map((id, i) => ({ id, category: null, color: null, preview: "",
      source_line: i + 1, source_end_line: i + 1 })),
    edges: [{ id: "A:jump:0", source: "A", target: "B", kind: "jump", label: null,
              condition: "x > 1", source_line: 2, ends_node: false }],
  };
  assert.equal(toFlow(only).edges[0].style.strokeDasharray, undefined);
});

test("US-29 AC2: loops back to earlier nodes are detected, forward edges are not", () => {
  assert.deepEqual([...findBackEdges(graph)].sort(), [
    "Node_Browse_Shop:choice:0",
    "Node_Browse_Shop:choice:1",
    "Node_Hand_In_Quest:jump:0",
  ]);
});

test("US-29 AC2: loop edges use the curved loop edge type", () => {
  const loop = edge("Node_Hand_In_Quest:jump:0");
  assert.equal(loop.type, "loop");
  assert.equal(loop.style.strokeDasharray, undefined, "this looping jump ends its node, so it's solid");
  assert.equal(edge("Node_Merchant_Greeting:choice:0").type, "default");
});

test("saved positions override auto-layout", () => {
  const { nodes: placed } = toFlow(graph, new Map([["Node_Exit", { x: 5, y: 7 }]]));
  assert.deepEqual(placed.find((n) => n.id === "Node_Exit")!.position, { x: 5, y: 7 });
});

test("disconnected components and isolated nodes are all retained", () => {
  const isolated: DialogueGraph = { ...graph, edges: [] };
  assert.equal(toFlow(isolated).nodes.length, graph.nodes.length);
  assert.equal(findBackEdges(isolated).size, 0);
});

test("many loop lanes keep gutters outside a self-loop's node", () => {
  for (let lane = 0; lane < 25; lane++) {
    const { points } = loopPath(NODE_W, NODE_H / 2, 0, NODE_H / 2, NODE_H + 30 + lane * 16, lane);
    assert.ok(points[1][0] > NODE_W);
    assert.ok(points[3][0] < 0);
  }
});

test("a 12,000-node conversation maps without recursion overflow", () => {
  const large: DialogueGraph = { snapshot_id: "large", start: "0", diagnostics: [],
    nodes: Array.from({ length: 12_000 }, (_, i) => ({ id: String(i), category: null, color: null,
      preview: "", source_line: i + 1, source_end_line: i + 1 })),
    edges: Array.from({ length: 11_999 }, (_, i) => ({ id: `edge-${i}`, source: String(i), target: String(i + 1),
      kind: "jump", condition: null, label: null, source_line: i + 1, ends_node: true })),
  };
  const mapped = toFlow(large);
  assert.equal(mapped.nodes.length, 12_000);
  assert.ok(mapped.nodes.at(-1)!.position.x > mapped.nodes[0].position.x);
});
