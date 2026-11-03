import { Handle, Position, type NodeProps, type Node } from "@xyflow/react";
import type { GraphNode } from "../graph/contract";

const SWATCH: Record<string, string> = {
  blue: "#3d5a80", red: "#b23a48", green: "#4f7942", purple: "#6b4e9b",
};

type DialogueFlowNode = Node<GraphNode, "dialogue">;

export function DialogueNode({ data, selected }: NodeProps<DialogueFlowNode>) {
  const vertical = document.querySelector<HTMLSelectElement>("#graph-layout")?.value === "vertical";
  const accent = SWATCH[data.color ?? ""] ?? "#6b7280";
  return (
    <div
      className="dlg-node"
      style={{
        borderColor: selected ? "#f5b800" : undefined,
        boxShadow: selected ? "0 0 0 3px #f5c542, 0 0 0 5px rgba(245,197,66,.28)" : undefined,
      }}
    >
      {/* One handle each side; loops are routed by LoopEdge, not by extra handles. */}
      <Handle type="target" position={vertical ? Position.Top : Position.Left} id="in" />
      {/* The node's color fills the title bar. */}
      <div className="dlg-node__id" style={{ background: accent }} title={data.id}>{data.id}</div>
      <div className="dlg-node__body">
      <div className="dlg-node__preview">
        {data.dialogue_lines?.length ? data.dialogue_lines.map((line, index) => (
          <div className="dlg-node__line" key={`${line.source_line}-${index}`}>
            <strong>{line.speaker}:</strong> {line.text}
          </div>
        )) : (data.preview || "No dialogue lines")}
      </div>
      {data.category && <div className="dlg-node__category">{data.category}</div>}
      </div>
      <Handle type="source" position={vertical ? Position.Bottom : Position.Right} id="out" />
    </div>
  );
}
