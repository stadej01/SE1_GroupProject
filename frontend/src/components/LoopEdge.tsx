import { BaseEdge, EdgeLabelRenderer, useNodes, type EdgeProps, type Edge } from "@xyflow/react";
import { NODE_H, NODE_W, loopClearance, loopPath } from "../graph/toFlow";

type LoopData = { kind: "choice" | "jump"; condition: string | null; backEdge: boolean; lane: number; rotateLabels?: boolean };

/**
 * US-29 AC2. Clearance is computed from the nodes' *current* positions, so the
 * loop's bottom segment stays below nodes in its span after dragging. Side
 * gutters are not a general obstacle router; see README for that limitation.
 */
export function LoopEdge(props: EdgeProps<Edge<LoopData, "loop">>) {
  const { id, sourceX, sourceY, targetX, targetY, style, markerEnd, label, data } = props;
  const lane = data?.lane ?? 0;

  const boxes = useNodes().map((n) => ({
    x: n.position.x,
    y: n.position.y,
    width: n.measured?.width ?? n.width ?? NODE_W,
    height: n.measured?.height ?? n.height ?? NODE_H,
  }));
  const clearY = loopClearance(boxes, targetX, sourceX, lane);
  const { path, labelX, labelY } = loopPath(sourceX, sourceY, targetX, targetY, clearY, lane);

  return (
    <>
      <BaseEdge id={id} path={path} style={style} markerEnd={markerEnd} />
      {label && (
        <EdgeLabelRenderer>
          <div
            className="dlg-edge-label nodrag nopan"
            style={{ transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px) ${data?.rotateLabels ? "rotate(-90deg)" : ""}` }}
          >
            {label}
          </div>
        </EdgeLabelRenderer>
      )}
    </>
  );
}
