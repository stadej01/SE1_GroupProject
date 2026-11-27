import type { LayoutData } from "./layout";

export interface NodeComment {
  comment_id: string;
  project_id: string;
  node_id: string;
  author_id: number;
  author_name: string;
  body: string;
  created_at: string;
  edited_at: string | null;
}

export interface ProjectSnapshot {
  markdown_source: string;
  revision: number;
  layout_data: LayoutData;
  comments?: NodeComment[];
}

export interface SaveProject {
  markdown_source: string;
  layout_data: LayoutData;
  base_revision: number;
}

export class ProjectRequestError extends Error {
  constructor(
    public readonly status: number | null,
    public readonly detail: unknown = null,
    public readonly revision?: number,
    public readonly isJson = true,
  ) {
    super(status === null ? "Could not reach the server."
      : isJson ? `Project request failed (${status}).`
      : `The server returned an unexpected response (${status}).`);
    this.name = "ProjectRequestError";
  }
}

async function projectRequest<T>(url: string, init: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(url, { mode: "same-origin", credentials: "same-origin", ...init });
  } catch {
    throw new ProjectRequestError(null);
  }
  if (!response.headers.get("content-type")?.includes("application/json")) {
    throw new ProjectRequestError(response.status, null, undefined, false);
  }
  let body;
  try { body = await response.json(); }
  catch { throw new ProjectRequestError(response.status, null, undefined, false); }
  if (!response.ok) {
    throw new ProjectRequestError(response.status, body?.detail ?? body,
      typeof body?.revision === "number" ? body.revision : undefined);
  }
  return body as T;
}

export function openProject(url: string): Promise<ProjectSnapshot> {
  return projectRequest(url, { method: "GET", headers: { Accept: "application/json" } });
}

export function saveProject(url: string, csrf: string, body: SaveProject): Promise<{ revision: number }> {
  return projectRequest(url, {
    method: "PUT",
    headers: { "Content-Type": "application/json", "X-CSRFToken": csrf, Accept: "application/json" },
    body: JSON.stringify(body),
  });
}

function writeRequest(method: string, csrf: string, body?: object): RequestInit {
  return {
    method,
    headers: { "Content-Type": "application/json", "X-CSRFToken": csrf, Accept: "application/json" },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  };
}

export async function listComments(commentsUrl: string): Promise<NodeComment[]> {
  const reply = await projectRequest<{ comments: NodeComment[] }>(commentsUrl,
    { method: "GET", headers: { Accept: "application/json" } });
  return reply.comments;
}

export function createComment(commentsUrl: string, csrf: string, nodeId: string, body: string): Promise<NodeComment> {
  return projectRequest(commentsUrl, writeRequest("POST", csrf, { node_id: nodeId, body }));
}

export function updateComment(commentsUrl: string, csrf: string, commentId: string, body: string): Promise<NodeComment> {
  return projectRequest(`${commentsUrl}/${encodeURIComponent(commentId)}`, writeRequest("PUT", csrf, { body }));
}

export function deleteComment(commentsUrl: string, csrf: string, commentId: string): Promise<{ message: string }> {
  return projectRequest(`${commentsUrl}/${encodeURIComponent(commentId)}`, writeRequest("DELETE", csrf));
}
