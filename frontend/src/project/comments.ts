import { ProjectRequestError, type NodeComment } from "./api";

// comments are kept apart from the graph, the pending Markdown, and Undo,
// so adding or removing one never counts as an unsaved change.
export type CommentStore = Map<string, NodeComment>;

export function commentStore(comments: readonly NodeComment[] = []): CommentStore {
  return new Map(comments.map(comment => [comment.comment_id, comment]));
}

function byCreated(a: NodeComment, b: NodeComment) {
  return a.created_at.localeCompare(b.created_at) || a.comment_id.localeCompare(b.comment_id);
}

/** Comments grouped by node ID, oldest first. */
export function byNode(comments: Iterable<NodeComment>): Map<string, NodeComment[]> {
  const grouped = new Map<string, NodeComment[]>();
  for (const comment of comments) {
    const list = grouped.get(comment.node_id);
    if (list) list.push(comment); else grouped.set(comment.node_id, [comment]);
  }
  for (const list of grouped.values()) list.sort(byCreated);
  return grouped;
}

export function commentCounts(comments: Iterable<NodeComment>): Map<string, number> {
  const counts = new Map<string, number>();
  for (const comment of comments) counts.set(comment.node_id, (counts.get(comment.node_id) ?? 0) + 1);
  return counts;
}

export function upsert(store: CommentStore, comment: NodeComment): CommentStore {
  return new Map(store).set(comment.comment_id, comment);
}

export function remove(store: CommentStore, commentId: string): CommentStore {
  const next = new Map(store);
  next.delete(commentId);
  return next;
}

export function canModify(comment: NodeComment, userId: number | null): boolean {
  return userId !== null && comment.author_id === userId;
}

/** Text the user typed but has not sent: new comments by node ID, edits by comment ID. */
export interface CommentDrafts {
  added: ReadonlyMap<string, string>;
  edited: ReadonlyMap<string, string>;
}

/** With node IDs, drafts on nodes that are no longer in the graph do not count. */
export function hasUnsentText(drafts: CommentDrafts, store: CommentStore, nodeIds: ReadonlySet<string> | null): boolean {
  const reachable = (nodeId: string) => nodeIds === null || nodeIds.has(nodeId);
  return [...drafts.added].some(([nodeId, text]) => text.trim() !== "" && reachable(nodeId))
    || [...drafts.edited].some(([commentId, text]) => {
      const comment = store.get(commentId);
      return comment !== undefined && text !== comment.body && reachable(comment.node_id);
    });
}

export type CommentOperation = "add" | "edit" | "delete" | "refresh";

export const UNSAVED_NODE = "Save the project before commenting on this node.";

const FAILED: Record<CommentOperation, string> = {
  add: "The comment was not added.",
  edit: "The comment was not changed.",
  delete: "The comment was not deleted.",
  refresh: "The comments were not refreshed.",
};

// A 400 names the rejected field, such as {"body": ["..."]}.
function fieldMessage(detail: unknown): string | null {
  if (typeof detail !== "object" || detail === null) return null;
  const messages = (detail as { body?: unknown }).body;
  return Array.isArray(messages) && typeof messages[0] === "string" ? messages[0] : null;
}

export function commentErrorMessage(error: unknown, operation: CommentOperation): string {
  const failed = FAILED[operation];
  if (!(error instanceof ProjectRequestError)) return `${failed} Try again.`;
  const { status, isJson } = error;
  const detail = typeof error.detail === "string" ? error.detail : "";
  if (status === null) return `Could not reach the server. ${failed} Try again.`;
  if (!isJson) return `The server had a problem (${status}). ${failed}`;
  switch (status) {
    case 400: return `${failed} ${fieldMessage(error.detail) ?? "The server could not accept it."}`;
    case 401: return `You are signed out. ${failed} Sign in again.`;
    case 403:
      if (detail.startsWith("CSRF Failed")) return `Security check failed. ${failed} Copy any text, then reload.`;
      return `${failed} ${detail || "You do not have access."}`;
    case 404:
      if (operation === "add" && detail === UNSAVED_NODE) return "Save the project before commenting on new nodes.";
      if (detail.includes("Comment")) return "This comment no longer exists. Refresh comments to see the latest.";
      return `This project no longer exists. ${failed}`;
    case 503: return `Project storage is not available right now. ${failed} Try again later.`;
    default: return `The server had a problem (${status}). ${failed} Try again.`;
  }
}
