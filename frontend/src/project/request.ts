import type { Diagnostic, DialogueGraph } from "../graph/contract";

export interface Reply {
  ok: boolean;
  status: number;
  detail?: string;
  graph?: DialogueGraph;
  diagnostics?: Diagnostic[];
  revision?: number;
}

export function createRequest(getCsrfToken: () => string) {
  return async (url: string, method: string, body: object, signal?: AbortSignal): Promise<Reply> => {
    const response = await fetch(url, {
      method, mode: "same-origin", credentials: "same-origin", signal,
      headers: { "Content-Type": "application/json", "X-CSRFToken": getCsrfToken() },
      body: JSON.stringify(body),
    });
    if (!response.headers.get("content-type")?.includes("application/json")) {
      if (response.status === 401 || response.status === 403) return { ok: false, status: response.status };
      throw new Error(`The server returned an unexpected response (${response.status}). Your text is still in the editor.`);
    }
    const reply = await response.json() as Reply;
    return { ...reply, ok: response.ok && reply.ok, status: response.status };
  };
}
