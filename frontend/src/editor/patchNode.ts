import type { GraphNode } from "../graph/contract";

/** Replace only the selected node's metadata and dialogue lines. Preserve choices,
 * jumps, comments and other syntax exactly. Uses the source snapshot line span. */
export function patchNodeSource(markdown: string, node: GraphNode, fields: Record<string, string>, dialogue: string): string {
  const lines = markdown.split("\n");
  const first = node.source_line - 1;
  const last = node.source_end_line;
  if (first < 0 || last > lines.length || !/^#\s+\w+\s*$/.test(lines[first])) throw new Error("Node source location is no longer valid. Parse again.");
  const current = lines.slice(first, last);
  const originalId = node.id;
  const nextId = fields.node_id?.trim() || originalId;
  if (!/^\w+$/.test(nextId)) throw new Error("Node ID must contain only letters, numbers, or underscores.");
  if (nextId !== originalId) throw new Error("Renaming node IDs is not supported yet because incoming links must also be updated.");
  const speaker = fields.speaker?.trim();
  if (!speaker || !/^\w[\w ]*$/.test(speaker)) throw new Error("Speaker is required (letters, numbers, spaces, underscores).");
  if (!dialogue.trim()) throw new Error("Dialogue cannot be empty.");
  if (dialogue.split("\n").some(line => !line.trim())) throw new Error("Dialogue lines cannot be blank.");
  const knownLines = new Set((node.dialogue_lines ?? []).map(d => d.source_line - node.source_line));
  const metaPattern = /^@([a-z_][a-z_0-9]*)\s*:/;
  const requested = Object.entries(fields).filter(([k]) => k !== "node_id" && k !== "speaker" && k !== "audience");
  const newMetadata: string[] = [];
  for (const [key, value] of requested) {
    if (!/^[a-z_][a-z_0-9]*$/.test(key)) throw new Error(`Invalid metadata field: ${key}`);
    if (value.includes("\n") || value.includes("\r")) throw new Error(`Field ${key} must be one line.`);
    if (value.trim()) newMetadata.push(`@${key}: ${value.trim()}`);
  }
  const audience = fields.audience?.trim();
  if (audience) newMetadata.unshift(`@audience: ${audience}`);
  const result = [current[0], ...newMetadata, ...dialogue.split("\n").map(line => `${speaker}: ${line}`)];
  for (let i = 1; i < current.length; i++) {
    const line = current[i];
    if (metaPattern.test(line) || knownLines.has(i)) continue;
    result.push(line);
  }
  lines.splice(first, last - first, ...result);
  return lines.join("\n");
}
