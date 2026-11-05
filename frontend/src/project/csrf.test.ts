import { test } from "node:test";
import assert from "node:assert/strict";
import { readCsrfToken } from "./csrf";

test("reads the configured token among several cookies", () => {
  const cookies = "session=abc; csrftoken=shared; se1_editor_csrftoken=demo; suffix_csrftoken=wrong";
  assert.equal(readCsrfToken(cookies, "csrftoken"), "shared");
  assert.equal(readCsrfToken(cookies, "se1_editor_csrftoken"), "demo");
});
test("returns an empty token when the cookie is missing", () => {
  assert.equal(readCsrfToken("", "csrftoken"), "");
  assert.equal(readCsrfToken("other_csrftoken=wrong", "csrftoken"), "");
});
test("decodes the cookie value without including other cookies", () => {
  assert.equal(readCsrfToken("csrftoken=a%3Db; session=abc", "csrftoken"), "a=b");
});
