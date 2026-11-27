import { test } from "node:test";
import assert from "node:assert/strict";
import { ProjectRequestError, type NodeComment } from "./api";
import { byNode, canModify, commentCounts, commentErrorMessage, commentStore, hasUnsentText, remove, upsert, UNSAVED_NODE } from "./comments";

function comment(id: string, node: string, created: string, author = 1): NodeComment {
  return { comment_id: id, project_id: "p", node_id: node, author_id: author, author_name: `User ${author}`,
    body: `Body ${id}`, created_at: created, edited_at: null };
}

const a = comment("a", "Node_1", "2026-11-22T10:00:00Z");
const b = comment("b", "Node_2", "2026-11-22T10:01:00Z", 2);
const c = comment("c", "Node_1", "2026-11-22T09:00:00Z", 2);

test("byNode groups comments by node, oldest first", () => {
  const grouped = byNode([a, b, c]);
  assert.deepEqual(grouped.get("Node_1")!.map(item => item.comment_id), ["c", "a"]);
  assert.deepEqual(grouped.get("Node_2")!.map(item => item.comment_id), ["b"]);
  assert.equal(grouped.get("Node_3"), undefined);
});

test("commentCounts counts comments per node", () => {
  assert.deepEqual([...commentCounts([a, b, c])].sort(), [["Node_1", 2], ["Node_2", 1]]);
});

test("upsert adds or replaces without changing the original store", () => {
  const store = commentStore([a]);
  const added = upsert(store, b);
  assert.equal(store.size, 1);
  assert.equal(added.size, 2);
  const edited = upsert(added, { ...a, body: "Edited", edited_at: "2026-11-22T11:00:00Z" });
  assert.equal(edited.size, 2);
  assert.equal(edited.get("a")!.body, "Edited");
  assert.equal(added.get("a")!.body, "Body a");
});

test("remove drops one comment without changing the original store", () => {
  const store = commentStore([a, b]);
  const removed = remove(store, "a");
  assert.deepEqual([...removed.keys()], ["b"]);
  assert.equal(store.size, 2);
  assert.equal(remove(store, "missing").size, 2);
});

test("only the author can modify a comment", () => {
  assert.equal(canModify(a, 1), true);
  assert.equal(canModify(a, 2), false);
  assert.equal(canModify(a, null), false);
});

test("error messages follow the server's reason and the operation", () => {
  const failed = (status: number | null, detail: unknown) => new ProjectRequestError(status, detail);
  assert.equal(commentErrorMessage(failed(404, UNSAVED_NODE), "add"), "Save the project before commenting on new nodes.");
  assert.match(commentErrorMessage(failed(404, "No Project matches the given query."), "add"), /project no longer exists/);
  assert.match(commentErrorMessage(failed(404, "No Project matches the given query."), "edit"), /project no longer exists/);
  assert.match(commentErrorMessage(failed(404, "No Comment matches the given query."), "edit"), /comment no longer exists/);
  assert.match(commentErrorMessage(failed(400, { body: ["Ensure this field has no more than 5000 characters."] }), "add"), /5000 characters/);
  assert.match(commentErrorMessage(failed(400, { node_id: ["Bad"] }), "add"), /could not accept/);
  assert.match(commentErrorMessage(failed(403, "You are not a member of this project's team."), "add"), /not a member/);
  assert.match(commentErrorMessage(failed(403, "Only the author can change this comment."), "delete"), /not deleted. Only the author/);
  assert.match(commentErrorMessage(failed(403, "CSRF Failed: x"), "add"), /Security check/);
  assert.match(commentErrorMessage(failed(null, null), "refresh"), /Could not reach.*not refreshed/);
  assert.match(commentErrorMessage(new Error("boom"), "add"), /not added/);
});

test("unsent text counts until it is blank, unchanged, or its node is gone", () => {
  const store = commentStore([a]);
  const drafts = (added: [string, string][], edited: [string, string][] = []) =>
    ({ added: new Map(added), edited: new Map(edited) });
  const nodes = new Set(["Node_1"]);
  assert.equal(hasUnsentText(drafts([["Node_1", "Hi"]]), store, nodes), true);
  assert.equal(hasUnsentText(drafts([["Node_1", "  "]]), store, nodes), false);
  assert.equal(hasUnsentText(drafts([["Gone", "Hi"]]), store, nodes), false);
  assert.equal(hasUnsentText(drafts([["Gone", "Hi"]]), store, null), true);
  assert.equal(hasUnsentText(drafts([], [["a", a.body]]), store, nodes), false);
  assert.equal(hasUnsentText(drafts([], [["a", "New"]]), store, nodes), true);
  assert.equal(hasUnsentText(drafts([], [["deleted", "New"]]), store, nodes), false);
});
