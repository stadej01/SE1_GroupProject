import { test } from "node:test";
import assert from "node:assert/strict";
import { sourceRange } from "./source";

test("node span includes its content but not the following node", () => {
  const source = "# A\nNarrator: Hello\n\n# B\nNarrator: Goodbye";
  const { start, end } = sourceRange(source, 1, 3);
  assert.equal(source.slice(start, end), "# A\nNarrator: Hello\n");
});
test("offsets match textarea UTF-16 positions after emoji", () => {
  const source = "Narrator: Hello 🌍\n# B\nNarrator: Bye";
  const { start, end } = sourceRange(source, 2, 3);
  assert.equal(source.slice(start, end), "# B\nNarrator: Bye");
});
test("a line diagnostic selects only the offending line", () => {
  const source = "# A\n???\n";
  const { start, end } = sourceRange(source, 2);
  assert.equal(source.slice(start, end), "???");
});
