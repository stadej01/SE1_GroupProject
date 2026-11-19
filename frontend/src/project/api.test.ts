import { test } from "node:test";
import assert from "node:assert/strict";
import { openProject, saveProject, ProjectRequestError } from "./api";

test("open accepts a project response without an ok field", async t => {
  const snapshot = { markdown_source: "# A\r\nHello", revision: 7, layout_data: { nodes: [] } };
  t.mock.method(globalThis, "fetch", async (url: string, init: RequestInit) => {
    assert.equal(url, "/projects/1");
    assert.equal(init.method, "GET");
    assert.equal(init.credentials, "same-origin");
    return Response.json(snapshot);
  });
  assert.deepEqual(await openProject("/projects/1"), snapshot);
});

test("save sends the project payload and accepts success without ok", async t => {
  const body = { markdown_source: "# A", base_revision: 7, layout_data: { nodes: [{ id: "A", position: { x: 20, y: 30 } }] } };
  t.mock.method(globalThis, "fetch", async (url: string, init: RequestInit) => {
    assert.equal(url, "/projects/1/save");
    assert.equal(init.method, "PUT");
    assert.equal(new Headers(init.headers).get("X-CSRFToken"), "test-csrf");
    assert.deepEqual(JSON.parse(init.body as string), body);
    return Response.json({ status: "saved", revision: 8, diagnostics: [] });
  });
  assert.equal((await saveProject("/projects/1/save", "test-csrf", body)).revision, 8);
});

test("open rejects HTTP failure even when its body contains project fields", async t => {
  t.mock.method(globalThis, "fetch", async () => Response.json({ revision: 4, markdown_source: "" }, { status: 503 }));
  await assert.rejects(openProject("/projects/1"), /503/);
});

test("open rejects an HTML login response", async t => {
  t.mock.method(globalThis, "fetch", async () => new Response("<html>Log in</html>", { headers: { "Content-Type": "text/html" } }));
  await assert.rejects(openProject("/projects/1"), /unexpected response/);
});

for (const [status, body, detail, revision] of [
  [403, { detail: "CSRF Failed: token changed" }, "CSRF Failed: token changed", undefined],
  [409, { detail: "Refresh", revision: 8 }, "Refresh", 8],
  [400, { markdown_source: ["Required"] }, { markdown_source: ["Required"] }, undefined],
] as const) {
  test(`project errors preserve response data for ${status}`, async t => {
    t.mock.method(globalThis, "fetch", async () => Response.json(body, { status }));
    await assert.rejects(openProject("/projects/1"), error => {
      assert.ok(error instanceof ProjectRequestError);
      assert.equal(error.status, status);
      assert.deepEqual(error.detail, detail);
      assert.equal(error.revision, revision);
      return true;
    });
  });
}
test("network failure has no HTTP status", async t => {
  t.mock.method(globalThis, "fetch", async () => { throw new TypeError("Failed to fetch"); });
  await assert.rejects(openProject("/projects/1"), error => {
    assert.ok(error instanceof ProjectRequestError);
    assert.equal(error.status, null);
    return true;
  });
});
test("HTML failure keeps status without exposing HTML in detail", async t => {
  t.mock.method(globalThis, "fetch", async () => new Response("<h1>Server error</h1>", { status: 500 }));
  await assert.rejects(openProject("/projects/1"), error => {
    assert.ok(error instanceof ProjectRequestError);
    assert.equal(error.status, 500);
    assert.equal(error.isJson, false);
    assert.equal(error.detail, null);
    return true;
  });
});
