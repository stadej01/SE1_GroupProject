
import { createContext, useContext } from "react";
import { Handle, Position, type NodeProps, type Node } from "@xyflow/react";
import type { GraphNode } from "../graph/contract";

// While the node details are open, only the node they describe is highlighted.
export const EditingNodeContext = createContext<string | null>(null);

// review comment counts by node ID. Kept out of the node data, because
// that data is turned back into Markdown.
export const CommentCountContext = createContext<ReadonlyMap<string, number>>(new Map());

// A speech bubble drawn in the text color, so it looks the same on every system.
// Decorative only: the badge's text says how many comments there are.
function CommentIcon() {
  return (
    <svg
      className="dlg-node__comments-icon"
      viewBox="0 0 16 16"
      aria-hidden="true"
      focusable="false"
    >
      <path
        d="M2.5 3.5a1 1 0 0 1 1-1h9a1 1 0 0 1 1 1v6a1 1 0 0 1-1 1H7l-3 2.5v-2.5h-.5a1 1 0 0 1-1-1z"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinejoin="round"
      />
    </svg>
  );
}

// Available node colors.
const SWATCH: Record<string, string> = {
  blue: "#3d5a80",
  red: "#b23a48",
  green: "#4f7942",
  purple: "#6b4e9b",
};

type DialogueFlowNode = Node<GraphNode, "dialogue">;

export function DialogueNode({ data, selected }: NodeProps<DialogueFlowNode>) {
  const editingNodeId = useContext(EditingNodeContext);
  const highlighted = editingNodeId === null ? selected : editingNodeId === data.id;
  const commentCount = useContext(CommentCountContext).get(data.id) ?? 0;

  // Determine whether the graph is using vertical or horizontal layout.
  const vertical =
    document.querySelector<HTMLSelectElement>("#graph-layout")?.value === "vertical";

  // Use the node's assigned color, or gray if none is provided.
  const accent = SWATCH[data.color ?? ""] ?? "#6b7280";

  return (
    <div
      className="dlg-node"
      style={{
        // Highlight selected nodes in yellow without removing their color.
        // A borderColor shorthand would also replace the left stripe's color.
        borderTopColor: highlighted ? "#f5b800" : undefined,
        borderRightColor: highlighted ? "#f5b800" : undefined,
        borderBottomColor: highlighted ? "#f5b800" : undefined,
        boxShadow: highlighted
          ? "0 0 0 3px #f5c542, 0 0 0 5px rgba(245,197,66,.28)"
          : undefined,
        borderLeft: `6px solid ${accent}`,
      }}
    >
      {/* One handle each side; loops are routed by LoopEdge, not by extra handles. */}
      <Handle
        type="target"
        position={vertical ? Position.Top : Position.Left}
        id="in"
      />

      <div className="dlg-node__heading">
        <div
          className="dlg-node__id"
          style={{ background: accent }}
          title={data.id}
        >
          {data.id}
        </div>
        {commentCount > 0 && (
          <span
            className="dlg-node__comments"
            title={`${commentCount} comment${commentCount === 1 ? "" : "s"}`}
          >
            <CommentIcon />
            {commentCount}
            {}
            <span className="visually-hidden"> comment{commentCount === 1 ? "" : "s"}</span>
          </span>
        )}
        {data.is_start && <span className="dlg-node__start">START</span>}
      </div>

      <div className="dlg-node__body">
        <div className="dlg-node__preview">
          {data.dialogue_lines?.length
            ? data.dialogue_lines.map(
                (
                  line: NonNullable<GraphNode["dialogue_lines"]>[number],
                  index: number
                ) => (
                  <div
                    className="dlg-node__line"
                    key={`${line.source_line}-${index}`}
                  >
                    <strong>{line.speaker}:</strong> {line.text}
                  </div>
                )
              )
            : (data.preview || "No dialogue lines")}
        </div>

        {data.category && (
          <div className="dlg-node__category">
            {data.category}
          </div>
        )}
      </div>

      <Handle
        type="source"
        position={vertical ? Position.Bottom : Position.Right}
        id="out"
      />
    </div>
  );
}
