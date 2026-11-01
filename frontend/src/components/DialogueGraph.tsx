import { useMemo, useState, useCallback } from "react";
import { Background, Controls, ReactFlow, applyEdgeChanges, applyNodeChanges, type Connection, type Edge, type Node, type NodeChange, type EdgeChange } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import "./dialogue-graph.css";
import type { DialogueGraph as Graph, GraphNode, GraphEdge } from "../graph/contract";
import { toFlow } from "../graph/toFlow";
import { DialogueNode } from "./DialogueNode";
import { LoopEdge } from "./LoopEdge";

// Defined outside the component so React Flow doesn't warn about new objects each render.
const nodeTypes = { dialogue: DialogueNode };
const edgeTypes = { loop: LoopEdge };

interface Props {
  graph: Graph;
  /** NodePosition rows from GET /projects/{id}; omit to use auto-layout only. */
  savedPositions?: Map<string, { x: number; y: number }>;
  onSelectNode: (node: GraphNode) => void;
  onEditNode?: (node: GraphNode) => void;
  vertical?: boolean;
  rotateLabels?: boolean;
  onConnectNodes?: (from: string, to: string, kind: "choice" | "jump", label: string) => void;
  onSelectEdge?: (edge: GraphEdge) => void;
  onMoveNode: (id: string, position: { x: number; y: number }) => void;
}

export function DialogueGraph({ graph, savedPositions, onSelectNode, onMoveNode, onEditNode, vertical = false, rotateLabels = false, onConnectNodes, onSelectEdge }: Props) {
  // Re-derives only when a sync returns a new graph.
  const { nodes, edges } = useMemo(() => toFlow(graph, savedPositions, vertical, rotateLabels), [graph, savedPositions]);

  const [liveNodes, setLiveNodes] = useState<Node[]>(nodes as Node[]);
  const [liveEdges, setLiveEdges] = useState<Edge[]>(edges as Edge[]);
  const connect = useCallback((connection: Connection) => {
    if (!connection.source || !connection.target || !onConnectNodes) return;
    const kind = window.confirm("Player choice? OK = choice, Cancel = automatic jump") ? "choice" : "jump";
    const label = kind === "choice" ? window.prompt("Choice text:", "Continue") : "";
    if (label === null || (kind === "choice" && !label.trim())) return;
    onConnectNodes(connection.source, connection.target, kind, label ?? "");
  }, [onConnectNodes]);
  return (
    <div className="dlg-canvas">
      <ReactFlow
        nodes={liveNodes}
        edges={liveEdges}
        onNodesChange={(changes: NodeChange<Node>[]) => setLiveNodes(current => applyNodeChanges(changes, current))}
        onEdgesChange={(changes: EdgeChange<Edge>[]) => setLiveEdges(current => applyEdgeChanges(changes, current))}
        onConnect={connect}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        onEdgeClick={(_: unknown, edge: Edge) => {
          const original = graph.edges.find(item => item.id === edge.id);
          if (original) onSelectEdge?.(original);
        }}
        onNodeClick={(_: unknown, node: Node) => onSelectNode(node.data as GraphNode)}
        onNodeDragStop={(_: unknown, node: Node) => onMoveNode(node.id, node.position)}
        nodesConnectable={Boolean(onConnectNodes)}
        edgesReconnectable={false}
        deleteKeyCode={null}
        fitView
        minZoom={0.1}
        // Text and source spans also change identity, even if every edge ID stays the same.
        key={`${graph.snapshot_id}-${vertical}-${rotateLabels}`}
      >
        <Background gap={24} />
        <Controls showInteractive={false} />
      </ReactFlow>
      {onEditNode && <div className="dlg-edit-hint">Click a node to select it, then use Edit node.</div>}
      <div className="dlg-legend" aria-label="Edge legend">
        <svg width="36" height="8" aria-hidden><line x1="0" y1="4" x2="36" y2="4" stroke="#3d5a80" strokeWidth="2" /></svg>
        <span>Player choice</span>
        <svg width="36" height="8" aria-hidden><line x1="0" y1="4" x2="36" y2="4" stroke="#8a5a00" strokeWidth="2" strokeDasharray="2 5" strokeLinecap="round" /></svg>
        <span>Automatic jump</span>
      </div>
      {graph.diagnostics.length > 0 && (
        <ul className="dlg-diagnostics">
          {graph.diagnostics.map((d, i) => (
            <li key={i}>Line {d.line ?? "?"}: {d.message}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
