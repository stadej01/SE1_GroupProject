
import { useMemo, useState, useCallback, useEffect } from "react";

import {
  Background,
  Controls,
  ReactFlow,
  applyEdgeChanges,
  applyNodeChanges,
  type Connection,
  type Edge,
  type Node,
  type NodeChange,
  type EdgeChange,
} from "@xyflow/react";

import "@xyflow/react/dist/style.css";
import "./dialogue-graph.css";

import type {
  DialogueGraph as Graph,
  GraphNode,
  GraphEdge,
} from "../graph/contract";

import { toFlow } from "../graph/toFlow";
import { DialogueNode } from "./DialogueNode";
import { LoopEdge } from "./LoopEdge";


// Keep these outside the component to avoid recreating them on each render.
const nodeTypes = { dialogue: DialogueNode };
const edgeTypes = { loop: LoopEdge };


interface Props {
  graph: Graph;
  savedPositions?: Map<string, { x: number; y: number }>;

  onSelectNode: (node: GraphNode) => void;
  onEditNode?: (node: GraphNode) => void;

  vertical?: boolean;
  rotateLabels?: boolean;

  onConnectNodes?: (
    from: string,
    to: string,
    kind: "choice" | "jump",
    label: string
  ) => void;

  onSelectEdge?: (edge: GraphEdge) => void;
  onPaneClick?: () => void;

  onMoveNode: (
    id: string,
    position: { x: number; y: number }
  ) => void;
}


export function DialogueGraph({
  graph,
  savedPositions,
  onSelectNode,
  onMoveNode,
  onEditNode,
  vertical = false,
  rotateLabels = false,
  onConnectNodes,
  onSelectEdge,
  onPaneClick,
}: Props) {

  // Convert the graph data into React Flow nodes and edges.
  const { nodes, edges } = useMemo(
    () => toFlow(graph, savedPositions, vertical, rotateLabels),
    [graph, savedPositions, vertical, rotateLabels]
  );

  const [liveNodes, setLiveNodes] = useState<Node[]>(nodes as Node[]);
  const [liveEdges, setLiveEdges] = useState<Edge[]>(edges as Edge[]);

  // Update React Flow when the parsed graph or layout changes.
  useEffect(() => {
    setLiveNodes(nodes as Node[]);
  }, [nodes]);

  useEffect(() => {
    setLiveEdges(edges as Edge[]);
  }, [edges]);

  // Create a new connection by dragging between node handles.
  const connect = useCallback(
    (connection: Connection) => {
      if (
        !connection.source ||
        !connection.target ||
        !onConnectNodes
      ) {
        return;
      }

      const kind = window.confirm(
        "Player choice? OK = choice, Cancel = automatic jump"
      )
        ? "choice"
        : "jump";

      const label =
        kind === "choice"
          ? window.prompt("Choice text:", "Continue")
          : "";

      if (label === null || (kind === "choice" && !label.trim())) {
        return;
      }

      onConnectNodes(
        connection.source,
        connection.target,
        kind,
        label ?? ""
      );
    },
    [onConnectNodes]
  );

  return (
    <div className="dlg-canvas">
      <ReactFlow
        nodes={liveNodes}
        edges={liveEdges}

        onNodesChange={(changes: NodeChange<Node>[]) =>
          setLiveNodes(current => applyNodeChanges(changes, current))
        }

        onEdgesChange={(changes: EdgeChange<Edge>[]) =>
          setLiveEdges(current => applyEdgeChanges(changes, current))
        }

        onConnect={connect}

        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}

        onEdgeClick={(_, edge) => {
          const original = graph.edges.find(
            item => item.id === edge.id
          );

          if (original) {
            onSelectEdge?.(original);
          }
        }}

        onNodeClick={(_, node) =>
          onSelectNode(node.data as GraphNode)
        }

        onPaneClick={onPaneClick}

        onNodeDragStop={(_, _node, nodes) =>
          nodes.forEach(node => onMoveNode(node.id, node.position))
        }
        onSelectionDragStop={(_, nodes) =>
          nodes.forEach(node => onMoveNode(node.id, node.position))
        }

        nodesConnectable={Boolean(onConnectNodes)}
        edgesReconnectable={false}
        deleteKeyCode={null}

        fitView
        // Keep the first view clear of the legend in the bottom-right corner.
        fitViewOptions={{ padding: { top: "5%", right: "10%", bottom: "72px", left: "10%" } }}
        minZoom={0.1}

        key={`${graph.snapshot_id}-${vertical}-${rotateLabels}`}
      >
        <Background gap={24} />
        <Controls showInteractive={false} />
      </ReactFlow>

      {onEditNode && (
        <div className="dlg-edit-hint">
          Click a node to select it, then use Edit node.
        </div>
      )}

      <div className="dlg-legend" aria-label="Edge legend">
        <span className="dlg-legend__item">
          <svg width="28" height="8" aria-hidden>
            <line
              x1="0"
              y1="4"
              x2="28"
              y2="4"
              stroke="#3d5a80"
              strokeWidth="2"
            />
          </svg>
          <span>Player choice</span>
        </span>

        <span className="dlg-legend__item">
          <svg width="28" height="8" aria-hidden>
            <line
              x1="0"
              y1="4"
              x2="28"
              y2="4"
              stroke="#8a5a00"
              strokeWidth="2"
            />
          </svg>
          <span>Jump (ends the node)</span>
        </span>

        <span className="dlg-legend__item">
          <svg width="28" height="8" aria-hidden>
            <line
              x1="0"
              y1="4"
              x2="28"
              y2="4"
              stroke="#8a5a00"
              strokeWidth="2"
              strokeDasharray="2 5"
              strokeLinecap="round"
            />
          </svg>
          <span>Jump (mid-dialogue)</span>
        </span>
      </div>

      {graph.diagnostics.length > 0 && (
        <ul className="dlg-diagnostics">
          {graph.diagnostics.map((d, i) => (
            <li key={i}>
              Line {d.line ?? "?"}: {d.message}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
