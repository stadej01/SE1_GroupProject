import { test } from "node:test";
import assert from "node:assert/strict";
import { appendNode, setStartNodes } from "./graphEdits";

test("appends an isolated node with its requested ID", () => {
  const updated = appendNode("# A\nNarrator: Hello.\n", "B", "Narrator", "Goodbye.");
  assert.match(updated, /# B\nNarrator: Goodbye\.\n$/);
  assert.doesNotMatch(updated, /(?:->|<<jump:)/);
});

test("sets multiple starting node directives and can clear them", () => {
  const source = "# A\nNarrator: Hello.\n\n# B\nNarrator: Goodbye.\n";
  const started = setStartNodes(source, ["B", "A"]);
  assert.equal(started, "<!-- start: B -->\n<!-- start: A -->\n" + source);
  assert.equal(setStartNodes(started, ["A"]), "<!-- start: A -->\n" + source);
  assert.equal(setStartNodes(started, []), source);
});

test("rejects a start ID that is not a node in the draft", () => {
  assert.throws(() => setStartNodes("# A\n", ["Missing"]), /does not exist/);
});
