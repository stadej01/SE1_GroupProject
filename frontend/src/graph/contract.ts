// Mirrors fixtures/merchant.graph.json — the payload of POST /sync (source: "markdown").
// Agree on this with whoever owns the parser; it's the only thing US-29 depends on.

export type EdgeKind = "choice" | "jump";

export interface GraphNode extends Record<string, unknown> {
  id: string;
  category: string | null;
  color: string | null;
  preview: string;
  is_start?: boolean;
  is_end?: boolean;
  metadata?: Record<string, string>;
  dialogue_lines?: { speaker: string; text: string; source_line: number }[];
  source_line: number;
  source_end_line: number;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  kind: EdgeKind;
  label: string | null;
  condition: string | null;
  source_line: number;
  /** True for a jump at the end of its node; may be absent on a new graph edge. */
  ends_node?: boolean;
}

export interface Diagnostic {
  severity: "error" | "warning";
  line?: number | null;
  node_id?: string;
  message: string;
}

export interface DialogueGraph {
  snapshot_id: string;
  start_nodes: string[];
  end_nodes: string[];
  nodes: GraphNode[];
  edges: GraphEdge[];
  diagnostics: Diagnostic[];
}
