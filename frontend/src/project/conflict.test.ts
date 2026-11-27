import { test } from "node:test";
import assert from "node:assert/strict";
import type { ProjectSnapshot } from "./api";
import { copyText, loadLatest } from "./conflict";

const latest: ProjectSnapshot = {
  markdown_source: "# Latest\nNarrator: Saved elsewhere.",
  revision: 4,
  layout_data: { nodes: [{ id: "Latest", position: { x: 10, y: 20 } }] },
};

test("copyText writes the exact text", async () => {
  const written: string[] = [];
  assert.equal(await copyText("# A\nB: text", { writeText: async text => { written.push(text); } }), true);
  assert.deepEqual(written, ["# A\nB: text"]);
});

test("copyText reports a refused or missing clipboard", async () => {
  assert.equal(await copyText("x", { writeText: async () => { throw new Error("denied"); } }), false);
  assert.equal(await copyText("x", undefined), false);
});

test("loadLatest applies the snapshot only after it arrives, while busy", async () => {
  const events: string[] = [];
  const result = await loadLatest({
    setBusy: busy => events.push(`busy:${busy}`),
    open: async () => { events.push("open"); return latest; },
    apply: snapshot => events.push(`apply:${snapshot.revision}`),
    fail: () => events.push("fail"),
  });
  assert.equal(result, latest);
  assert.deepEqual(events, ["busy:true", "open", "apply:4", "busy:false"]);
});

test("loadLatest keeps the editor unchanged when the read fails", async () => {
  const events: string[] = [];
  const failure = new Error("offline");
  const result = await loadLatest({
    setBusy: busy => events.push(`busy:${busy}`),
    open: async () => { throw failure; },
    apply: () => events.push("apply"),
    fail: error => events.push(error === failure ? "fail" : "wrong error"),
  });
  assert.equal(result, null);
  assert.deepEqual(events, ["busy:true", "busy:false", "fail"]);
});
