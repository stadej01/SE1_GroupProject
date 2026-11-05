import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequest } from "./request";

test("sync and draft requests read the current token each time", async t => {
  let token = "old";
  const sent: string[] = [];
  const request = createRequest(() => token);
  t.mock.method(globalThis, "fetch", async (_url: string, init: RequestInit) => {
    sent.push(new Headers(init.headers).get("X-CSRFToken")!);
    return Response.json({ok:true});
  });
  await request("/sync", "POST", {});
  token = "new";
  await request("/save", "PUT", {});
  assert.deepEqual(sent, ["old", "new"]);
});
for (const status of [401, 403, 422, 200]) {
  test(`request keeps the HTTP status ${status}`, async t => {
    t.mock.method(globalThis, "fetch", async () => Response.json({ok:true, status:999}, {status}));
    const reply = await createRequest(() => "token")("/sync", "POST", {});
    assert.equal(reply.status, status);
    assert.equal(reply.ok, status === 200);
  });
}
test("HTML auth failures still expose status for Parse to retain the graph", async t => {
  t.mock.method(globalThis, "fetch", async () => new Response("<html>Forbidden</html>", {status:403}));
  assert.deepEqual(await createRequest(() => "token")("/sync", "POST", {}), {ok:false, status:403});
});
