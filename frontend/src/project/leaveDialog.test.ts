import { test } from "node:test";
import assert from "node:assert/strict";
import { shouldConfirmLeave, type LeaveClick } from "./leaveDialog";

const plain: LeaveClick = { button: 0, metaKey: false, ctrlKey: false, shiftKey: false, altKey: false };

test("a plain click with unsaved changes asks first", () => {
  assert.equal(shouldConfirmLeave(plain, true), true);
});

test("a plain click without unsaved changes leaves directly", () => {
  assert.equal(shouldConfirmLeave(plain, false), false);
});

for (const [name, click] of [
  ["Cmd", { ...plain, metaKey: true }],
  ["Ctrl", { ...plain, ctrlKey: true }],
  ["Shift", { ...plain, shiftKey: true }],
  ["Alt", { ...plain, altKey: true }],
  ["middle button", { ...plain, button: 1 }],
] as const) {
  test(`${name} click is left to the browser even with unsaved changes`, () => {
    assert.equal(shouldConfirmLeave(click, true), false);
  });
}
