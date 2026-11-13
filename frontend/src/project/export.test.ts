import { test } from "node:test";
import assert from "node:assert/strict";
import { ProjectRequestError } from "./api";
import { ExportBlockedError, exportErrorNotice, exportFilename, exportProject, parseWarnings } from "./export";

const EXPORT = { schema_version: "1.0", snapshot_id: "abc", start_nodes: ["Node_1"], nodes: [] };

test("export downloads the server JSON with its file name and warnings", async test => {
  const warnings = [{ severity: "warning", message: "Starting nodes have not been allocated." }];
  test.mock.method(globalThis, "fetch", async (url: string, init: RequestInit) => {
    assert.equal(url, "/api/v1/projects/1/export");
    assert.equal(init.method, "GET");
    assert.equal(init.credentials, "same-origin");
    return Response.json(EXPORT, { headers: {
      "Content-Disposition": 'attachment; filename="act-1.json"',
      "X-Dialogue-Warnings": JSON.stringify(warnings),
    } });
  });
  const result = await exportProject("/api/v1/projects/1/export");
  assert.equal(result.filename, "act-1.json");
  assert.deepEqual(result.warnings, warnings);
  assert.deepEqual(JSON.parse(await result.blob.text()), EXPORT);
  assert.equal(result.blob.type, "application/json");
});

test("a 422 reply becomes an ExportBlockedError with the error log", async test => {
  const diagnostics = [{ severity: "error", line: 4, node_id: "Node_1", message: "Unrecognized line",
    detected_at: "2026-11-10T21:30:00Z", snapshot_id: "abc" }];
  test.mock.method(globalThis, "fetch", async () => Response.json(
    { ok: false, detected_at: "2026-11-10T21:30:00Z", snapshot_id: "abc", diagnostics }, { status: 422 }));
  await assert.rejects(exportProject("/x"), (error: unknown) => {
    assert.ok(error instanceof ExportBlockedError);
    assert.deepEqual(error.diagnostics, diagnostics);
    assert.equal(error.detectedAt, "2026-11-10T21:30:00Z");
    return true;
  });
});

for (const status of [401, 403, 404, 503]) {
  test(`a ${status} reply is a ProjectRequestError`, async test => {
    test.mock.method(globalThis, "fetch", async () => Response.json({ detail: "No." }, { status }));
    await assert.rejects(exportProject("/x"), (error: unknown) =>
      error instanceof ProjectRequestError && error.status === status && error.detail === "No.");
  });
}

test("an HTML reply and a network failure are reported without JSON", async test => {
  test.mock.method(globalThis, "fetch", async () => new Response("<html></html>", { headers: { "Content-Type": "text/html" } }));
  await assert.rejects(exportProject("/x"), (error: unknown) => error instanceof ProjectRequestError && !error.isJson);
  test.mock.restoreAll();
  test.mock.method(globalThis, "fetch", async () => { throw new TypeError("offline"); });
  await assert.rejects(exportProject("/x"), (error: unknown) => error instanceof ProjectRequestError && error.status === null);
});

test("file names come from the plain or encoded header, else the fallback", () => {
  assert.equal(exportFilename('attachment; filename="act-1.json"'), "act-1.json");
  assert.equal(exportFilename("attachment; filename*=utf-8''acto%20uno.json"), "acto uno.json");
  assert.equal(exportFilename(null), "dialogue.json");
  assert.equal(exportFilename("attachment"), "dialogue.json");
});

test("warnings header tolerates absence and bad JSON", () => {
  assert.deepEqual(parseWarnings(null), []);
  assert.deepEqual(parseWarnings("not json"), []);
  assert.deepEqual(parseWarnings('{"a":1}'), []);
});

for (const [error, message, signIn] of [
  [new ProjectRequestError(401), "You are signed out. Nothing was exported.", true],
  [new ProjectRequestError(403, "Not a member"), "You do not have access to export this project.", false],
  [new ProjectRequestError(404), "This project no longer exists and cannot be exported.", false],
  [new ProjectRequestError(503), "Project storage is not available right now. Nothing was exported. Try again later.", false],
  [new ProjectRequestError(null), "Could not reach the server. Nothing was exported. Try again.", false],
  [new ProjectRequestError(500, null, undefined, false), "The server had a problem (500). Nothing was exported.", false],
] as const) {
  test(`export notice: ${message}`, () => {
    const notice = exportErrorNotice(error);
    assert.equal(notice.message, message);
    assert.equal(Boolean(notice.signIn), signIn);
  });
}
