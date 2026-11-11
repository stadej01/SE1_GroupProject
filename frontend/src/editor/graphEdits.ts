import type { GraphNode, GraphEdge, EdgeKind } from "../graph/contract";

/** Locate a node by stable ID in the current pending snapshot. */
export function locateNode(source: string, id: string): Pick<GraphNode, "source_line" | "source_end_line" | "dialogue_lines"> {
  const lines = source.split("\n");
  const header = `# ${id}`;
  const start = lines.findIndex(line => line.trim() === header);
  if (start < 0) throw new Error(`Node ${id} not found in the current draft.`);
  let end = start + 1;
  while (end < lines.length && !/^#\s+\w+\s*$/.test(lines[end])) end++;
  const dialogue_lines = lines.slice(start, end).flatMap((line, i) => {
    const match = /^([\w ]+):\s+(.+?)(?:\s*<!--.*)?$/.exec(line);
    return match ? [{ speaker: match[1], text: match[2], source_line: start + i + 1 }] : [];
  });
  return { source_line: start + 1, source_end_line: end, dialogue_lines };
}

export function appendNode(source: string, id: string, speaker: string, dialogue: string): string {
  return source.trimEnd() + `\n\n# ${id}\n${speaker}: ${dialogue}\n`;
}

/** Replace the document-level starting node directives. */
export function setStartNodes(source: string, ids: string[]): string {
  const lines = source.split("\n");
  const retainedLines = lines.filter(line => !/^\s*<!--\s*start:\s*\w+\s*-->\s*$/.test(line));
  const uniqueIds = [...new Set(ids)];
  for (const id of uniqueIds) {
    if (!/^\w+$/.test(id)) throw new Error("Starting node ID must contain only letters, numbers, or underscores.");
    if (!lines.some(line => line.trim() === `# ${id}`)) throw new Error(`Starting node ${id} does not exist in the current draft.`);
  }
  return [...uniqueIds.map(id => `<!-- start: ${id} -->`), ...retainedLines].join("\n");
}

/** Replace the document-level end-node directives. */
export function setEndNodes(source: string, ids: string[]): string {
  const lines = source.split("\n");
  const retainedLines = lines.filter(line => !/^\s*<!--\s*end:\s*\w+\s*-->\s*$/.test(line));
  const uniqueIds = [...new Set(ids)];
  for (const id of uniqueIds) {
    if (!/^\w+$/.test(id)) throw new Error("End node ID must contain only letters, numbers, or underscores.");
    if (!lines.some(line => line.trim() === `# ${id}`)) throw new Error(`End node ${id} does not exist in the current draft.`);
  }
  return [...uniqueIds.map(id => `<!-- end: ${id} -->`), ...retainedLines].join("\n");
}

/** Add a connection inside the source node, before the next header. */
export function appendConnection(source: string, from: string, to: string, kind: EdgeKind, label: string): string {
  if (!locateNode(source, to)) throw new Error("Target node does not exist.");
  const node = locateNode(source, from);
  if (kind === "choice" && (!label.trim() || label.includes('"') || label.includes("\n"))) {
    throw new Error("A choice requires a label without quotation marks or newlines.");
  }
  const syntax = kind === "choice" ? `* "${label.trim()}" -> ${to}` : `<<jump: ${to}>>`;
  const lines = source.split("\n");
  let insert = node.source_end_line;
  while (insert > node.source_line && !lines[insert - 1].trim()) insert--;
  lines.splice(insert, 0, syntax);
  return lines.join("\n");
}

/** Remove exactly one source connection, including its optional condition.
 * Match within the originating node so identical choices elsewhere remain untouched.
 */
export function removeConnection(source: string, edge: GraphEdge): string {
  const span = locateNode(source, edge.source);
  const lines = source.split("\n");
  const candidates: number[] = [];
  for (let i = span.source_line; i < span.source_end_line; i++) {
    const line = lines[i]?.trim() ?? "";
    if (edge.kind === "choice") {
      const match = /^\*\s*(?:\[if\s+([^\]]+?)\]\s*)?"([^"]*)"\s*->\s*(\w+)\s*(?:<!--.*-->)?$/.exec(line);
      if (match && match[2] === (edge.label ?? "") && match[3] === edge.target &&
          (match[1] ?? null) === (edge.condition ?? null)) candidates.push(i);
    } else {
      const match = /^(?:\[if\s+([^\]]+?)\]\s*)?<<jump:\s*(\w+)\s*>>\s*$/.exec(line);
      if (match && match[2] === edge.target && (match[1] ?? null) === (edge.condition ?? null)) candidates.push(i);
    }
  }
  if (!candidates.length) throw new Error(`Connection ${edge.source} → ${edge.target} was not found in the pending Markdown.`);
  // Prefer original line when it still points to the same connection.
  const preferred = candidates.includes(edge.source_line - 1) ? edge.source_line - 1 : candidates[0];
  lines.splice(preferred, 1);
  return lines.join("\n");
}
