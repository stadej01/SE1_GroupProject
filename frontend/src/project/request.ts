import type { Diagnostic, DialogueGraph } from "../graph/contract";

// A stalled sync/open request must not leave the editor permanently showing
// "Parsing…" with its controls disabled. The caller's AbortSignal still wins
// immediately; this is only a safety net for a server or connection that
// never completes.
export const REQUEST_TIMEOUT_MS = 30_000;

export interface Reply {
  ok: boolean;
  status: number;
  detail?: string;
  graph?: DialogueGraph;
  diagnostics?: Diagnostic[];
  revision?: number;
  continuity_status?: "clean" | "issues";
  issues?: Diagnostic[];
}

export function createRequest(getCsrfToken: () => string) {
  return async (url: string, method: string, body: object, signal?: AbortSignal): Promise<Reply> => {
    const controller = new AbortController();
    let timedOut = false;
    const timeout = setTimeout(() => {
      timedOut = true;
      controller.abort();
    }, REQUEST_TIMEOUT_MS);
    const abortFromCaller = () => controller.abort();
    signal?.addEventListener("abort", abortFromCaller, { once: true });

    try {
      const response = await fetch(url, {
        method, mode: "same-origin", credentials: "same-origin", signal: controller.signal,
        headers: { "Content-Type": "application/json", "X-CSRFToken": getCsrfToken() },
        body: JSON.stringify(body),
      });
      if (!response.headers.get("content-type")?.includes("application/json")) {
        if (response.status === 401 || response.status === 403) return { ok: false, status: response.status };
        throw new Error(`The server returned an unexpected response (${response.status}). Your text is still in the editor.`);
      }
      const reply = await response.json() as Reply;
      return { ...reply, ok: response.ok && reply.ok, status: response.status };
    } catch (error) {
      if (timedOut) {
        throw new Error("The server did not respond within 30 seconds. Your text is still in the editor.");
      }
      throw error;
    } finally {
      clearTimeout(timeout);
      signal?.removeEventListener("abort", abortFromCaller);
    }
  };
}
