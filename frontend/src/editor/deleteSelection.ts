
import type { DialogueGraph, GraphEdge } from "../graph/contract";

/**
 * Determine everything affected by deleting selected
 * nodes and connections.
 */
export function inspectDeletion(
  graph: DialogueGraph,
  nodeIds: Iterable<string>,
  edgeIds: Iterable<string>
) {
  const requestedNodes = new Set(nodeIds);
  const requestedEdges = new Set(edgeIds);

  const nodes = graph.nodes
    .filter(node => requestedNodes.has(node.id))
    .map(node => node.id);

  const removedNodes = new Set(nodes);

  // Connections selected directly OR attached to deleted nodes
  const edges = graph.edges.filter(edge =>
    requestedEdges.has(edge.id) ||
    removedNodes.has(edge.source) ||
    removedNodes.has(edge.target)
  );

  // Connections from surviving nodes into deleted nodes
  const incoming = edges.filter(edge =>
    removedNodes.has(edge.target) &&
    !removedNodes.has(edge.source)
  );

  // Connections from deleted nodes into surviving nodes
  const outgoing = edges.filter(edge =>
    removedNodes.has(edge.source) &&
    !removedNodes.has(edge.target)
  );

  const connected = edges.filter(edge =>
    removedNodes.has(edge.source) ||
    removedNodes.has(edge.target)
  );

  const startNodes = graph.start_nodes.filter(id =>
    removedNodes.has(id)
  );

  return { nodes, edges, incoming, outgoing, connected, startNodes };
}


function matchesEdge(line: string, edge: GraphEdge): boolean {
  const text = line.trim();

  if (edge.kind === "choice") {
    const match =
      /^\*\s*(?:\[if\s+([^\]]+?)\]\s*)?"([^"]*)"\s*->\s*(\w+)\s*(?:<!--.*-->)?$/.exec(text);

    return Boolean(
      match &&
      match[2] === (edge.label ?? "") &&
      match[3] === edge.target &&
      (match[1] ?? null) === (edge.condition ?? null)
    );
  }

  const match =
    /^(?:\[if\s+([^\]]+?)\]\s*)?<<jump:\s*(\w+)\s*>>\s*(?:<!--.*-->)?$/.exec(text);

  return Boolean(
    match &&
    match[2] === edge.target &&
    (match[1] ?? null) === (edge.condition ?? null)
  );
}

export function deleteSelection(
  source: string,
  graph: DialogueGraph,
  nodeIds: Iterable<string>,
  edgeIds: Iterable<string>
) {
  const impact = inspectDeletion(graph, nodeIds, edgeIds);

  if (!impact.nodes.length && !impact.edges.length) {
    throw new Error("Select a node or connection to delete.");
  }

  const removedNodes = new Set(impact.nodes);
  const removedEdges = new Set(impact.edges.map(edge => edge.id));

  const lines = source.split("\n");
  const removedLines = new Set<number>();

  // Identify each node's full Markdown section.
  const headers: { id: string; start: number }[] = [];

  lines.forEach((line, i) => {
    const match = /^#\s+(\w+)\s*$/.exec(line.trim());
    if (match) headers.push({ id: match[1], start: i });
  });

  const spans = new Map<string, { start: number; end: number }>();

  headers.forEach((header, i) => {
    spans.set(header.id, {
      start: header.start,
      end: headers[i + 1]?.start ?? lines.length
    });
  });

  // Delete entire Markdown sections for selected nodes.
  for (const id of removedNodes) {
    const span = spans.get(id);

    if (!span) {
      throw new Error(`Node ${id} was not found in Markdown.`);
    }

    for (let i = span.start; i < span.end; i++) {
      removedLines.add(i);
    }
  }

  // Remove start-node directives for deleted nodes.
  lines.forEach((line, i) => {
    const match =
      /^<!--\s*start:\s*(\w+)\s*-->$/.exec(line.trim());

    if (match && removedNodes.has(match[1])) {
      removedLines.add(i);
    }
  });

  // Remove connection lines in surviving nodes.
  for (const edge of impact.edges) {
    if (removedNodes.has(edge.source)) continue;

    const span = spans.get(edge.source);

    if (!span) {
      throw new Error(`Source node ${edge.source} not found.`);
    }

    const candidates: number[] = [];

    for (let i = span.start + 1; i < span.end; i++) {
      if (!removedLines.has(i) && matchesEdge(lines[i], edge)) {
        candidates.push(i);
      }
    }

    if (!candidates.length) {
      throw new Error(
        `Cannot find ${edge.source} → ${edge.target} in Markdown.`
      );
    }

    // Prefer the original source line when still valid.
    const preferred =
      edge.source_line > 0 &&
      candidates.includes(edge.source_line - 1)
        ? edge.source_line - 1
        : edge.source_line === 0
          ? candidates[candidates.length - 1]
          : candidates[0];

    removedLines.add(preferred);
  }

  const markdown = lines
    .filter((_, i) => !removedLines.has(i))
    .join("\n");

  const updatedGraph: DialogueGraph = {
    ...graph,
    nodes: graph.nodes.filter(node => !removedNodes.has(node.id)),
    edges: graph.edges.filter(edge => !removedEdges.has(edge.id)),
    start_nodes: graph.start_nodes.filter(id => !removedNodes.has(id)),
    diagnostics: []
  };

  return { markdown, graph: updatedGraph, impact };
}
