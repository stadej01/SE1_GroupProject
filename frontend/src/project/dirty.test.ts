import { test } from "node:test";
import assert from "node:assert/strict";
import { isDirty, canApplySubmittedSource, type EditState } from "./dirty";

const clean: EditState = { source: "text", savedSource: "text", pendingMarkdown: null,
  project: true, positionVersion: 4, savedPositionVersion: 4 };
for (const [name, state, expected] of [
  ["saved project", clean, false],
  ["edited Markdown", { ...clean, source: "new text" }, true],
  ["pending graph edit", { ...clean, pendingMarkdown: "graph edit" }, true],
  ["pending empty Markdown", { ...clean, pendingMarkdown: "" }, true],
  ["moved nodes", { ...clean, positionVersion: 5 }, true],
  ["demo ignores positions", { ...clean, project: false, positionVersion: 5 }, false],
  ["demo tracks text", { ...clean, project: false, source: "new" }, true],
  ["demo tracks graph edits", { ...clean, project: false, pendingMarkdown: "new" }, true],
] as const) {
  test(`dirty state: ${name}`, () => assert.equal(isDirty(state), expected));
}
test("a drag during saving stays dirty after the submitted position version is saved", () => {
  let state = { ...clean, positionVersion: 5 };
  const submittedVersion = state.positionVersion;
  state.positionVersion++;
  state.savedPositionVersion = submittedVersion;
  assert.equal(isDirty(state), true);
  state.savedPositionVersion = state.positionVersion;
  assert.equal(isDirty(state), false);
});
test("save can sync unchanged pending graph edits", () => {
  assert.equal(canApplySubmittedSource("submitted", "submitted"), true);
});
test("save cannot replace typing or newer graph edits", () => {
  assert.equal(canApplySubmittedSource(null, "submitted"), false);
  assert.equal(canApplySubmittedSource("new graph edit", "submitted"), false);
});
