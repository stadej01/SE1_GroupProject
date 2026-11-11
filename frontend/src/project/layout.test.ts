import { test } from "node:test";
import assert from "node:assert/strict";
import type { DialogueGraph } from "../graph/contract";
import { applyLayout, fillMissingPositions, readPositions, saveLayout, writeLayout } from "./layout";

const graph: DialogueGraph = {
  snapshot_id: "test", start_nodes: [], end_nodes: [], diagnostics: [],
  nodes: ["A", "B"].map(id => ({ id, category: null, color: null, preview: "Hello", source_line: 1, source_end_line: 2 })),
  edges: [{ id: "A-B", source: "A", target: "B", kind: "jump", label: null, condition: null, source_line: 2 }],
};

test("layout round trip preserves zero, negative, and decimal positions without sharing objects", () => {
  const data = { nodes: [{ id: "A", position: { x: 0, y: -24.5 } }, { id: "B", position: { x: 42.5, y: 100 } }] };
  const positions = readPositions(data);
  assert.deepEqual(writeLayout(positions), data);
  positions.get("A")!.x = 10;
  assert.equal(data.nodes[0].position.x, 0);
});

test("saving includes auto-layout nodes as well as dragged nodes", () => {
  const positions = new Map([["A", { x: 25, y: 40 }]]);
  assert.deepEqual(saveLayout(graph, positions, false).nodes, [
    { id: "A", position: { x: 25, y: 40 } }, { id: "B", position: { x: 360, y: 0 } },
  ]);
  assert.equal(positions.size, 1);
});

test("vertical positions remain the same after reopening with horizontal selected", () => {
  const positions = new Map([["A", { x: 25, y: 40 }]]);
  const sent = saveLayout(graph, positions, true);
  assert.deepEqual(sent.nodes[1], { id: "B", position: { x: 0, y: 360 } });
  applyLayout(positions, sent);
  assert.deepEqual(saveLayout(graph, positions, false), sent);
});

test("without a graph, save retains the known positions", () => {
  const positions = new Map([["A", { x: 25, y: 40 }], ["Previous", { x: 0, y: -10 }]]);
  assert.deepEqual(readPositions(saveLayout(null, positions, true)), positions);
});

test("save completion fills generated positions without replacing newer drags", () => {
  const positions = new Map([["A", { x: 25, y: 40 }]]);
  const submitted = saveLayout(graph, positions, true);
  positions.set("A", { x: 90, y: 100 });
  fillMissingPositions(positions, submitted);
  assert.deepEqual(positions.get("A"), { x: 90, y: 100 });
  assert.deepEqual(positions.get("B"), { x: 0, y: 360 });
});
