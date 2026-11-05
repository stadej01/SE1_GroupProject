import type { DialogueGraph } from "../graph/contract";
import { toFlow } from "../graph/toFlow";

export type Positions = Map<string, { x: number; y: number }>;
export interface LayoutData {
  nodes: { id: string; position: { x: number; y: number } }[];
}

export function readPositions(layout: LayoutData): Positions {
  return new Map(layout.nodes.map(node => [node.id, { ...node.position }]));
}

export function writeLayout(positions: Positions): LayoutData {
  return { nodes: [...positions].map(([id, position]) => ({ id, position: { ...position } })) };
}

export function saveLayout(graph: DialogueGraph | null, positions: Positions, vertical: boolean): LayoutData {
  if (!graph) return writeLayout(positions);
  return { nodes: toFlow(graph, positions, vertical).nodes.map(({ id, position }) => ({ id, position: { ...position } })) };
}

export function applyLayout(positions: Positions, layout: LayoutData): void {
  for (const [id, position] of readPositions(layout)) positions.set(id, position);
}

export function fillMissingPositions(positions: Positions, layout: LayoutData): void {
  for (const [id, position] of readPositions(layout)) {
    if (!positions.has(id)) positions.set(id, position);
  }
}
