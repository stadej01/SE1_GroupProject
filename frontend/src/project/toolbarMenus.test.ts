import { test } from "node:test";
import assert from "node:assert/strict";
import { panelShift } from "./toolbarMenus";

test("a panel that fits on screen stays where it is", () => {
  assert.equal(panelShift(900, 340, 1440), 0);
  assert.equal(panelShift(1092, 340, 1440), 0);
});

test("a panel past the right edge moves left to fit", () => {
  assert.equal(panelShift(1200, 340, 1440), 108);
});

test("a panel wider than the screen stays on the left margin", () => {
  assert.equal(panelShift(20, 400, 375), 12);
});
