import { test } from "node:test";
import assert from "node:assert/strict";
import { createStore, initializeEditor } from "./store";
import type { ProjectSnapshot } from "./api";

const projectOptions = {
  openUrl: "/projects/1", saveUrl: "/projects/1/save", getCsrfToken: () => "test-csrf",
  request: async () => { throw new Error("Project must not use the draft request."); },
};

test("the demo keeps its draft endpoint, payload, and labels", async t => {
  t.mock.method(globalThis, "fetch", async () => { throw new Error("Demo must not use the project API."); });
  const positions = new Map([["A", { x: 0, y: 0 }]]);
  const store = createStore({ ...projectOptions, openUrl: "", saveUrl: "/save", request: async (url, method, body) => {
    assert.equal(url, "/save");
    assert.equal(method, "PUT");
    assert.deepEqual(body, { markdown_source: "draft text", revision: 3 });
    return { ok: true, revision: 4 };
  } });
  assert.equal(await store.open(), null);
  assert.deepEqual(await store.save("draft text", 3, null, positions, false), { revision: 4 });
  assert.equal(store.savedLabel, "Draft saved");
});

test("project saves use base_revision and a copy of the submitted positions", async t => {
  const positions = new Map([["A", { x: 10, y: 20 }]]);
  t.mock.method(globalThis, "fetch", async (_url: string, init: RequestInit) => {
    assert.deepEqual(JSON.parse(init.body as string), {
      markdown_source: "# A", base_revision: 3, layout_data: { nodes: [{ id: "A", position: { x: 10, y: 20 } }] },
    });
    return Response.json({ revision: 4 });
  });
  const store = createStore(projectOptions);
  assert.deepEqual(await store.save("# A", 3, null, positions, false), { revision: 4 });
  assert.equal(store.savedLabel, "Saved");
});

test("failed saves leave working positions unchanged and do not return a newer revision", async t => {
  const positions = new Map([["A", { x: 10, y: 20 }]]);
  t.mock.method(globalThis, "fetch", async () => Response.json({ revision: 99 }, { status: 409 }));
  await assert.rejects(createStore(projectOptions).save("edited", 3, null, positions, false), /409/);
  assert.deepEqual([...positions], [["A", { x: 10, y: 20 }]]);
});

test("each project save reads the current CSRF token", async t => {
  let token = "before-login";
  const sent: string[] = [];
  t.mock.method(globalThis, "fetch", async (_url: string, init: RequestInit) => {
    sent.push(new Headers(init.headers).get("X-CSRFToken")!);
    return Response.json({ revision: 4 });
  });
  const store = createStore({ ...projectOptions, getCsrfToken: () => token });
  await store.save("text", 2, null, new Map(), false);
  token = "after-login";
  await store.save("text", 3, null, new Map(), false);
  assert.deepEqual(sent, ["before-login", "after-login"]);
});

test("save completion keeps a node moved while the request was pending", async t => {
  const positions = new Map([["A", { x: 10, y: 20 }]]);
  let deliver!: (response: Response) => void;
  t.mock.method(globalThis, "fetch", () => new Promise<Response>(resolve => { deliver = resolve; }));
  const saving = createStore(projectOptions).save("text", 3, null, positions, false);
  positions.set("A", { x: 50, y: 80 });
  deliver(Response.json({ revision: 4 }));
  await saving;
  assert.deepEqual(positions.get("A"), { x: 50, y: 80 });
});

function editorSpy() {
  const events: string[] = [];
  return {
    events,
    setEnabled(enabled: boolean) { events.push(`enabled:${enabled}`); },
    restore(_snapshot: ProjectSnapshot) { events.push("restore"); },
    setStatus(message: string, error: boolean) { events.push(`status:${error}:${message}`); },
    async parse() { events.push("parse"); },
  };
}

test("opening keeps editing locked until content arrives and enables Parse before calling it", async t => {
  let deliver!: (response: Response) => void;
  t.mock.method(globalThis, "fetch", () => new Promise<Response>(resolve => { deliver = resolve; }));
  const editor = editorSpy();
  const opening = initializeEditor(createStore(projectOptions), editor);
  assert.deepEqual(editor.events, ["enabled:false"]);
  deliver(Response.json({ markdown_source: "# A", revision: 3, layout_data: { nodes: [] } }));
  await opening;
  assert.deepEqual(editor.events, ["enabled:false", "restore", "status:false:Saved", "enabled:true", "parse"]);
});

test("a failed open keeps editing locked and displays an error", async t => {
  t.mock.method(globalThis, "fetch", async () => Response.json({}, { status: 503 }));
  const editor = editorSpy();
  await initializeEditor(createStore(projectOptions), editor);
  assert.deepEqual(editor.events, ["enabled:false", "enabled:false", "status:true:Project storage is not available right now. Refresh later to try opening this project again."]);
});

test("empty projects open without parsing", async t => {
  t.mock.method(globalThis, "fetch", async () => Response.json({ markdown_source: "", revision: 1, layout_data: { nodes: [] } }));
  const editor = editorSpy();
  await initializeEditor(createStore(projectOptions), editor);
  assert.deepEqual(editor.events, ["enabled:false", "restore", "status:false:Saved", "enabled:true"]);
});

test("demo startup does not fetch, restore, or parse", async t => {
  t.mock.method(globalThis, "fetch", async () => { throw new Error("Unexpected fetch"); });
  const editor = editorSpy();
  await initializeEditor(createStore({ ...projectOptions, openUrl: undefined }), editor);
  assert.deepEqual(editor.events, ["enabled:true"]);
});
