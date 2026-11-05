import { test } from "node:test";
import assert from "node:assert/strict";
import { ProjectRequestError } from "./api";
import { projectErrorNotice } from "./errors";

for (const [name, error, message, signIn] of [
  ["conflict", new ProjectRequestError(409, "Refresh the page before saving", 9), "A newer version was saved (revision 9). Your text is still here. Copy it, then reload.", false],
  ["signed out", new ProjectRequestError(401), "You are signed out. Your text is still here.", true],
  ["CSRF", new ProjectRequestError(403, "CSRF Failed: stale token"), "Security check failed. Copy your text, then reload.", false],
  ["membership", new ProjectRequestError(403, "Not a member"), "You no longer have access to this project. Your text is still here.", false],
  ["missing project", new ProjectRequestError(404), "This project no longer exists. Copy your text.", false],
  ["storage", new ProjectRequestError(503), "Project storage is not available right now. Nothing was saved. Try again later.", false],
  ["fields", new ProjectRequestError(400, {base_revision:["Required"]}), "The server could not accept this save. Your text is still here.", false],
  ["HTML", new ProjectRequestError(404, null, undefined, false), "The server had a problem (404). Your text is still here.", false],
  ["server error", new ProjectRequestError(500), "The server had a problem (500). Your text is still here.", false],
  ["other status", new ProjectRequestError(418), "The server had a problem (418). Your text is still here.", false],
  ["network", new ProjectRequestError(null), "Could not reach the server. Your text is still here. Try again.", false],
] as const) {
  test(`save notice: ${name}`, () => {
    const notice = projectErrorNotice(error);
    assert.equal(notice.message, message);
    assert.equal(Boolean(notice.signIn), signIn);
  });
}
for (const [status, message, signIn] of [
  [401, "You are signed out. The project could not be opened.", true],
  [403, "You do not have access to open this project.", false],
  [404, "This project no longer exists and cannot be opened.", false],
  [503, "Project storage is not available right now. Refresh later to try opening this project again.", false],
  [null, "Could not reach the server. Refresh later to try opening this project again.", false],
] as const) {
  test(`open notice: ${status}`, () => {
    const notice = projectErrorNotice(new ProjectRequestError(status), "open");
    assert.equal(notice.message, message);
    assert.equal(Boolean(notice.signIn), signIn);
  });
}
