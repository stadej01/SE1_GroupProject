
import { test } from "node:test";
import assert from "node:assert/strict";

import type {
  DialogueGraph,
  GraphEdge
} from "../graph/contract";

import {
  deleteSelection,
  inspectDeletion
} from "./deleteSelection";

// Test dialogue with four nodes.
// A -> B, A -> C, B -> C.
// D is isolated and should remain unaffected.
const markdown = [
  "<!-- start: A -->",
  "# A",
  "Narrator: Hello.",
  '* "Go to B" -> B',
  "<<jump: C>>",
  "",
  "# B",
  "Narrator: Branch B.",
  '* "Finish" -> C',
  "",
  "# C",
  "Narrator: Ending.",
  "",
  "# D",
  "Narrator: Untouched."
].join("\n");

function makeGraph(): DialogueGraph {
  const edges: GraphEdge[] = [
    {
      id: "AB",
      source: "A",
      target: "B",
      kind: "choice",
      label: "Go to B",
      condition: null,
      source_line: 4
    },
    {
      id: "AC",
      source: "A",
      target: "C",
      kind: "jump",
      label: null,
      condition: null,
      source_line: 5
    },
    {
      id: "BC",
      source: "B",
      target: "C",
      kind: "choice",
      label: "Finish",
      condition: null,
      source_line: 9
    }
  ];

  return {
    snapshot_id: "test",
    start_nodes: ["A"],
    end_nodes: [],
    diagnostics: [],
    nodes: ["A", "B", "C", "D"].map(id => ({
      id,
      category: null,
      color: null,
      preview: `Node ${id}`,
      source_line: 0,
      source_end_line: 0
    })),
    edges
  };
}

// AC1: Single node deletion
test("US-14 AC1: deletes one selected node and its connections", () => {
  const result = deleteSelection(
    markdown,
    makeGraph(),
    ["B"],
    []
  );

  assert.deepEqual(
    result.graph.nodes.map(node => node.id),
    ["A", "C", "D"]
  );

  assert.deepEqual(
    result.graph.edges.map(edge => edge.id),
    ["AC"]
  );

  // Unselected nodes remain.
  assert.ok(result.graph.nodes.some(n => n.id === "D"));
});

// AC1: Multiple node deletion
test("US-14 AC1: deletes multiple selected nodes", () => {
  const result = deleteSelection(
    markdown,
    makeGraph(),
    ["B", "C"],
    []
  );

  assert.deepEqual(
    result.graph.nodes.map(node => node.id),
    ["A", "D"]
  );

  assert.equal(result.graph.edges.length, 0);

  // Dialogue outside the selection remains.
  assert.match(result.markdown, /Narrator: Hello/);
  assert.match(result.markdown, /Narrator: Untouched/);
});

// AC2: Detect references before deletion
test("US-14 AC2: identifies nodes referencing a selected node", () => {
  const impact = inspectDeletion(
    makeGraph(),
    ["B"],
    []
  );

  // A references B.
  assert.deepEqual(
    impact.incoming.map(edge => edge.source),
    ["A"]
  );

  // B references C.
  assert.deepEqual(
    impact.outgoing.map(edge => edge.target),
    ["C"]
  );

  assert.deepEqual(impact.nodes, ["B"]);
  assert.equal(impact.connected.length, 2);
});

// AC5: Synchronize removal with Markdown
test("US-14 AC5: removes deleted nodes and connections from graph and Markdown", () => {
  const result = deleteSelection(
    markdown,
    makeGraph(),
    ["B"],
    []
  );

  // Graph no longer contains B.
  assert.ok(
    !result.graph.nodes.some(node => node.id === "B")
  );

  // Graph no longer contains references to B.
  assert.ok(
    result.graph.edges.every(edge =>
      edge.source !== "B" && edge.target !== "B"
    )
  );

  // Markdown no longer contains B or its references.
  assert.doesNotMatch(result.markdown, /^# B$/m);
  assert.doesNotMatch(result.markdown, /-> B/);
  assert.doesNotMatch(result.markdown, /"Finish" -> C/);

  // Unrelated content survives.
  assert.match(result.markdown, /^# A$/m);
  assert.match(result.markdown, /^# C$/m);
  assert.match(result.markdown, /^# D$/m);
  assert.match(result.markdown, /<<jump: C>>/);
  assert.match(result.markdown, /Narrator: Untouched/);
});

// Additional test: Delete a connection only
test("US-14: deleting a selected connection preserves its nodes", () => {
  const result = deleteSelection(
    markdown,
    makeGraph(),
    [],
    ["AB"]
  );

  assert.equal(result.graph.nodes.length, 4);

  assert.deepEqual(
    result.graph.edges.map(edge => edge.id),
    ["AC", "BC"]
  );

  assert.doesNotMatch(result.markdown, /"Go to B" -> B/);
  assert.match(result.markdown, /^# A$/m);
  assert.match(result.markdown, /^# B$/m);
});

// Additional test: Deleting the starting node
test("US-14: deleting the start node removes its start directive", () => {
  const result = deleteSelection(
    markdown,
    makeGraph(),
    ["A"],
    []
  );

  assert.deepEqual(result.graph.start_nodes, []);
  assert.doesNotMatch(result.markdown, /<!-- start: A -->/);
  assert.doesNotMatch(result.markdown, /^# A$/m);

  // Other node sections remain.
  assert.match(result.markdown, /^# B$/m);
  assert.match(result.markdown, /^# C$/m);
  assert.match(result.markdown, /^# D$/m);
});
