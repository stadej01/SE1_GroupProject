import type { Diagnostic } from "../graph/contract";
import { ProjectRequestError } from "./api";
import type { ErrorNotice } from "./errors";

export interface ExportResult {
  blob: Blob;
  filename: string;
  warnings: Diagnostic[];
}

// The saved Markdown failed validation. The diagnostics explain why.
export class ExportBlockedError extends Error {
  constructor(public readonly diagnostics: Diagnostic[], public readonly detectedAt?: string) {
    super("Export blocked by errors.");
    this.name = "ExportBlockedError";
  }
}

export function exportFilename(disposition: string | null, fallback = "dialogue.json"): string {
  if (!disposition) return fallback;
  const encoded = disposition.match(/filename\*\s*=\s*(?:utf-8|UTF-8)''([^;]+)/);
  if (encoded) {
    try { return decodeURIComponent(encoded[1].trim()); } catch { /* fall through */ }
  }
  const plain = disposition.match(/filename\s*=\s*"?([^";]+)"?/);
  return plain ? plain[1].trim() : fallback;
}

export function parseWarnings(header: string | null): Diagnostic[] {
  if (!header) return [];
  try {
    const value = JSON.parse(header);
    return Array.isArray(value) ? value : [];
  } catch { return []; }
}

export interface UnsavedExport {
  markdown: string;
  csrf: string;
}

// Without unsaved, the server exports the saved Markdown. With it, the server
// exports that text instead and saves nothing.
export async function exportProject(url: string, unsaved?: UnsavedExport): Promise<ExportResult> {
  const init: RequestInit = unsaved
    ? { method: "POST", body: JSON.stringify({ markdown_source: unsaved.markdown }),
        headers: { "Content-Type": "application/json", "X-CSRFToken": unsaved.csrf, Accept: "application/json" } }
    : { method: "GET", headers: { Accept: "application/json" } };
  let response: Response;
  try {
    response = await fetch(url, { ...init, mode: "same-origin", credentials: "same-origin" });
  } catch {
    throw new ProjectRequestError(null);
  }
  if (!response.headers.get("content-type")?.includes("application/json")) {
    throw new ProjectRequestError(response.status, null, undefined, false);
  }
  if (!response.ok) {
    let body;
    try { body = await response.json(); }
    catch { throw new ProjectRequestError(response.status, null, undefined, false); }
    if (response.status === 422) throw new ExportBlockedError(body?.diagnostics ?? [], body?.detected_at);
    throw new ProjectRequestError(response.status, body?.detail ?? body);
  }
  
  // Keep the server's JSON byte for byte instead of re-serializing it.
  const text = await response.text();
  return {
    blob: new Blob([text], { type: "application/json" }),
    filename: exportFilename(response.headers.get("content-disposition")),
    warnings: parseWarnings(response.headers.get("x-dialogue-warnings")),
  };
}

export function exportErrorNotice(error: unknown): ErrorNotice {
  if (!(error instanceof ProjectRequestError)) return { message: "The server had a problem. Nothing was exported." };
  const { status, isJson, detail } = error;
  if (status === null) return { message: "Could not reach the server. Nothing was exported." };
  if (!isJson) return { message: `The server had a problem (${status}). Nothing was exported.` };
  switch (status) {
    case 401: return { message: "You are signed out. Nothing was exported.", signIn: true };
    case 400: return { message: "The editor text could not be sent. Nothing was exported." };
    case 403:
      if (typeof detail === "string" && detail.startsWith("CSRF Failed")) {
        return { message: "Security check failed. Try reloading the page." };
      }
      return { message: "You do not have access to export this project." };
    case 404: return { message: "This project no longer exists and cannot be exported." };
    case 503: return { message: "Project storage is not available right now. Nothing was exported. Try again later." };
    default: return { message: `The server had a problem (${status}). Nothing was exported.` };
  }
}

export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 0);
}
